"""
sincronizacao.py — Etapa 0 do pipeline de análise pupilométrica.

Estabelece os dois pontos-âncora que alinham o eixo de tempo do
eye-tracker (Pupil Labs, frames de vídeo) com o eixo de tempo da
telemetria (MoTeC, segundos), e persiste esses âncoras no banco de
dados para uso pelos demais scripts do TCC.

Fluxo:
    Etapa 1 → Ponto de sync do Pupil Labs (frame na largada)
    Etapa 2 → Mapeamento de voltas via Car Pos Norm (MoTeC)
    Etapa 3 → Cálculo do offset e confirmação do alinhamento
    Etapa 4 → Seleção da melhor volta e fixações âncora
"""

import pandas as pd

from backend.database import SessionLocal
from backend.db_ops import (
    get_or_create_piloto,
    get_or_create_sessao,
    upsert_parametros_sync,
    upsert_volta,
)
from backend.models import ParametrosSync, Volta
from codigos_tcc.configuracao import PILOTOS
from codigos_tcc.individual import clean_col, force_float, tradutor_de_tempos


# ---------------------------------------------------------------------------
# Helpers de entrada interativa
# ---------------------------------------------------------------------------

def _input_int(prompt: str) -> int:
    """Repete o prompt até o usuário digitar um inteiro válido."""
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("   Valor inválido. Digite um número inteiro.")


def _selecionar_piloto() -> str:
    """Exibe a lista de pilotos cadastrados e retorna o nome escolhido."""
    nomes = list(PILOTOS.keys())
    print("\nPilotos disponíveis:")
    for i, nome in enumerate(nomes, start=1):
        print(f"  {i}. {nome}")
    while True:
        try:
            idx = int(input("Escolha o número do piloto: ").strip()) - 1
            if 0 <= idx < len(nomes):
                return nomes[idx]
        except ValueError:
            pass
        print("   Opção inválida. Tente novamente.")


def _selecionar_sessao() -> str:
    """Pede o nome da sessão ao operador (ex.: 'InterTatus — Maio/2024')."""
    while True:
        nome = input("Nome da sessão (ex: 'InterTatus_2024'): ").strip()
        if nome:
            return nome
        print("   O nome não pode ser vazio.")


# ---------------------------------------------------------------------------
# Carregamento de arquivos
# ---------------------------------------------------------------------------

def _carregar_fixations(path) -> pd.DataFrame:
    """Carrega fixations.csv do Pupil Labs e valida colunas mínimas."""
    df = pd.read_csv(path)
    colunas_necessarias = {"id", "start_frame_index"}
    faltando = colunas_necessarias - set(df.columns)
    if faltando:
        raise ValueError(
            f"fixations.csv não possui as colunas: {faltando}\n"
            f"Colunas encontradas: {list(df.columns)}"
        )
    return df


