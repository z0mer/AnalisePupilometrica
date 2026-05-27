"""
backend/processamento/pipeline.py
==================================
Funções puras de processamento — sem leitura de disco, sem plt.show(), sem input().

Fluxo principal:
    1. carregar_pupil / carregar_motec / carregar_fixacoes / carregar_blinks
    2. processar_volta_ouro  → (df_ouro, motec_sinc, t_sync_p, escala)
    3. calcular_tracado_ideal → (df_ideal, png_bytes)
    4. processar_anomalias_piloto → (anomalias_lista, {filename: png_bytes})
    5. processar_tr_piloto   → (registros_csv, pdf_bytes | None, csv_bytes)
"""
from __future__ import annotations

import io
from typing import Any

import matplotlib

matplotlib.use("Agg")  # backend sem display

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.processamento.utils import (
    CORES_TIPO,
    DTW_PASSO,
    DTW_TAMANHO_JANELA,
    DURACAO_MINIMA_PCT,
    JANELA_POS_ANOMALIA_SEG,
    JANELA_REACAO_SEG,
    JANELA_SUAVIZACAO_DERIV,
    LABELS_TIPO,
    LIMIAR_CHICOTE_IDEAL_GRAUS,
    LIMIAR_CHICOTE_PILOTO_GRAUS,
    LIMIAR_DESVIO_RETA_GRAUS,
    LIMIAR_OVERSHOOT_GRAUS,
    LIMIAR_DESVIO_RETA_PICO_GRAUS,
    LIMIAR_DERIVADA,
    LIMIAR_DERIVADA_MEDIA,
    LIMIAR_DTW_SCORE,
    LIMIAR_FIXACAO_CURTA_MS,
    LIMIAR_FIXACAO_LONGA_MS,
    LIMIAR_ONSET_PEDAL_PCT,
    LIMIAR_ONSET_PUPILA_MM,
    LIMIAR_ONSET_STEERING_GRAUS,
    LIMIAR_PICO_DILATACAO_MM,
    LIMIAR_RETA_GRAUS,
    LIMIAR_SINAL_INVERTIDO_GRAUS,
    N_SETORES,
    NIVEL_PILOTOS,
    TOLERANCIA_GAP_PCT,
    atirar_com_sniper,
    clean_col,
    fig_para_bytes,
    force_float,
    limpa_diametro,
)

# ---------------------------------------------------------------------------
# Carregamento de dados (bytes → DataFrame)
# ---------------------------------------------------------------------------


def carregar_pupil(data: bytes) -> pd.DataFrame:
    """
    Lê pupil_positions.csv a partir de bytes.
    Aplica filtragem por método de detecção (Pye3D > 2D C++).
    Retorna DataFrame com colunas originais mais 'c_t', 'c_wi', 'c_d'
    preenchidas nas colunas corretas detectadas.
    """
    df = pd.read_csv(
        io.BytesIO(data), sep=None, engine="python", on_bad_lines="skip"
    )
    df.columns = [str(c).strip() for c in df.columns]

    # Filtrar por método de detecção
    c_p_m = [c for c in df.columns if "method" in c.lower()]
    if c_p_m:
        count_2d = df[c_p_m[0]].astype(str).str.contains(
            r"2d c\+\+", regex=True, case=False
        ).sum()
        count_3d = df[c_p_m[0]].astype(str).str.contains(
            "pye3d", regex=True, case=False
        ).sum()
        if count_3d > count_2d:
            df = df[
                df[c_p_m[0]].astype(str).str.contains(
                    "pye3d", regex=True, case=False, na=False
                )
            ]
            print("   Metodo Pye3D detectado e filtrado.")
        else:
            df = df[
                df[c_p_m[0]].astype(str).str.contains(
                    r"2d c\+\+", regex=True, case=False, na=False
                )
            ]
            print("   Metodo 2D C++ detectado e filtrado.")

    return df.reset_index(drop=True)