def _carregar_motec(path) -> pd.DataFrame:
    """
    Carrega o CSV de telemetria do MoTeC.

    O formato padrão de exportação do MoTeC possui 14 linhas de cabeçalho
    descartáveis antes da linha de nomes de coluna, usa separador
    auto-detectável (ponto-e-vírgula no iRacing) e encoding latin-1.
    Usa os mesmos parâmetros do individual.py para garantir consistência.
    """
    df = pd.read_csv(
        path,
        skiprows=14,
        sep=None,
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    df.columns = [str(c).strip() for c in df.columns]

    if not any("car pos norm" in c.lower() for c in df.columns):
        raise ValueError(
            f"Coluna 'Car Pos Norm' não encontrada em {path}.\n"
            f"Colunas disponíveis: {list(df.columns)[:10]} ...\n"
            "Verifique se o arquivo foi exportado corretamente pelo MoTeC."
        )
    return df


def _carregar_world_timestamps(path) -> pd.DataFrame:
    """Carrega world_timestamps.csv do Pupil Labs (frame index → timestamp)."""
    df = pd.read_csv(path)
    return df


# ---------------------------------------------------------------------------
# Lógica de dados
# ---------------------------------------------------------------------------

def _buscar_frame_fixacao(df_fix: pd.DataFrame, fixation_id: int) -> int:
    """
    Localiza a fixação pelo ID e retorna seu start_frame_index.
    Lança ValueError se o ID não existir no CSV.
    """
    linha = df_fix[df_fix["id"] == fixation_id]
    if linha.empty:
        raise ValueError(
            f"ID de fixação {fixation_id} não encontrado em fixations.csv.\n"
            f"IDs disponíveis: {df_fix['id'].min()} – {df_fix['id'].max()}"
        )
    return int(linha["start_frame_index"].iloc[0])


def _detectar_quedas_carpnorm(df_motec: pd.DataFrame) -> list[int]:
    """
    Encontra os índices de linha onde Car Pos Norm cai abruptamente
    (diferença < -0.5), sinalizando a passagem pela linha de chegada.

    Regra de negócio MoTeC (largada parada do grid):
        índice 0 → largada (início da Volta 0)
        índice 1 → fim da Volta 0 / início da Volta 1
        índice V → início da Volta V  (para V ≥ 1)
        índice V+1 → fim da Volta V
    """
    col_cpn = clean_col(df_motec, ["Car Pos Norm", "car pos norm", "CarPosNorm"])
    if col_cpn is None:
        raise ValueError("Não foi possível localizar a coluna 'Car Pos Norm' no MoTeC.")

    # diff() retorna NaN na primeira linha; valores negativos abaixo de -0.5
    # indicam uma queda brusca de ~1.0 para ~0.0 (cruzamento da linha)
    diff_series = col_cpn.diff()
    indices = df_motec.index[diff_series < -0.1].tolist()

    if len(indices) < 2:
        raise ValueError(
            f"Apenas {len(indices)} queda(s) detectada(s) em Car Pos Norm. "
            "São necessárias pelo menos 2 para definir uma volta completa."
        )
    return indices


def _extrair_tempo_motec(df_motec: pd.DataFrame, indice: int) -> float:
    """
    Retorna o tempo (em segundos) da linha `indice` no DataFrame do MoTeC.
    Busca a coluna de tempo por nomes comuns do MoTeC ("Time", "Lap Time", etc.).
    """
    col_t = clean_col(df_motec, ["Time", "Lap Time", "Session Time", "timestamp"])
    if col_t is None:
        # Fallback: usa o próprio índice de linha como proxy de tempo
        print(
            "   AVISO: coluna de tempo não encontrada no MoTeC. "
            "Usando índice de linha como substituto."
        )
        return float(indice)
    return tradutor_de_tempos(col_t.iloc[indice])


# ---------------------------------------------------------------------------
# Etapa 1 — Ponto de Sync do Pupil Labs
# ---------------------------------------------------------------------------

def etapa1_sync_pupil(df_fix: pd.DataFrame) -> int:
    """
    Pergunta ao operador o ID da fixação no momento da largada e
    retorna o start_frame_index correspondente.
    """
    print("\n" + "=" * 60)
    print("ETAPA 1 — Ponto de Sincronização Inicial (Pupil Labs)")
    print("=" * 60)
    print(
        "Identifique no Pupil Player o momento exato em que o piloto\n"
        "ultrapassa a linha de largada vindo do grid parado.\n"
        "Anote o ID da fixação ativa nesse instante."
    )

    while True:
        fixation_id = _input_int(
            "\nDigite o ID da fixação da pupila no momento em que o piloto\n"
            "ultrapassa a linha de largada vindo do grid parado: "
        )
        try:
            frame_sync = _buscar_frame_fixacao(df_fix, fixation_id)
            print(f"\n   ✓ Fixação {fixation_id} encontrada.")
            print(f"   start_frame_index (âncora Pupil): {frame_sync}")
            return frame_sync
        except ValueError as e:
            print(f"\n   Erro: {e}")
            print("   Tente novamente.")


# ---------------------------------------------------------------------------
# Etapa 2 — Mapeamento de Voltas (MoTeC)
# ---------------------------------------------------------------------------

def etapa2_sync_motec(
    df_motec: pd.DataFrame,
) -> tuple[list[int], float]:
    """
    Detecta os inícios de cada volta via Car Pos Norm e retorna:
        - indices_quedas: lista de índices de linha em cada queda brusca
        - t_sync_motec_s: tempo (s) no MoTeC correspondente ao índice 0
                          (ponto de largada)
    """
    print("\n" + "=" * 60)
    print("ETAPA 2 — Mapeamento de Voltas (MoTeC)")
    print("=" * 60)

    # Detecta quedas de Car Pos Norm (cada queda = cruzamento da linha)
    indices_quedas = _detectar_quedas_carpnorm(df_motec)
    n_voltas = len(indices_quedas) - 1  # voltas completas (excluindo a Volta 0)

    print(f"\n   Quedas detectadas em Car Pos Norm: {len(indices_quedas)}")
    print(f"   → Ponto de largada (índice 0): linha {indices_quedas[0] + 16}")
    print(f"   → Voltas completas detectadas: {n_voltas}")

    # Tempo no MoTeC correspondente ao ponto de largada
    t_sync_motec_s = _extrair_tempo_motec(df_motec, indices_quedas[0])
    print(f"   → Sync Point MoTeC (t na linha {indices_quedas[0] + 16}): {t_sync_motec_s:.4f} s")

    return indices_quedas, t_sync_motec_s


# ---------------------------------------------------------------------------
# Etapa 3 — Sincronização Base
# ---------------------------------------------------------------------------

def etapa3_alinhar(
    frame_sync: int,
    t_sync_motec_s: float,
    path_world_timestamps,
) -> float:
    """
    Carrega world_timestamps.csv, extrai o timestamp Pupil no frame âncora
    e calcula o offset entre os dois eixos de tempo.

    Retorna o offset em segundos (MoTeC_t − Pupil_t no ponto de sync).
    """
    print("\n" + "=" * 60)
    print("ETAPA 3 — Sincronização Base")
    print("=" * 60)

    # world_timestamps.csv mapeia frame_index → timestamp (µs ou s)
    df_wt = _carregar_world_timestamps(path_world_timestamps)

    # Busca a coluna de timestamp (Pupil exporta como "timestamp" ou "timestamps")
    col_ts = next(
        (c for c in df_wt.columns if "timestamp" in c.lower()),
        None,
    )
    if col_ts is None:
        print(
            "   AVISO: coluna 'timestamp' não encontrada em world_timestamps.csv.\n"
            "   Verificação de offset pulada — âncoras salvas nas etapas anteriores."
        )
        return 0.0

    # O índice da linha corresponde ao frame_index (padrão do Pupil Labs)
    if frame_sync >= len(df_wt):
        print(
            f"   AVISO: frame_sync={frame_sync} excede o total de frames "
            f"({len(df_wt)}) em world_timestamps.csv. Verificação pulada."
        )
        return 0.0

    ts_raw = force_float(df_wt[col_ts].iloc[frame_sync])

    # Auto-detecta escala: timestamps do Pupil costumam estar em µs (> 1e12)
    if ts_raw > 1e12:
        t_pupil_s = ts_raw / 1e6   # microssegundos → segundos
        escala = "microseconds"
    elif ts_raw > 1e9:
        t_pupil_s = ts_raw / 1e3   # milissegundos → segundos
        escala = "milliseconds"
    else:
        t_pupil_s = ts_raw         # já em segundos
        escala = "seconds"

    offset_s = t_sync_motec_s - t_pupil_s

    print(f"\n   Âncora Pupil Labs:")
    print(f"      frame_sync          = {frame_sync}")
    print(f"      timestamp bruto     = {ts_raw} ({escala})")
    print(f"      t_pupil_s           = {t_pupil_s:.4f} s")
    print(f"\n   Âncora MoTeC:")
    print(f"      t_sync_motec_s      = {t_sync_motec_s:.4f} s")
    print(f"\n   Offset calculado (MoTeC − Pupil): {offset_s:.4f} s")

    if abs(offset_s) < 1.0:
        print("   ✓ Alinhamento coerente (offset < 1 s).")
    else:
        print(
            f"   ⚠ Offset de {offset_s:.2f} s — verifique se os âncoras estão corretos."
        )

    return offset_s


# ---------------------------------------------------------------------------
# Etapa 4 — Melhor Volta (Ideal Lap)
# ---------------------------------------------------------------------------

def etapa4_melhor_volta(
    indices_quedas: list[int],
    t_sync_motec_s: float,
    df_motec: pd.DataFrame,
    df_fix: pd.DataFrame,
    sessao_id: str,
    piloto_id: str,
) -> None:
    """
    Permite ao operador escolher a melhor volta e registra no banco:
        - Volta com eh_volta_ouro=True, t_ini_sync_s, t_fim_sync_s
        - frame_ini_pupil e frame_fim_pupil da volta ouro
    """
    print("\n" + "=" * 60)
    print("ETAPA 4 — Preparação da Melhor Volta (Ideal Lap)")
    print("=" * 60)

    # Número de voltas completas disponíveis (Volta 0 é a saída do grid)
    n_voltas = len(indices_quedas) - 1
    voltas_disponiveis = list(range(1, n_voltas + 1))

    print(f"\n   Voltas detectadas: {', '.join(str(v) for v in voltas_disponiveis)}")
    print("   (Volta 0 = saída do grid — não disponível como volta de referência)")

    # --- Seleciona a melhor volta ---
    while True:
        V = _input_int("\nQual dessas foi a melhor volta do piloto? ")
        if V in voltas_disponiveis:
            break
        print(f"   Volta {V} inválida. Escolha entre: {voltas_disponiveis}")

    # Índices de linha no MoTeC para início e fim da volta V
    # Regra: Volta V começa no índice V e termina no índice V+1.
    # Para a última volta disponível, V+1 está fora da lista — usa o último
    # sample do df_motec (que já foi truncado até indices_quedas[-1]+1).
    idx_ini = indices_quedas[V]
    if V + 1 < len(indices_quedas):
        idx_fim = indices_quedas[V + 1]
    else:
        idx_fim = df_motec.index[-1]

    # Tempos sincronizados (relativo ao ponto de largada)
    t_ini_s = _extrair_tempo_motec(df_motec, idx_ini) - t_sync_motec_s
    t_fim_s = _extrair_tempo_motec(df_motec, idx_fim) - t_sync_motec_s
    duracao_s = t_fim_s - t_ini_s

    print(f"\n   Volta {V} selecionada:")
    print(f"      Índice de início no MoTeC : linha {idx_ini + 16}")
    print(f"      Índice de fim no MoTeC    : linha {idx_fim + 16}")
    print(f"      t_ini_sync_s              : {t_ini_s:.4f} s")
    print(f"      t_fim_sync_s              : {t_fim_s:.4f} s")
    print(f"      Duração                   : {duracao_s:.4f} s")

    # --- Fixação no início da melhor volta ---
    print(
        "\nAgora identifique no Pupil Player o frame exato do\n"
        "INÍCIO da Volta " + str(V) + " e anote o ID da fixação ativa."
    )
    while True:
        id_ini = _input_int("Digite o ID da fixação correspondente ao INÍCIO dessa melhor volta: ")
        try:
            frame_ini = _buscar_frame_fixacao(df_fix, id_ini)
            print(f"   ✓ start_frame_index (início da volta): {frame_ini}")
            break
        except ValueError as e:
            print(f"   Erro: {e}")

    # --- Fixação no fim da melhor volta ---
    print(
        "\nAgora identifique o frame exato do\n"
        "FINAL da Volta " + str(V) + " e anote o ID da fixação ativa."
    )
    while True:
        id_fim = _input_int("Digite o ID da fixação correspondente ao FINAL dessa melhor volta: ")
        try:
            frame_fim = _buscar_frame_fixacao(df_fix, id_fim)
            print(f"   ✓ start_frame_index (fim da volta): {frame_fim}")
            break
        except ValueError as e:
            print(f"   Erro: {e}")

    # --- Persiste no banco ---
    # volta_id é lido dentro do bloco para evitar acesso a instância desvinculada da sessão
    with SessionLocal() as db:
        with db.begin():
            volta = upsert_volta(
                db=db,
                sessao_id=sessao_id,
                piloto_id=piloto_id,
                numero_volta=V,
                t_ini=t_ini_s,
                t_fim=t_fim_s,
                duracao=duracao_s,
                eh_ouro=True,
                frame_ini_pupil=frame_ini,
                frame_fim_pupil=frame_fim,
            )
            volta_id = volta.id  # captura antes de a sessão fechar

    print(f"\n   ✓ Volta {V} salva no banco de dados como VOLTA OURO.")
    print(f"      Volta ID             : {volta_id}")
    print(f"      frame_ini_pupil      : {frame_ini}")
    print(f"      frame_fim_pupil      : {frame_fim}")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def executar() -> None:
    """
    Orquestra as 4 etapas de sincronização para um piloto/sessão escolhido
    pelo operador via terminal, persistindo todos os dados âncora no banco.
    """
    print("\n" + "=" * 60)
    print("SINCRONIZAÇÃO MoTeC ↔ Pupil Labs")
    print("=" * 60)
    print(
        "Este script estabelece os pontos-âncora entre a telemetria\n"
        "MoTeC e o rastreamento ocular Pupil Labs.\n"
        "Execute-o UMA VEZ por piloto/sessão antes dos demais scripts."
    )

    # --- Seleção de piloto e sessão ---
    print("\n--- Configuração ---")
    nome_piloto = _selecionar_piloto()
    nome_sessao = _selecionar_sessao()

    caminhos = PILOTOS[nome_piloto]
    path_fix = caminhos["fixations"]
    path_motec = caminhos["motec"]
    path_wt = path_fix.parent / "world_timestamps.csv"

    print(f"\n   Piloto  : {nome_piloto}")
    print(f"   Sessão  : {nome_sessao}")
    print(f"   MoTeC   : {path_motec}")
    print(f"   Fixações: {path_fix}")

    # --- Carregamento dos arquivos ---
    print("\nCarregando arquivos...")
    df_fix = _carregar_fixations(path_fix)
    df_motec = _carregar_motec(path_motec)
    print(f"   fixations.csv  : {len(df_fix)} fixações")
    print(f"   MoTeC CSV      : {len(df_motec)} linhas")

    # --- Garante piloto e sessão no banco ---
    with SessionLocal() as db:
        with db.begin():
            piloto = get_or_create_piloto(db, nome_piloto)
            sessao = get_or_create_sessao(db, nome_sessao)
            sessao_id = sessao.id
            piloto_id = piloto.id

    # --- Verifica se já está sincronizado ---
    with SessionLocal() as db:
        ps = db.query(ParametrosSync).filter_by(
            sessao_id=sessao_id, piloto_id=piloto_id
        ).first()
        volta_ouro = db.query(Volta).filter_by(
            sessao_id=sessao_id, piloto_id=piloto_id, eh_volta_ouro=True
        ).first()

    ja_sincronizado = (
        ps is not None
        and ps.frame_sync is not None
        and ps.t_sync_motec_s is not None
        and volta_ouro is not None
    )

    if ja_sincronizado:
        print(f"\n   ✓ {nome_piloto} já está sincronizado na sessão '{nome_sessao}'.")
        print(f"     frame_sync     : {ps.frame_sync}")
        print(f"     t_sync_motec_s : {ps.t_sync_motec_s:.4f} s")
        print(f"     Volta de ouro  : volta {volta_ouro.numero_volta}")
        resp = input("\n   Deseja refazer a sincronização? [s/N]: ").strip().lower()
        if resp != "s":
            print("\nSincronização pulada. Dados existentes mantidos.")
            return

    # ==========================================================
    # Etapa 1 — Ponto de sync do Pupil Labs
    # ==========================================================
    frame_sync = etapa1_sync_pupil(df_fix)

    # Persiste frame_sync no banco (t_sync_motec_s ainda não disponível)
    with SessionLocal() as db:
        with db.begin():
            upsert_parametros_sync(
                db=db,
                sessao_id=sessao_id,
                piloto_id=piloto_id,
                frame_sync=frame_sync,
            )
    print("   ✓ frame_sync salvo em ParametrosSync.")

    # ==========================================================
    # Etapa 2 — Mapeamento de voltas (MoTeC)
    # ==========================================================
    indices_quedas, t_sync_motec_s = etapa2_sync_motec(df_motec)

    # Descarta a volta de desaceleração/retorno ao box — tudo após a última queda é lixo
    df_motec = df_motec.iloc[:indices_quedas[-1] + 1]

    # Persiste t_sync_motec_s no banco
    with SessionLocal() as db:
        with db.begin():
            upsert_parametros_sync(
                db=db,
                sessao_id=sessao_id,
                piloto_id=piloto_id,
                t_sync_motec_s=t_sync_motec_s,
            )
    print("   ✓ t_sync_motec_s (Sync Point MoTeC) salvo em ParametrosSync.")

    # ==========================================================
    # Etapa 3 — Sincronização base (cálculo de offset)
    # ==========================================================
    if path_wt.exists():
        offset_s = etapa3_alinhar(frame_sync, t_sync_motec_s, path_wt)
    else:
        print(
            f"\n   AVISO: world_timestamps.csv não encontrado em {path_wt}.\n"
            "   Etapa 3 pulada — âncoras já registrados nas etapas 1 e 2."
        )
        offset_s = None

    # Persiste a escala de timestamps detectada (quando disponível)
    if offset_s is not None and path_wt.exists():
        df_wt = _carregar_world_timestamps(path_wt)
        col_ts = next((c for c in df_wt.columns if "timestamp" in c.lower()), None)
        if col_ts and frame_sync < len(df_wt):
            ts_raw = force_float(df_wt[col_ts].iloc[frame_sync])
            if ts_raw > 1e12:
                escala = "microseconds"
            elif ts_raw > 1e9:
                escala = "milliseconds"
            else:
                escala = "seconds"
            with SessionLocal() as db:
                with db.begin():
                    upsert_parametros_sync(
                        db=db,
                        sessao_id=sessao_id,
                        piloto_id=piloto_id,
                        escala_timestamps=escala,
                    )
            print(f"   ✓ escala_timestamps='{escala}' salva em ParametrosSync.")

    # ==========================================================
    # Etapa 4 — Melhor volta (Ideal Lap)
    # ==========================================================
    etapa4_melhor_volta(
        indices_quedas=indices_quedas,
        t_sync_motec_s=t_sync_motec_s,
        df_motec=df_motec,
        df_fix=df_fix,
        sessao_id=sessao_id,
        piloto_id=piloto_id,
    )

    # --- Resumo final ---
    print("\n" + "=" * 60)
    print("SINCRONIZAÇÃO CONCLUÍDA")
    print("=" * 60)
    print(f"   Piloto            : {nome_piloto}")
    print(f"   Sessão            : {nome_sessao}")
    print(f"   frame_sync        : {frame_sync}")
    print(f"   t_sync_motec_s    : {t_sync_motec_s:.4f} s")
    if offset_s is not None:
        print(f"   offset calculado  : {offset_s:.4f} s")
    print(
        "\nOs dados âncora estão salvos no banco e podem ser usados\n"
        "pelos scripts individual.py, media_pilotos.py e anomalias.py."
    )