def carregar_motec(data: bytes) -> pd.DataFrame:
    """
    Lê o CSV do MoTeC a partir de bytes (pula as 14 linhas de cabeçalho).
    """
    df = pd.read_csv(
        io.BytesIO(data),
        skiprows=14,
        sep=None,
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def carregar_fixacoes(
    data: bytes, t_sync_p: float, escala: float
) -> pd.DataFrame:
    """
    Lê fixations.csv a partir de bytes.
    Sincroniza os timestamps usando t_sync_p (timestamp pupila no Marco Zero) e escala.
    Retorna DataFrame com colunas: t_sync, duration_ms, norm_x, norm_y, confidence, dispersion.
    """
    cols_vazias = ["t_sync", "duration_ms", "norm_x", "norm_y", "confidence", "dispersion"]
    try:
        df = pd.read_csv(
            io.BytesIO(data), sep=None, engine="python", on_bad_lines="skip"
        )
        df.columns = [str(c).strip() for c in df.columns]

        col_ts = next(
            (c for c in df.columns if "start_timestamp" in c.lower()),
            next((c for c in df.columns if "timestamp" in c.lower()), None),
        )
        if col_ts is None:
            return pd.DataFrame(columns=cols_vazias)

        col_dur = next((c for c in df.columns if "duration" in c.lower()), None)
        col_x = next((c for c in df.columns if "norm_pos_x" in c.lower()), None)
        col_y = next((c for c in df.columns if "norm_pos_y" in c.lower()), None)
        col_conf = next((c for c in df.columns if "confidence" in c.lower()), None)
        col_disp = next((c for c in df.columns if "dispersion" in c.lower()), None)

        ts_raw = pd.to_numeric(
            df[col_ts].astype(str).str.replace(",", ".", regex=False), errors="coerce"
        )
        out = pd.DataFrame()
        out["t_sync"] = (ts_raw - t_sync_p) / escala

        if col_dur is not None:
            dur_raw = pd.to_numeric(
                df[col_dur].astype(str).str.replace(",", ".", regex=False), errors="coerce"
            )
            med = dur_raw.dropna().median()
            out["duration_ms"] = dur_raw if (not np.isnan(med) and med > 10) else dur_raw * 1000.0
        else:
            out["duration_ms"] = np.nan

        out["norm_x"] = pd.to_numeric(df[col_x], errors="coerce") if col_x else np.nan
        out["norm_y"] = pd.to_numeric(df[col_y], errors="coerce") if col_y else np.nan
        out["confidence"] = pd.to_numeric(df[col_conf], errors="coerce") if col_conf else np.nan
        out["dispersion"] = pd.to_numeric(df[col_disp], errors="coerce") if col_disp else np.nan

        return out.dropna(subset=["t_sync"]).reset_index(drop=True)
    except Exception as exc:
        print(f"  Aviso fixacoes: {exc}")
        return pd.DataFrame(columns=cols_vazias)


def carregar_blinks(
    data: bytes, t_sync_p: float, escala: float
) -> pd.DataFrame:
    """
    Lê blinks.csv a partir de bytes.
    Sincroniza os timestamps e retorna DataFrame com: t_ini, t_fim, duracao_s, confidence.
    """
    cols_vazias = ["t_ini", "t_fim", "duracao_s", "confidence"]
    try:
        df = pd.read_csv(
            io.BytesIO(data), sep=None, engine="python", on_bad_lines="skip"
        )
        df.columns = [str(c).strip() for c in df.columns]

        col_ini = next((c for c in df.columns if "start_timestamp" in c.lower()), None)
        col_fim = next((c for c in df.columns if "end_timestamp" in c.lower()), None)
        col_dur = next((c for c in df.columns if "duration" in c.lower()), None)
        col_conf = next((c for c in df.columns if "confidence" in c.lower()), None)

        if col_ini is None:
            return pd.DataFrame(columns=cols_vazias)

        ts_ini = pd.to_numeric(
            df[col_ini].astype(str).str.replace(",", ".", regex=False), errors="coerce"
        )
        out = pd.DataFrame()
        out["t_ini"] = (ts_ini - t_sync_p) / escala

        if col_fim is not None:
            ts_fim = pd.to_numeric(
                df[col_fim].astype(str).str.replace(",", ".", regex=False), errors="coerce"
            )
            out["t_fim"] = (ts_fim - t_sync_p) / escala
        elif col_dur is not None:
            dur_raw = pd.to_numeric(
                df[col_dur].astype(str).str.replace(",", ".", regex=False), errors="coerce"
            )
            med = dur_raw.dropna().median()
            dur_s = dur_raw / 1000.0 if (not np.isnan(med) and med > 10) else dur_raw
            out["t_fim"] = out["t_ini"] + dur_s
        else:
            out["t_fim"] = out["t_ini"] + 0.3

        out["duracao_s"] = out["t_fim"] - out["t_ini"]
        out["confidence"] = (
            pd.to_numeric(df[col_conf], errors="coerce") if col_conf else np.nan
        )
        return out.dropna(subset=["t_ini"]).reset_index(drop=True)
    except Exception as exc:
        print(f"  Aviso blinks: {exc}")
        return pd.DataFrame(columns=cols_vazias)


# ---------------------------------------------------------------------------
# Processamento da Volta de Ouro
# ---------------------------------------------------------------------------


def processar_volta_ouro(
    pupil_df: pd.DataFrame,
    motec_df: pd.DataFrame,
    frame_sync: int,
    t_sync_motec_s: float,
    frame_ini_pupil: int,
    frame_fim_pupil: int,
    nome: str,
) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    """
    Extrai a volta de ouro a partir dos dados brutos da pupila e do MoTeC.

    Parâmetros
    ----------
    pupil_df          : DataFrame bruto (já filtrado por método)
    motec_df          : DataFrame bruto do MoTeC (skiprows=14)
    frame_sync        : frame do Marco Zero no Pupil Player
    t_sync_motec_s    : tempo correspondente ao Marco Zero no MoTeC (segundos)
    frame_ini_pupil   : frame de início da volta de ouro
    frame_fim_pupil   : frame de fim da volta de ouro
    nome              : nome do piloto (usado em prints)

    Retorna
    -------
    df_ouro    : DataFrame com colunas tempo_sync, diam_suav, [acel, freio, volante]
    motec_sinc : DataFrame com colunas t_sync, steer, acel, freio, lap_count, [vel]
    t_sync_p   : timestamp bruto do Marco Zero no arquivo da pupila
    escala     : fator de escala dos timestamps da pupila (1, 1000 ou 1_000_000)
    """
    # Identificar colunas da pupila
    c_p_t_list = [c for c in pupil_df.columns if "timestamp" in c.lower()]
    if not c_p_t_list:
        raise ValueError(f"[{nome}] Coluna 'timestamp' nao encontrada na pupila.")
    c_p_t = c_p_t_list[0]

    c_p_wi_list = [c for c in pupil_df.columns if "world_index" in c.lower()]
    if not c_p_wi_list:
        raise ValueError(f"[{nome}] Coluna 'world_index' nao encontrada na pupila.")
    c_p_wi = c_p_wi_list[0]

    c_p_d_list = [c for c in pupil_df.columns if "diameter_3d" in c.lower()]
    if not c_p_d_list or pupil_df[c_p_d_list[0]].isna().all():
        c_p_d_list = [c for c in pupil_df.columns if "diameter" in c.lower()]
    if not c_p_d_list:
        raise ValueError(f"[{nome}] Coluna de diametro nao encontrada na pupila.")
    c_p_d = c_p_d_list[0]
    print(f"   [{nome}] Usando diametro: '{c_p_d}'")

    # Marco Zero: localizar timestamp do frame_sync
    t_sync_p = atirar_com_sniper(frame_sync, pupil_df, c_p_wi, c_p_t)
    print(f"   [{nome}] Timestamp bruto Marco Zero: {t_sync_p}")

    # Converter e limpar
    pupil_df = pupil_df.copy()
    pupil_df[c_p_t] = pupil_df[c_p_t].apply(force_float)
    pupil_df[c_p_d] = pupil_df[c_p_d].apply(limpa_diametro)
    pupil_df = pupil_df.dropna(subset=[c_p_t, c_p_d])

    # Detectar escala de timestamps
    t_mestre_raw = pupil_df[c_p_t].values - t_sync_p
    mediana_abs = np.nanmedian(np.abs(t_mestre_raw))
    if mediana_abs > 100_000:
        escala = 1_000_000.0
        print(f"   [{nome}] Timestamps em microssegundos -> segundos")
    elif mediana_abs > 500:
        escala = 1_000.0
        print(f"   [{nome}] Timestamps em milissegundos -> segundos")
    else:
        escala = 1.0
        print(f"   [{nome}] Timestamps ja em segundos")

    t_mestre = t_mestre_raw / escala
    df_master = pd.DataFrame({"tempo_sync": t_mestre})
    df_master["diam_suav"] = (
        pupil_df[c_p_d].rolling(window=5, center=True).mean().values
    )

    # Processar MoTeC
    print(f"   [{nome}] Processando MoTeC...")
    t_clean = clean_col(motec_df, ["Time", "tempo"])
    f_clean = clean_col(motec_df, ["Brake Pos", "freio", "brk"])
    a_clean = clean_col(motec_df, ["Throttle Pos", "acel", "thr"])
    s_clean = clean_col(motec_df, ["Steering Angle", "volante", "whl"])
    lap_clean = clean_col(motec_df, ["Session Lap Count", "lap", "volta"])
    vel_clean = clean_col(motec_df, ["Ground Speed", "GPS Speed", "Vehicle Speed", "Speed"])

    motec_df = motec_df.copy()
    motec_df["t_clean"] = t_clean
    motec_df["f_clean"] = f_clean
    motec_df["a_clean"] = a_clean
    motec_df["s_clean"] = s_clean
    motec_df["lap_clean"] = lap_clean
    motec_df["vel_clean"] = (
        (vel_clean / 3.6) if vel_clean is not None else pd.Series(np.nan, index=motec_df.index)
    )
    motec_df = motec_df.dropna(subset=["t_clean"])

    t_m_orig = motec_df["t_clean"].values - t_sync_motec_s

    # DataFrame motec_sinc para uso na análise de anomalias
    motec_sinc = pd.DataFrame({
        "t_sync":    t_m_orig,
        "steer":     motec_df["s_clean"].values if s_clean is not None else np.nan,
        "acel":      motec_df["a_clean"].values if a_clean is not None else np.nan,
        "freio":     motec_df["f_clean"].values if f_clean is not None else np.nan,
        "lap_count": motec_df["lap_clean"].values if lap_clean is not None else np.nan,
        "vel":       motec_df["vel_clean"].values,
    })

    # Interpolar canais MoTeC no eixo temporal da pupila
    for col, source in [("freio", "f_clean"), ("acel", "a_clean"), ("volante", "s_clean")]:
        if source in motec_df.columns and motec_df[source].notna().any():
            vals = motec_df[source].values.astype(float)
            df_master[col] = np.interp(t_mestre, t_m_orig, vals)
        else:
            print(f"   [{nome}] '{col}' nao disponivel, pulando.")

    # Recortar janela da volta de ouro
    t_ini_p = atirar_com_sniper(frame_ini_pupil, pupil_df, c_p_wi, c_p_t)
    t_fim_p = atirar_com_sniper(frame_fim_pupil, pupil_df, c_p_wi, c_p_t)
    t_ouro_ini = (t_ini_p - t_sync_p) / escala
    t_ouro_fim = (t_fim_p - t_sync_p) / escala
    print(f"   [{nome}] Janela volta de ouro: {t_ouro_ini:.2f}s -> {t_ouro_fim:.2f}s")

    df_ouro = df_master[
        (df_master["tempo_sync"] >= t_ouro_ini) &
        (df_master["tempo_sync"] <= t_ouro_fim)
    ].copy()

    if df_ouro.empty:
        raise ValueError(
            f"[{nome}] Volta de ouro vazia! "
            f"df_master vai de {df_master['tempo_sync'].min():.2f} a "
            f"{df_master['tempo_sync'].max():.2f}s"
        )

    print(f"   [{nome}] Linhas na volta de ouro: {len(df_ouro)}")
    return df_ouro, motec_sinc, t_sync_p, escala


# ---------------------------------------------------------------------------
# Traçado Ideal (Script 2 equivalente)
# ---------------------------------------------------------------------------


def calcular_tracado_ideal(
    voltas: list[dict[str, Any]],
    n_pontos: int = 1000,
) -> tuple[pd.DataFrame, bytes]:
    """
    Calcula o traçado ideal a partir das voltas de ouro de vários pilotos.

    Parâmetros
    ----------
    voltas   : lista de dicts {"nome": str, "df_ouro": pd.DataFrame}
               df_ouro deve ter colunas: tempo_sync, diam_suav, [acel, freio, volante]
    n_pontos : resolução da normalização (padrão 1000)

    Retorna
    -------
    df_ideal  : DataFrame com colunas progresso_pct, steering_medio, steering_sigma,
                acel_medio, acel_sigma, freio_medio, freio_sigma, pupila_medio, pupila_sigma
    png_bytes : gráfico PNG em memória (bytes)
    """
    eixo_norm = np.linspace(0, 100, n_pontos)
    canais = ["diam_suav", "acel", "freio", "volante"]
    dados_norm: dict[str, list] = {c: [] for c in canais}

    for entrada in voltas:
        nome = entrada["nome"]
        df = entrada["df_ouro"]
        t = df["tempo_sync"].values
        t_pct = np.linspace(0, 100, len(t))
        for canal in canais:
            if canal in df.columns:
                vals_interp = np.interp(eixo_norm, t_pct, df[canal].values)
                dados_norm[canal].append(vals_interp)
                print(f"   {nome} / {canal}: {len(df[canal])} pts -> {n_pontos}")
            else:
                dados_norm[canal].append(np.full(n_pontos, np.nan))
                print(f"   {nome} / {canal}: ausente")

    medias: dict[str, np.ndarray] = {}
    sigmas: dict[str, np.ndarray] = {}
    for canal in canais:
        stack = np.array(dados_norm[canal])
        medias[canal] = np.nanmean(stack, axis=0)
        sigmas[canal] = np.nanstd(stack, axis=0)

    # Gráfico
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    fig.suptitle("Tracado Ideal — Media das Voltas de Ouro", fontsize=14, fontweight="bold")

    ax1.plot(eixo_norm, medias["diam_suav"], color="purple", linewidth=2)
    ax1.fill_between(
        eixo_norm,
        medias["diam_suav"] - sigmas["diam_suav"],
        medias["diam_suav"] + sigmas["diam_suav"],
        alpha=0.15, color="purple",
    )
    ax1.set_title("Dilatacao da Pupila")
    ax1.set_ylabel("Diametro (mm)")
    ax1.grid(True, alpha=0.3)

    ax2.plot(eixo_norm, medias["acel"], color="orange", linewidth=2, label="Acelerador")
    ax2.plot(eixo_norm, medias["freio"], color="green", linewidth=2, label="Freio")
    ax2.fill_between(
        eixo_norm,
        medias["acel"] - sigmas["acel"],
        medias["acel"] + sigmas["acel"],
        alpha=0.12, color="orange",
    )
    ax2.fill_between(
        eixo_norm,
        medias["freio"] - sigmas["freio"],
        medias["freio"] + sigmas["freio"],
        alpha=0.12, color="green",
    )
    ax2.set_title("Pedais")
    ax2.set_ylabel("%")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    ax3.plot(eixo_norm, medias["volante"], color="black", linewidth=2)
    ax3.fill_between(
        eixo_norm,
        medias["volante"] - sigmas["volante"],
        medias["volante"] + sigmas["volante"],
        alpha=0.15, color="black", label="±1σ",
    )
    ax3.set_title("Estercamento do Volante")
    ax3.set_ylabel("Graus")
    ax3.set_xlabel("Progresso da Volta (%)")
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    png_bytes = fig_para_bytes(fig, dpi=150)
    plt.close(fig)

    df_ideal = pd.DataFrame({
        "progresso_pct":  eixo_norm,
        "steering_medio": medias["volante"],
        "steering_sigma": sigmas["volante"],
        "acel_medio":     medias["acel"],
        "acel_sigma":     sigmas["acel"],
        "freio_medio":    medias["freio"],
        "freio_sigma":    sigmas["freio"],
        "pupila_medio":   medias["diam_suav"],
        "pupila_sigma":   sigmas["diam_suav"],
    })
    return df_ideal, png_bytes


# ---------------------------------------------------------------------------
# Detecção de anomalias (Script 3 equivalente)
# ---------------------------------------------------------------------------


def _interpolar_volta(valores: np.ndarray, n_pontos: int) -> np.ndarray:
    n = int(n_pontos)
    valores = valores.astype(float)
    mask_valido = ~np.isnan(valores)
    if mask_valido.sum() < 2:
        return np.full(n, np.nan)
    eixo_orig = np.linspace(0.0, 100.0, len(valores))
    eixo_novo = np.linspace(0.0, 100.0, n)
    return np.interp(eixo_novo, eixo_orig[mask_valido], valores[mask_valido])


def _agrupar_regioes(mascara_bool: np.ndarray, eixo: np.ndarray) -> list[tuple[int, int]]:
    regioes = []
    em_regiao = False
    inicio = 0
    for i, flag in enumerate(mascara_bool):
        if flag and not em_regiao:
            inicio = i
            em_regiao = True
        elif not flag and em_regiao:
            regioes.append((inicio, i - 1))
            em_regiao = False
    if em_regiao:
        regioes.append((inicio, len(mascara_bool) - 1))
    return regioes


def _mesclar_e_filtrar(
    regioes: list[tuple[int, int]], eixo: np.ndarray, tol: float, dur_min: float
) -> list[tuple[int, int]]:
    if not regioes:
        return []
    mescladas = [list(regioes[0])]
    for ini, fim in regioes[1:]:
        gap = eixo[ini] - eixo[mescladas[-1][1]]
        if gap <= tol:
            mescladas[-1][1] = fim
        else:
            mescladas.append([ini, fim])
    return [(i, f) for i, f in mescladas if eixo[f] - eixo[i] >= dur_min]


def _dtw_score_janelas(
    pilot_steer: np.ndarray,
    ideal_steer: np.ndarray,
    tamanho_janela: int = DTW_TAMANHO_JANELA,
    passo: int = DTW_PASSO,
) -> np.ndarray:
    """
    Calcula um score DTW por janela deslizante.
    Score baixo = forma similar ao ideal (pode ser só atraso de execução).
    Score alto = formato genuinamente diferente = anomalia real.
    """
    try:
        from fastdtw import fastdtw
        from scipy.spatial.distance import euclidean
        usar_dtw = True
    except ImportError:
        usar_dtw = False

    n = len(pilot_steer)
    scores = np.zeros(n)
    contagens = np.zeros(n)

    for start in range(0, n - tamanho_janela, passo):
        end = start + tamanho_janela
        p = pilot_steer[start:end]
        i = ideal_steer[start:end]
        if usar_dtw:
            dist, _ = fastdtw(p.reshape(-1, 1), i.reshape(-1, 1), dist=euclidean)
        else:
            dist = float(np.sum(np.abs(p - i)))  # fallback ponto-a-ponto
        dist_norm = dist / tamanho_janela
        scores[start:end] += dist_norm
        contagens[start:end] += 1

    contagens[contagens == 0] = 1
    return scores / contagens


def _centralizar_no_pico(
    regioes: list[tuple[int, int]],
    delta: np.ndarray,
    limiar_relativo: float = 0.2,
) -> list[tuple[int, int]]:
    """
    Re-ancora cada região detectada no pico do delta, expandindo enquanto
    o sinal superar 20% do pico. Corrige o offset entre onde o erro acontece
    e onde a máscara booleana dispara.
    """
    resultado = []
    n = len(delta)
    for ini, fim in regioes:
        segmento = np.abs(delta[ini : fim + 1])
        if len(segmento) == 0:
            continue
        peak_local = int(np.argmax(segmento))
        peak_idx = ini + peak_local
        limiar = segmento[peak_local] * limiar_relativo

        start = peak_idx
        while start > 0 and np.abs(delta[start - 1]) >= limiar:
            start -= 1
        end = peak_idx
        while end < n - 1 and np.abs(delta[end + 1]) >= limiar:
            end += 1
        resultado.append((start, end))
    return resultado


def _filtrar_por_pico(
    regioes: list[tuple[int, int]],
    sinal: np.ndarray,
    limiar_pico: float,
) -> list[tuple[int, int]]:
    """Mantém só regiões cujo pico absoluto supera limiar_pico."""
    return [
        (i, f) for i, f in regioes
        if len(sinal[i : f + 1]) > 0 and np.max(np.abs(sinal[i : f + 1])) >= limiar_pico
    ]


def _coalescer_recuperacoes(
    regioes_a: list[tuple[int, int]],
    regioes_bc: list[tuple[int, int]],
    eixo_pct: np.ndarray,
    janela_pct: float = 5.0,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Absorve cada região B/C que começa dentro de janela_pct% após o fim de
    uma região A. Evita que a recuperação frenética do erro seja classificada
    como anomalia separada.
    """
    regioes_a = [list(r) for r in regioes_a]
    absorvidas: set[int] = set()

    for a in regioes_a:
        fim_a_pct = eixo_pct[a[1]]
        for j, bc in enumerate(regioes_bc):
            if j in absorvidas:
                continue
            ini_bc_pct = eixo_pct[bc[0]]
            if 0.0 <= ini_bc_pct - fim_a_pct <= janela_pct:
                a[1] = max(a[1], bc[1])
                absorvidas.add(j)

    regioes_bc_restantes = [r for j, r in enumerate(regioes_bc) if j not in absorvidas]
    return [tuple(r) for r in regioes_a], regioes_bc_restantes


def detectar_anomalias_pura(
    piloto_steer: np.ndarray,
    steering_medio: np.ndarray,
    steering_sigma: np.ndarray,
    eixo_pct: np.ndarray,
) -> tuple[list[dict], np.ndarray]:
    """
    Detecta anomalias de volante comparando com o traçado ideal.
    Tipos: A (sinal invertido em curva OU chicote/salvamento na reta),
           B (desvio excessivo em reta com magnitude confirmada),
           C (correção brusca com derivada sustentada).
    Retorna (lista_anomalias, derivada).
    """
    delta = piloto_steer - steering_medio
    dtw_scores = _dtw_score_janelas(piloto_steer, steering_medio)

    eh_reta = np.abs(steering_medio) < LIMIAR_RETA_GRAUS
    eh_curva = ~eh_reta

    # --- Tipo A: sinal invertido em curva OU chicote/salvamento na reta ---
    sinal_oposto = np.sign(piloto_steer) != np.sign(steering_medio)
    magnitude_ok = (
        (np.abs(piloto_steer) > LIMIAR_SINAL_INVERTIDO_GRAUS) &
        (np.abs(steering_medio) > LIMIAR_SINAL_INVERTIDO_GRAUS)
    )
    mascara_chicote = (
        (np.abs(steering_medio) <= LIMIAR_CHICOTE_IDEAL_GRAUS) &
        (np.abs(piloto_steer) >= LIMIAR_CHICOTE_PILOTO_GRAUS)
    )
    mascara_overshoot = np.abs(delta) > LIMIAR_OVERSHOOT_GRAUS
    mascara_a = (
        (sinal_oposto & magnitude_ok & eh_curva)
        | mascara_chicote
        | mascara_overshoot
    ) & (dtw_scores > LIMIAR_DTW_SCORE)

    # --- Tipo B: desvio excessivo em reta ---
    mascara_b = eh_reta & (np.abs(piloto_steer) > LIMIAR_DESVIO_RETA_GRAUS)
    mascara_b = mascara_b & (dtw_scores > LIMIAR_DTW_SCORE)

    # --- Tipo C: correção brusca (derivada) ---
    steer_suav = (
        pd.Series(piloto_steer)
        .rolling(window=JANELA_SUAVIZACAO_DERIV, center=True, min_periods=1)
        .mean()
        .values
    )
    derivada = np.abs(np.gradient(steer_suav, eixo_pct))
    mascara_c = derivada > LIMIAR_DERIVADA

    # Agrupamento e filtragem
    regioes_a = _mesclar_e_filtrar(
        _agrupar_regioes(mascara_a, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    regioes_b = _mesclar_e_filtrar(
        _agrupar_regioes(mascara_b, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    # Tipo B: confirmar pico mínimo para eliminar micro-correções de reta
    regioes_b = _filtrar_por_pico(regioes_b, piloto_steer, LIMIAR_DESVIO_RETA_PICO_GRAUS)

    regioes_c = _mesclar_e_filtrar(
        _agrupar_regioes(mascara_c, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    # Tipo C: confirmar que a derivada média é sustentada (não apenas spike de ruído)
    regioes_c = [
        (i, f) for i, f in regioes_c
        if len(derivada[i : f + 1]) > 0 and np.mean(derivada[i : f + 1]) >= LIMIAR_DERIVADA_MEDIA
    ]

    # Centralizar cada região no pico real do delta
    regioes_a = _centralizar_no_pico(regioes_a, delta)
    regioes_b = _centralizar_no_pico(regioes_b, delta)
    regioes_c = _centralizar_no_pico(regioes_c, derivada)

    # Coalescência: absorver B/C de recuperação dentro do Tipo A precedente
    regioes_a, regioes_b = _coalescer_recuperacoes(regioes_a, regioes_b, eixo_pct)
    regioes_a, regioes_c = _coalescer_recuperacoes(regioes_a, regioes_c, eixo_pct)

    anomalias = []
    for tipo, regioes in [("A", regioes_a), ("B", regioes_b), ("C", regioes_c)]:
        for ini_idx, fim_idx in regioes:
            anomalias.append({
                "tipo":    tipo,
                "ini_idx": ini_idx,
                "fim_idx": fim_idx,
                "ini_pct": float(eixo_pct[ini_idx]),
                "fim_pct": float(eixo_pct[fim_idx]),
            })
    return anomalias, derivada


def processar_anomalias_piloto(
    nome: str,
    motec_sinc: pd.DataFrame,
    t_pupila: np.ndarray,
    diam_pupila: np.ndarray,
    df_ideal: pd.DataFrame,
) -> tuple[list[dict], dict[str, bytes]]:
    """
    Processa todas as voltas do MoTeC sincronizado, detecta anomalias e gera
    gráficos por volta em memória.

    Retorna
    -------
    anomalias_lista : list[dict] com campos piloto, volta_num, anom_num, tipo,
                      ini_pct, fim_pct, t_ini_volta, t_fim_volta
    imagens         : dict {nome_arquivo: png_bytes}
    """
    eixo_pct = df_ideal["progresso_pct"].values
    n_pontos_ideal = len(eixo_pct)
    steering_medio = df_ideal["steering_medio"].values
    steering_sigma = df_ideal["steering_sigma"].values
    acel_medio = df_ideal["acel_medio"].values
    freio_medio = df_ideal["freio_medio"].values
    pupila_medio = df_ideal["pupila_medio"].values

    cores_tipo = {"A": "#e74c3c", "B": "#e67e22", "C": "#8e44ad"}
    labels_tipo = {"A": "Sinal Invertido", "B": "Desvio na Reta", "C": "Correcao Brusca"}

    # Voltas disponíveis (exclui volt 0 e a última)
    lap_counts = sorted(motec_sinc["lap_count"].dropna().unique())
    if len(lap_counts) > 1:
        lap_counts = lap_counts[:-1]
    else:
        lap_counts = []
    print(f"   [{nome}] Voltas para analisar: {[int(lc) for lc in lap_counts]}")

    # Duração mediana das voltas lancadas (lap > 0) para cortar Volta 0
    duracoes_standard = []
    for lc in lap_counts:
        if int(lc) > 0:
            df_lc = motec_sinc[motec_sinc["lap_count"] == lc]
            if len(df_lc) >= 10:
                duracoes_standard.append(
                    float(df_lc["t_sync"].max()) - float(df_lc["t_sync"].min())
                )
    duracao_ref = float(np.median(duracoes_standard)) if duracoes_standard else None

    anomalias_lista: list[dict] = []
    imagens: dict[str, bytes] = {}

    t_motec = motec_sinc["t_sync"].values
    steer_vals = motec_sinc["steer"].values
    acel_vals = motec_sinc["acel"].values
    freio_vals = motec_sinc["freio"].values

    for lap_count in lap_counts:
        volta_num = int(lap_count)
        df_v = (
            motec_sinc[motec_sinc["lap_count"] == lap_count]
            .sort_values("t_sync")
            .reset_index(drop=True)
        )
        t_ini = float(df_v["t_sync"].min())
        t_fim = float(df_v["t_sync"].max())

        # Corte da volta 0 (saída do grid)
        if volta_num == 0 and duracao_ref is not None:
            t_corte = t_fim - duracao_ref
            df_v = df_v[df_v["t_sync"] >= t_corte].reset_index(drop=True)
            t_ini = float(df_v["t_sync"].min())

        if len(df_v) < 10:
            print(f"   [{nome}] Volta {volta_num}: poucos dados ({len(df_v)}), pulando")
            continue

        mask_p = (t_pupila >= t_ini) & (t_pupila <= t_fim)

        t_pct_v = np.linspace(0, 100, len(df_v))
        steer_v = np.interp(eixo_pct, t_pct_v, df_v["steer"].values)
        acel_v = np.interp(eixo_pct, t_pct_v, df_v["acel"].values)
        freio_v = np.interp(eixo_pct, t_pct_v, df_v["freio"].values)

        n_pup = mask_p.sum()
        if n_pup > 5:
            t_pct_pup = np.linspace(0, 100, n_pup)
            pup_v = np.interp(eixo_pct, t_pct_pup, diam_pupila[mask_p])
        else:
            pup_v = np.full(n_pontos_ideal, np.nan)

        anomalias, derivada = detectar_anomalias_pura(
            steer_v, steering_medio, steering_sigma, eixo_pct
        )
        print(f"   [{nome}] Volta {volta_num}: {len(anomalias)} anomalia(s)")

        for idx_a, anom in enumerate(anomalias):
            anomalias_lista.append({
                "piloto":      nome,
                "volta_num":   volta_num,
                "anom_num":    idx_a + 1,
                "tipo":        anom["tipo"],
                "ini_pct":     anom["ini_pct"],
                "fim_pct":     anom["fim_pct"],
                "t_ini_volta": t_ini,
                "t_fim_volta": t_fim,
            })

        # Gerar gráfico da volta
        eh_reta = np.abs(steering_medio) < LIMIAR_RETA_GRAUS
        eh_curva = ~eh_reta

        fig = plt.figure(figsize=(20, 16))
        fig.suptitle(
            f"Volta {volta_num} - {nome} | {len(anomalias)} anomalia(s)",
            fontsize=14, fontweight="bold",
        )
        gs = gridspec.GridSpec(5, 1, height_ratios=[0.5, 2.5, 1.5, 1.5, 1.5], hspace=0.4)

        ax_ctx = fig.add_subplot(gs[0])
        ax_steer = fig.add_subplot(gs[1], sharex=ax_ctx)
        ax_ideal = fig.add_subplot(gs[2], sharex=ax_ctx)
        ax_pedal = fig.add_subplot(gs[3], sharex=ax_ctx)
        ax_pupil = fig.add_subplot(gs[4], sharex=ax_ctx)

        ax_ctx.fill_between(eixo_pct, 0, 1, where=eh_reta, color="#2ecc71", alpha=0.4, label="Reta")
        ax_ctx.fill_between(eixo_pct, 0, 1, where=eh_curva, color="#3498db", alpha=0.4, label="Curva")
        ax_ctx.set_yticks([])
        ax_ctx.legend(loc="upper right", fontsize=7)
        ax_ctx.set_title("Contexto da Pista", fontsize=8)

        ax_steer.fill_between(
            eixo_pct, steering_medio - steering_sigma, steering_medio + steering_sigma,
            color="gray", alpha=0.15, label="+/-1sigma ideal",
        )
        ax_steer.plot(eixo_pct, steering_medio, color="gray", linewidth=2, linestyle="--", label="Ideal", zorder=4)
        ax_steer.plot(eixo_pct, steer_v, color="#2980b9", linewidth=1.5, label=f"{nome} - Volta {volta_num}", zorder=5)
        ax_steer.set_ylabel("Steering (graus)", fontsize=9)
        ax_steer.legend(loc="upper right", fontsize=7)
        ax_steer.grid(True, alpha=0.3)

        desvio_interp = steer_v - steering_medio
        ax_ideal.axhline(0, color="gray", linewidth=1, linestyle="--")
        ax_ideal.fill_between(eixo_pct, 0, desvio_interp, where=desvio_interp > 0, color="#e74c3c", alpha=0.4, label="Acima")
        ax_ideal.fill_between(eixo_pct, 0, desvio_interp, where=desvio_interp < 0, color="#3498db", alpha=0.4, label="Abaixo")
        ax_ideal.set_ylabel("Delta Steering", fontsize=9)
        ax_ideal.set_title("Desvio em relacao ao Tracado Ideal", fontsize=8)
        ax_ideal.legend(loc="upper right", fontsize=7)
        ax_ideal.grid(True, alpha=0.3)

        ax_pedal.plot(eixo_pct, acel_v, color="orange", linewidth=1.2, label="Acelerador")
        ax_pedal.plot(eixo_pct, freio_v, color="green", linewidth=1.2, label="Freio")
        ax_pedal.set_ylabel("%", fontsize=9)
        ax_pedal.legend(loc="upper right", fontsize=7)
        ax_pedal.grid(True, alpha=0.3)

        ax_pupil.plot(eixo_pct, pup_v, color="purple", linewidth=1.2, label="Pupila")
        ax_pupil.set_ylabel("Diametro (mm)", fontsize=9)
        ax_pupil.set_xlabel("Progresso da Volta (%)", fontsize=10)
        ax_pupil.legend(loc="upper right", fontsize=7)
        ax_pupil.grid(True, alpha=0.3)

        labels_plotados: set[str] = set()
        for idx_a, anom in enumerate(anomalias):
            cor = cores_tipo[anom["tipo"]]
            ini_p = anom["ini_pct"]
            fim_p = anom["fim_pct"]
            label = labels_tipo[anom["tipo"]] if anom["tipo"] not in labels_plotados else None
            for ax in [ax_ctx, ax_steer, ax_ideal, ax_pedal, ax_pupil]:
                ax.axvspan(ini_p, fim_p, color=cor, alpha=0.15, zorder=3)
            mask_a = (eixo_pct >= ini_p) & (eixo_pct <= fim_p)
            ax_steer.plot(eixo_pct[mask_a], steer_v[mask_a], color=cor, linewidth=3, zorder=6, label=label)
            labels_plotados.add(anom["tipo"])
            meio = (ini_p + fim_p) / 2
            idx_ann = int(np.argmin(np.abs(eixo_pct - meio)))
            y = steer_v[idx_ann]
            off = 15 if y >= 0 else -15
            ax_steer.annotate(
                f"{anom['tipo']}{idx_a + 1}",
                xy=(meio, y), xytext=(meio, y + off),
                fontsize=7, color=cor, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="->", color=cor, lw=0.8),
            )

        ax_steer.legend(loc="upper right", fontsize=7)

        nome_arquivo = f"volta_{volta_num:02d}_{nome}.png"
        imagens[nome_arquivo] = fig_para_bytes(fig, dpi=150)
        plt.close(fig)
        print(f"   [{nome}] Imagem gerada: {nome_arquivo}")

    return anomalias_lista, imagens


# ---------------------------------------------------------------------------
# Análise TR — helpers (Script 4 equivalente)
# ---------------------------------------------------------------------------


def _encontrar_onset(
    t_sinal: np.ndarray,
    v_sinal: np.ndarray,
    t_ref: float,
    janela_seg: float,
    limiar: float,
) -> float | None:
    mask = (t_sinal >= t_ref - janela_seg) & (t_sinal <= t_ref)
    if mask.sum() < 3:
        return None
    t_j = t_sinal[mask]
    v_j = v_sinal[mask]
    n_base = max(1, int(len(v_j) * 0.2))
    baseline = np.nanmean(v_j[:n_base])
    for i in range(len(v_j) - 1, -1, -1):
        if abs(v_j[i] - baseline) <= limiar:
            return float(t_j[i])
    return float(t_j[0])


def _pct_para_tempo_real(pct_alvo: float, t_ini_volta: float, t_fim_volta: float) -> float:
    return t_ini_volta + (pct_alvo / 100.0) * (t_fim_volta - t_ini_volta)


def _calcular_crescimento_pupilar_derivada(
    t_pupila: np.ndarray, diam_pupila: np.ndarray, t_ini: float, t_fim: float
) -> float:
    mask = (t_pupila >= t_ini) & (t_pupila <= t_fim)
    if mask.sum() < 3:
        return np.nan
    t_seg = t_pupila[mask]
    d_seg = diam_pupila[mask]
    dt = np.diff(t_seg)
    dt[dt == 0] = np.nan
    derivadas = np.diff(d_seg) / dt
    valid = derivadas[~np.isnan(derivadas)]
    return float(np.nanmax(valid)) if len(valid) > 0 else np.nan


def _calcular_metricas_blinks(
    df_blinks: pd.DataFrame,
    t_jan_ini: float,
    t_jan_fim: float,
    t_motec: np.ndarray,
    vel_ms: np.ndarray | None,
) -> tuple[float, float]:
    if df_blinks.empty:
        return np.nan, np.nan
    mask = (df_blinks["t_ini"] < t_jan_fim) & (df_blinks["t_fim"] > t_jan_ini)
    blinks_janela = df_blinks[mask]
    if blinks_janela.empty:
        return 0.0, 0.0
    tempo_total = 0.0
    distancia_total = 0.0
    vel_disponivel = vel_ms is not None and not np.all(np.isnan(vel_ms))
    for _, blink in blinks_janela.iterrows():
        b_ini = max(blink["t_ini"], t_jan_ini)
        b_fim = min(blink["t_fim"], t_jan_fim)
        tempo_total += b_fim - b_ini
        if vel_disponivel:
            mask_v = (t_motec >= b_ini) & (t_motec <= b_fim)
            if mask_v.sum() >= 2:
                distancia_total += float(np.trapezoid(vel_ms[mask_v], t_motec[mask_v]))
    return round(tempo_total, 4), round(distancia_total, 4)


def _detectar_picos_pupila(
    t_pupila: np.ndarray, diam_pupila: np.ndarray, janela: int = 15
) -> list[tuple[float, float]]:
    if len(t_pupila) < janela * 3:
        return []
    series = pd.Series(diam_pupila)
    baseline = series.rolling(window=janela * 3, center=True, min_periods=3).median()
    delta = series - baseline
    picos = []
    for i in range(janela, len(delta) - janela):
        d = delta.iloc[i]
        if np.isnan(d) or d <= LIMIAR_PICO_DILATACAO_MM:
            continue
        janela_local = delta.iloc[i - janela: i + janela + 1]
        if d == janela_local.max():
            picos.append((float(t_pupila[i]), float(d)))
    return picos


def _estatisticas_fixacao(df_fix: pd.DataFrame) -> dict:
    vazio = {
        "n_fixacoes": 0, "dur_media_ms": np.nan, "dur_min_ms": np.nan,
        "dur_max_ms": np.nan, "n_curtas": 0, "n_longas": 0,
        "pos_x_media": np.nan, "pos_y_media": np.nan, "conf_media": np.nan,
    }
    if df_fix is None or df_fix.empty:
        return vazio
    durs = df_fix["duration_ms"].dropna() if "duration_ms" in df_fix.columns else pd.Series([], dtype=float)
    return {
        "n_fixacoes": len(df_fix),
        "dur_media_ms": float(durs.mean()) if len(durs) > 0 else np.nan,
        "dur_min_ms": float(durs.min()) if len(durs) > 0 else np.nan,
        "dur_max_ms": float(durs.max()) if len(durs) > 0 else np.nan,
        "n_curtas": int((durs < LIMIAR_FIXACAO_CURTA_MS).sum()),
        "n_longas": int((durs > LIMIAR_FIXACAO_LONGA_MS).sum()),
        "pos_x_media": float(df_fix["norm_x"].mean()) if "norm_x" in df_fix.columns else np.nan,
        "pos_y_media": float(df_fix["norm_y"].mean()) if "norm_y" in df_fix.columns else np.nan,
        "conf_media": float(df_fix["confidence"].mean()) if "confidence" in df_fix.columns else np.nan,
    }


def _classificar_comportamento_fixacao(stats: dict) -> str:
    if not stats or stats.get("n_fixacoes", 0) == 0:
        return "Sem dados de fixacao"
    n = stats["n_fixacoes"]
    dur = stats.get("dur_media_ms", np.nan)
    if np.isnan(dur):
        return "Sem dados de duracao"
    if stats.get("n_curtas", 0) / n > 0.4:
        return "Busca visual dispersa (muitas fixacoes curtas)"
    if stats.get("n_longas", 0) / n > 0.3:
        return "Visao em tunel (fixacoes excessivamente longas)"
    if LIMIAR_FIXACAO_CURTA_MS <= dur <= LIMIAR_FIXACAO_LONGA_MS:
        return "Exploracao visual normal"
    return "Padrao misto"


def _inferir_contexto_pista(tipo: str, s_window: np.ndarray | None) -> str:
    if tipo == "A":
        return "Curva"
    if tipo == "B":
        return "Reta"
    if s_window is not None and len(s_window) > 0:
        return "Curva" if np.nanmean(np.abs(s_window)) > 15.0 else "Reta"
    return "Indefinido"


# ---------------------------------------------------------------------------
# Análise TR por piloto — gera registros CSV + PDF (Script 4 equivalente)
# ---------------------------------------------------------------------------


def processar_tr_piloto(
    nome: str,
    anomalias_bruta: list[dict],
    df_ideal: pd.DataFrame,
    motec_sinc: pd.DataFrame,
    t_pupila: np.ndarray,
    diam_pupila: np.ndarray,
    df_fix_sync: pd.DataFrame,
    df_blinks: pd.DataFrame,
    imagens_voltas: dict[str, bytes] | None = None,
) -> tuple[list[dict], bytes | None, bytes]:
    """
    Processa a análise de Tempo de Reação para cada anomalia de um piloto.

    Parâmetros
    ----------
    nome           : nome do piloto
    anomalias_bruta: lista de dicts de `processar_anomalias_piloto`
    df_ideal       : DataFrame do traçado ideal (colunas progresso_pct, steering_medio, ...)
    motec_sinc     : DataFrame com t_sync, steer, acel, freio, vel
    t_pupila       : array de tempos sincronizados da pupila
    diam_pupila    : array de diâmetros suavizados
    df_fix_sync    : DataFrame de fixações sincronizadas (pode ser vazio)
    df_blinks      : DataFrame de blinks sincronizados (pode ser vazio)

    Retorna
    -------
    registros_csv : list[dict] com todas as métricas para exportação CSV
    pdf_bytes     : bytes do relatório PDF (None se reportlab não disponível)
    csv_bytes     : bytes do CSV individual do piloto
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate
        REPORTLAB_OK = True
    except ImportError:
        REPORTLAB_OK = False

    eixo_pct = df_ideal["progresso_pct"].values
    steer_med = df_ideal["steering_medio"].values

    t_motec = motec_sinc["t_sync"].values
    steer_raw = motec_sinc["steer"].values
    acel_raw = motec_sinc["acel"].values
    freio_raw = motec_sinc["freio"].values
    vel_raw = motec_sinc["vel"].values if "vel" in motec_sinc.columns else None

    # Filtrar anomalias desta volta (excluir volta 0)
    anom_piloto = [a for a in anomalias_bruta if a["piloto"] == nome and a["volta_num"] != 0]
    if not anom_piloto:
        return [], None, b""

    # Reordenar voltas (1, 2, ...) para exibição no PDF
    voltas_ordenadas = sorted({a["volta_num"] for a in anom_piloto})
    mapa_voltas = {v: i + 1 for i, v in enumerate(voltas_ordenadas)}

    # Picos cognitivos (sessão completa)
    picos_cognitivos = _detectar_picos_pupila(t_pupila, diam_pupila)
    print(f"   [{nome}] Picos cognitivos: {len(picos_cognitivos)}")

    # Perfil pupilar por setor e por volta
    lista_voltas_unicas = []
    seen_v: set[int] = set()
    for a in anom_piloto:
        vn = a["volta_num"]
        if vn not in seen_v:
            seen_v.add(vn)
            lista_voltas_unicas.append({
                "volta_num": mapa_voltas[vn],
                "t_ini": float(a["t_ini_volta"]),
                "t_fim": float(a["t_fim_volta"]),
            })

    perfis_por_volta = [
        _calcular_perfil_pupilar_por_setor(t_pupila, diam_pupila, v["t_ini"], v["t_fim"])
        for v in lista_voltas_unicas
    ]

    # Análise por anomalia
    lista_anomalias_dados: list[dict] = []
    registros_csv: list[dict] = []

    for a in anom_piloto:
        volta_num_orig = a["volta_num"]
        volta_num = mapa_voltas[volta_num_orig]
        anom_num = a["anom_num"]
        tipo = a["tipo"]
        ini_pct = a["ini_pct"]
        fim_pct = a["fim_pct"]
        t_ini_v = float(a["t_ini_volta"])
        t_fim_v = float(a["t_fim_volta"])

        t_anom_ini = _pct_para_tempo_real(ini_pct, t_ini_v, t_fim_v)
        t_anom_fim = _pct_para_tempo_real(fim_pct, t_ini_v, t_fim_v)
        dur_anom = t_anom_fim - t_anom_ini

        t_jan_ini = t_anom_ini - JANELA_REACAO_SEG
        t_jan_fim = t_anom_fim + JANELA_POS_ANOMALIA_SEG

        mask_m = (t_motec >= t_jan_ini) & (t_motec <= t_jan_fim)
        mask_p = (t_pupila >= t_jan_ini) & (t_pupila <= t_jan_fim)

        if mask_m.sum() < 5:
            print(f"   [{nome}] Anomalia {tipo}{anom_num}: dados insuficientes, pulando")
            continue

        t_m_jan = t_motec[mask_m]
        s_jan = steer_raw[mask_m]
        a_jan = acel_raw[mask_m]
        f_jan = freio_raw[mask_m]
        t_p_jan = t_pupila[mask_p]
        d_jan = diam_pupila[mask_p]

        onset_steer = _encontrar_onset(t_m_jan, s_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_STEERING_GRAUS)
        onset_acel = _encontrar_onset(t_m_jan, a_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PEDAL_PCT)
        onset_freio = _encontrar_onset(t_m_jan, f_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PEDAL_PCT)
        onset_pupil = (
            _encontrar_onset(t_p_jan, d_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PUPILA_MM)
            if len(t_p_jan) > 2 else None
        )

        onsets = {"Steering": onset_steer, "Acelerador": onset_acel, "Freio": onset_freio, "Pupila": onset_pupil}
        onsets_validos = {k: v for k, v in onsets.items() if v is not None}
        ordem_reacao = sorted(onsets_validos, key=lambda k: onsets_validos[k])
        primeiro_sinal = ordem_reacao[0] if ordem_reacao else None
        t_primeiro = onsets_validos.get(primeiro_sinal)

        # Diâmetro pupilar nas três fases
        m_antes = (t_pupila >= t_anom_ini - 1.0) & (t_pupila < t_anom_ini)
        m_durante = (t_pupila >= t_anom_ini) & (t_pupila < t_anom_fim)
        m_depois = (t_pupila >= t_anom_fim) & (t_pupila < t_anom_fim + 1.0)
        d_antes = np.nanmean(diam_pupila[m_antes]) if m_antes.sum() > 0 else np.nan
        d_durante = np.nanmean(diam_pupila[m_durante]) if m_durante.sum() > 0 else np.nan
        d_depois = np.nanmean(diam_pupila[m_depois]) if m_depois.sum() > 0 else np.nan
        delta_d = d_durante - d_antes if not (np.isnan(d_antes) or np.isnan(d_durante)) else np.nan

        # Fixações na janela
        df_fix_janela = (
            df_fix_sync[(df_fix_sync["t_sync"] >= t_jan_ini) & (df_fix_sync["t_sync"] <= t_jan_fim)].copy()
            if not df_fix_sync.empty and "t_sync" in df_fix_sync.columns
            else pd.DataFrame()
        )
        stats_fix = _estatisticas_fixacao(df_fix_janela)
        comportamento_fix = _classificar_comportamento_fixacao(stats_fix)

        # Picos na janela
        picos_jan = [(t, d) for (t, d) in picos_cognitivos if t_jan_ini <= t <= t_jan_fim]
        n_picos_jan = len(picos_jan)
        intensidade_picos = round(float(np.mean([d for _, d in picos_jan])), 4) if picos_jan else 0.0

        tr_pupilar = round(float(onset_pupil - t_anom_ini), 4) if onset_pupil is not None else ""
        media_pup = (
            round(float(np.nanmean(d_jan)), 4)
            if len(d_jan) > 0 and not np.all(np.isnan(d_jan))
            else ""
        )
        _cresc = _calcular_crescimento_pupilar_derivada(t_pupila, diam_pupila, t_anom_ini, t_anom_fim)
        cresc_derivada = round(_cresc, 4) if not np.isnan(_cresc) else ""

        tempo_escuro, dist_escuro = _calcular_metricas_blinks(
            df_blinks, t_jan_ini, t_jan_fim, t_motec, vel_raw
        )

        tipo_resp_pupilar = (
            "" if np.isnan(delta_d)
            else ("Dilatacao" if delta_d > 0.2 else ("Contracao" if delta_d < -0.2 else "Estavel"))
        )

        trs: dict[str, float] = {}
        if t_primeiro is not None:
            for sinal, t_on in onsets_validos.items():
                trs[f"TR_{sinal.lower()}_s"] = round(t_on - t_primeiro, 4)

        # Gráfico da anomalia individual (em memória)
        cor = CORES_TIPO[tipo]
        steer_sigma = df_ideal["steering_sigma"].values if "steering_sigma" in df_ideal.columns else None
        fig_bytes = _gerar_grafico_anomalia_individual(
            nome, tipo, volta_num, anom_num,
            t_m_jan, s_jan, a_jan, f_jan,
            t_p_jan, d_jan,
            t_anom_ini, t_anom_fim,
            df_fix_janela,
            eixo_pct, steer_med, steer_sigma, ini_pct, fim_pct,
            t_jan_ini, t_jan_fim,
            onsets_validos, ordem_reacao, primeiro_sinal,
            d_antes, delta_d,
            cor,
        )

        dado: dict = {
            "volta_num": volta_num,
            "anom_num": anom_num,
            "tipo": tipo,
            "ini_pct": ini_pct,
            "fim_pct": fim_pct,
            "duracao_anom": dur_anom,
            "primeiro_sinal": primeiro_sinal,
            "ordem_reacao": " -> ".join(ordem_reacao),
            "diam_antes": d_antes,
            "diam_durante": d_durante,
            "diam_depois": d_depois,
            "delta_diam": delta_d,
            "fig_bytes": io.BytesIO(fig_bytes) if fig_bytes else None,
            "stats_fixacao": stats_fix,
            "comportamento_visual": comportamento_fix,
        }
        dado.update(trs)
        lista_anomalias_dados.append(dado)

        registros_csv.append({
            "piloto": nome,
            "nivel_piloto": NIVEL_PILOTOS.get(nome, "Amador"),
            "volta_num": volta_num,
            "anom_num": anom_num,
            "tipo": tipo,
            "ini_pct": ini_pct,
            "fim_pct": fim_pct,
            "duracao_anom": round(dur_anom, 4),
            "primeiro_sinal": primeiro_sinal or "",
            "ordem_reacao": " -> ".join(ordem_reacao),
            "diam_antes_mm": round(d_antes, 4) if not np.isnan(d_antes) else "",
            "diam_durante_mm": round(d_durante, 4) if not np.isnan(d_durante) else "",
            "diam_depois_mm": round(d_depois, 4) if not np.isnan(d_depois) else "",
            "delta_diam_mm": round(delta_d, 4) if not np.isnan(delta_d) else "",
            "n_fixacoes_janela": stats_fix["n_fixacoes"],
            "dur_media_fix_ms": (
                round(stats_fix["dur_media_ms"], 1)
                if not np.isnan(stats_fix.get("dur_media_ms", float("nan")))
                else ""
            ),
            "fix_curtas": stats_fix["n_curtas"],
            "fix_longas": stats_fix["n_longas"],
            "comportamento_visual": comportamento_fix,
            "t_anom_ini": round(t_anom_ini, 4),
            "contexto_pista": _inferir_contexto_pista(tipo, s_jan),
            "tipo_resposta_pupilar": tipo_resp_pupilar,
            "n_picos_cognitivos_janela": n_picos_jan,
            "intensidade_media_picos": intensidade_picos,
            "tempo_reacao_pupilar_s": tr_pupilar,
            "media_tamanho_pupilar": media_pup,
            "crescimento_pupilar_derivada": cresc_derivada,
            "tempo_no_escuro_s": tempo_escuro if not (isinstance(tempo_escuro, float) and np.isnan(tempo_escuro)) else "",
            "distancia_no_escuro_m": dist_escuro if not (isinstance(dist_escuro, float) and np.isnan(dist_escuro)) else "",
            **{k: v for k, v in trs.items()},
        })

        print(
            f"   [{nome}] Anomalia {tipo}{anom_num} (Volta {volta_num}): "
            f"1o sinal={primeiro_sinal} | fixacoes={stats_fix['n_fixacoes']}"
        )

    # Gerar CSV em bytes
    csv_bytes = b""
    if registros_csv:
        df_csv = pd.DataFrame(registros_csv)
        buf = io.BytesIO()
        df_csv.to_csv(buf, index=False, encoding="utf-8")
        csv_bytes = buf.getvalue()

    # Gerar PDF em bytes
    pdf_bytes: bytes | None = None
    if lista_anomalias_dados and REPORTLAB_OK:
        from backend.processamento._pdf_builder import gerar_pdf_bytes
        pdf_bytes = gerar_pdf_bytes(
            nome=nome,
            lista_anomalias_dados=lista_anomalias_dados,
            perfis_por_volta=perfis_por_volta,
            picos_cognitivos=picos_cognitivos,
            t_pupila_total=t_pupila,
            diam_pupila_total=diam_pupila,
            df_fix_sync=df_fix_sync,
            lista_voltas=lista_voltas_unicas,
            imagens_voltas=imagens_voltas,
        )

    return registros_csv, pdf_bytes, csv_bytes


# ---------------------------------------------------------------------------
# Perfil pupilar por setor
# ---------------------------------------------------------------------------


def _calcular_perfil_pupilar_por_setor(
    t_pupila: np.ndarray,
    diam_pupila: np.ndarray,
    t_ini_volta: float,
    t_fim_volta: float,
) -> list[dict]:
    dur = t_fim_volta - t_ini_volta
    if dur <= 0:
        return []
    resultado = []
    for s in range(N_SETORES):
        t_s_ini = t_ini_volta + (s / N_SETORES) * dur
        t_s_fim = t_ini_volta + ((s + 1) / N_SETORES) * dur
        mask = (t_pupila >= t_s_ini) & (t_pupila < t_s_fim)
        vals = diam_pupila[mask]
        vals = vals[~np.isnan(vals)]
        resultado.append({
            "setor": s + 1,
            "pct_ini": s * (100 / N_SETORES),
            "pct_fim": (s + 1) * (100 / N_SETORES),
            "media": float(np.mean(vals)) if len(vals) > 0 else np.nan,
            "desvio": float(np.std(vals)) if len(vals) > 1 else np.nan,
            "n": len(vals),
        })
    return resultado


# ---------------------------------------------------------------------------
# Gráfico individual por anomalia (para o PDF)
# ---------------------------------------------------------------------------


def _gerar_grafico_anomalia_individual(
    nome, tipo, volta_num, anom_num,
    t_m_jan, s_jan, a_jan, f_jan,
    t_p_jan, d_jan,
    t_anom_ini, t_anom_fim,
    df_fix_janela,
    eixo_pct, steer_med, steer_sigma, ini_pct, fim_pct,
    t_jan_ini, t_jan_fim,
    onsets_validos, ordem_reacao, primeiro_sinal,
    d_antes, delta_d,
    cor,
) -> bytes:
    """
    Gera gráfico de anomalia individual com 4 painéis (de cima para baixo):
      1. Steering do piloto vs média ideal (± 1σ) + marcadores de TR
      2. Desvio em relação ao ideal (delta steering)
      3. Pupila (diâmetro suavizado + fixações)
      4. Pedais (acelerador e freio)
    """
    cores_onset = {
        "Steering": "#2980b9", "Acelerador": "#e67e22",
        "Freio": "#27ae60", "Pupila": "#8e44ad",
    }
    t_primeiro = onsets_validos.get(primeiro_sinal) if primeiro_sinal else None

    fig = plt.figure(figsize=(14, 12))
    fig.suptitle(
        f"Anomalia {tipo}{anom_num} - Volta {volta_num} - {nome}\n"
        f"{LABELS_TIPO.get(tipo, tipo)} | {ini_pct:.1f}% - {fim_pct:.1f}%",
        fontsize=10, fontweight="bold",
    )
    gs = gridspec.GridSpec(4, 1, height_ratios=[2.5, 1.2, 1.4, 1.2], hspace=0.50)
    ax_steer = fig.add_subplot(gs[0])
    ax_desvio = fig.add_subplot(gs[1], sharex=ax_steer)
    ax_pup = fig.add_subplot(gs[2], sharex=ax_steer)
    ax_pedal = fig.add_subplot(gs[3], sharex=ax_steer)

    # ── Painel 1: Steering piloto vs ideal ──────────────────────────────────
    steer_ideal_interp: np.ndarray | None = None
    if len(eixo_pct) > 0 and len(t_m_jan) > 0:
        mask_ideal = (eixo_pct >= max(0, ini_pct - 5)) & (eixo_pct <= min(100, fim_pct + 5))
        if mask_ideal.any():
            t_ideal_jan = np.linspace(t_jan_ini, t_jan_fim, mask_ideal.sum())
            med_seg = steer_med[mask_ideal]
            ax_steer.plot(t_ideal_jan, med_seg, color="gray", linewidth=2,
                          linestyle="--", label="Ideal (media)", zorder=3)
            if steer_sigma is not None:
                sig_seg = steer_sigma[mask_ideal]
                ax_steer.fill_between(
                    t_ideal_jan,
                    med_seg - sig_seg, med_seg + sig_seg,
                    color="gray", alpha=0.15, label="±1σ ideal",
                )
            # Interpola ideal no eixo de tempo do piloto para calcular desvio
            steer_ideal_interp = np.interp(t_m_jan, t_ideal_jan, med_seg)

    ax_steer.plot(t_m_jan, s_jan, color="#2980b9", linewidth=1.6, label="Steering piloto", zorder=5)
    ax_steer.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.20, label="Anomalia")
    ax_steer.axvline(t_anom_ini, color=cor, linewidth=2.2, linestyle="--",
                     label=f"Inicio ({t_anom_ini:.2f}s)")
    for sinal in ordem_reacao:
        t_on = onsets_validos[sinal]
        tr = t_on - t_primeiro if t_primeiro is not None else 0.0
        ax_steer.axvline(t_on, color=cores_onset[sinal], linewidth=1.6, linestyle=":",
                         alpha=0.9, label=f"{sinal} (TR={tr:+.3f}s)")
    ordem_str = " -> ".join(ordem_reacao) if ordem_reacao else "N/D"
    ax_steer.set_title(f"Media x Volta | Ordem reacao: {ordem_str}", fontsize=8)
    ax_steer.set_ylabel("Steering (graus)", fontsize=8)
    ax_steer.legend(loc="upper right", fontsize=6)
    ax_steer.grid(True, alpha=0.3)

    # ── Painel 2: Desvio em relação ao ideal ────────────────────────────────
    ax_desvio.axhline(0, color="gray", linewidth=1, linestyle="--")
    if steer_ideal_interp is not None and len(s_jan) == len(steer_ideal_interp):
        desvio = s_jan - steer_ideal_interp
        ax_desvio.fill_between(t_m_jan, 0, desvio, where=(desvio > 0),
                               color="#e74c3c", alpha=0.55, label="Acima do ideal")
        ax_desvio.fill_between(t_m_jan, 0, desvio, where=(desvio < 0),
                               color="#3498db", alpha=0.55, label="Abaixo do ideal")
        ax_desvio.plot(t_m_jan, desvio, color="gray", linewidth=0.7, alpha=0.5)
    ax_desvio.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.15)
    ax_desvio.axvline(t_anom_ini, color=cor, linewidth=1.8, linestyle="--")
    ax_desvio.set_title("Desvio em relacao ao Ideal", fontsize=8)
    ax_desvio.set_ylabel("Delta (graus)", fontsize=8)
    ax_desvio.legend(loc="upper right", fontsize=6)
    ax_desvio.grid(True, alpha=0.3)

    # ── Painel 3: Pupila ────────────────────────────────────────────────────
    if len(t_p_jan) > 1:
        ax_pup.plot(t_p_jan, d_jan, color="purple", linewidth=1.6, label="Pupila", zorder=4)
        if not np.isnan(d_antes):
            ax_pup.axhline(d_antes, color="gray", linewidth=1, linestyle=":",
                           label=f"Baseline: {d_antes:.2f}mm")
        if not df_fix_janela.empty and "t_sync" in df_fix_janela.columns:
            first_fix = True
            for _, fx in df_fix_janela.iterrows():
                lbl = "Fixacao" if first_fix else "_"
                ax_pup.axvline(fx["t_sync"], color="cyan", linewidth=0.9, alpha=0.7,
                               linestyle="-.", label=lbl)
                first_fix = False
        sinal_d = "+" if (not np.isnan(delta_d) and delta_d > 0) else ""
        reacao_p = "dilatou" if (not np.isnan(delta_d) and delta_d > 0) else "contraiu"
        titulo_pup = "Pupila"
        if not np.isnan(delta_d):
            titulo_pup += f" | Delta={sinal_d}{delta_d:.2f}mm ({reacao_p})"
        ax_pup.set_title(titulo_pup, fontsize=8)
    ax_pup.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.15)
    ax_pup.axvline(t_anom_ini, color=cor, linewidth=1.8, linestyle="--")
    ax_pup.set_ylabel("Diam (mm)", fontsize=8)
    ax_pup.legend(loc="upper right", fontsize=6)
    ax_pup.grid(True, alpha=0.3)

    # ── Painel 4: Pedais ────────────────────────────────────────────────────
    ax_pedal.plot(t_m_jan, a_jan, color="orange", linewidth=1.4, label="Acelerador")
    ax_pedal.plot(t_m_jan, f_jan, color="green", linewidth=1.4, label="Freio")
    ax_pedal.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.15)
    ax_pedal.axvline(t_anom_ini, color=cor, linewidth=1.8, linestyle="--")
    ax_pedal.set_ylabel("%", fontsize=8)
    ax_pedal.set_title("Pedais", fontsize=8)
    ax_pedal.set_xlabel("Tempo Sincronizado (s)", fontsize=8)
    ax_pedal.legend(loc="upper right", fontsize=6)
    ax_pedal.grid(True, alpha=0.3)

    plt.tight_layout()
    b = fig_para_bytes(fig, dpi=130)
    plt.close(fig)
    return b
