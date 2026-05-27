import os

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from codigos_tcc.configuracao import (
    ARQUIVO_ANOMALIAS,
    ARQUIVO_IDEAL,
    ARQUIVO_VOLTAS,
    GRAFICOS_VOLTAS_DIR,
    PILOTOS,
    validar_arquivos_base,
)


N_PONTOS = 1000
LIMIAR_RETA_GRAUS = 10.0
LIMIAR_SINAL_INVERTIDO_GRAUS = 20.0
LIMIAR_DESVIO_RETA_GRAUS = 15.0
LIMIAR_DERIVADA = 8.0
JANELA_SUAVIZACAO_DERIV = 5
DURACAO_MINIMA_PCT = 0.8
TOLERANCIA_GAP_PCT = 0.8

# Detecção aprimorada
LIMIAR_DTW_SCORE = 5.0
LIMIAR_DESVIO_RETA_PICO_GRAUS = 25.0
LIMIAR_DERIVADA_MEDIA = 3.5
LIMIAR_CHICOTE_IDEAL_GRAUS = 15.0
LIMIAR_CHICOTE_PILOTO_GRAUS = 45.0
LIMIAR_OVERSHOOT_GRAUS = 45.0
DTW_TAMANHO_JANELA = 80
DTW_PASSO = 20


def force_float(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip().replace(",", ".")
    if s.count(".") > 1:
        parts = s.rsplit(".", 1)
        s = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(s)
    except Exception:
        return np.nan


def limpa_diametro(x):
    s = str(x).strip().replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "")
        s = s[:2] + "." + s[2:]
    return pd.to_numeric(s, errors="coerce")


def atirar_com_sniper(frame_alvo, df, col_wi, col_t):
    match_exato = df[df[col_wi] == frame_alvo]
    if not match_exato.empty:
        return force_float(match_exato[col_t].iloc[0])
    idx_mais_perto = (df[col_wi] - frame_alvo).abs().idxmin()
    frame_encontrado = df.loc[idx_mais_perto, col_wi]
    diff = abs(frame_encontrado - frame_alvo)
    print(f"   Frame {frame_alvo} ausente -> {frame_encontrado} (diff: {diff})")
    return force_float(df.loc[idx_mais_perto, col_t])


def clean_col(df, name_list):
    for name in name_list:
        target = [c for c in df.columns if c.lower() == name.lower()]
        if not target:
            target = [c for c in df.columns if name.lower() in c.lower()]
        if target:
            series = pd.to_numeric(
                df[target[0]].astype(str).str.replace(",", ".", regex=False), errors="coerce"
            )
            print(f"   '{name}' -> '{target[0]}' | nao nulos: {series.notna().sum()}")
            return series
    print(f"   Nao encontrado: {name_list}")
    return None


def interpolar_volta(valores, n_pontos):
    n = int(n_pontos)
    valores = valores.astype(float)
    mask_valido = ~np.isnan(valores)
    if mask_valido.sum() < 2:
        return np.full(n, np.nan)
    eixo_orig = np.linspace(0.0, 100.0, len(valores))
    eixo_novo = np.linspace(0.0, 100.0, n)
    # Filtra NaN: mapeia apenas pontos validos para 0-100%, evitando shift lateral
    return np.interp(eixo_novo, eixo_orig[mask_valido], valores[mask_valido])


def agrupar_regioes(mascara_bool, eixo):
    regioes = []
    em_regiao = False
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


def mesclar_e_filtrar(regioes, eixo, tol, dur_min):
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


def dtw_score_janelas(pilot_steer, ideal_steer, tamanho_janela=DTW_TAMANHO_JANELA, passo=DTW_PASSO):
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
            dist = float(np.sum(np.abs(p - i)))
        scores[start:end] += dist / tamanho_janela
        contagens[start:end] += 1
    contagens[contagens == 0] = 1
    return scores / contagens


def centralizar_no_pico(regioes, delta, limiar_relativo=0.2):
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


def filtrar_por_pico(regioes, sinal, limiar_pico):
    return [
        (i, f) for i, f in regioes
        if len(sinal[i : f + 1]) > 0 and np.max(np.abs(sinal[i : f + 1])) >= limiar_pico
    ]


def coalescer_recuperacoes(regioes_a, regioes_bc, eixo_pct, janela_pct=5.0):
    regioes_a = [list(r) for r in regioes_a]
    absorvidas = set()
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


def detectar_anomalias(piloto_steer, steering_medio, steering_sigma, eixo_pct):
    delta = piloto_steer - steering_medio
    dtw_scores = dtw_score_janelas(piloto_steer, steering_medio)

    eh_reta = np.abs(steering_medio) < LIMIAR_RETA_GRAUS
    eh_curva = ~eh_reta

    sinal_oposto = np.sign(piloto_steer) != np.sign(steering_medio)
    magnitude_ok = (np.abs(piloto_steer) > LIMIAR_SINAL_INVERTIDO_GRAUS) & (
        np.abs(steering_medio) > LIMIAR_SINAL_INVERTIDO_GRAUS
    )
    mascara_chicote = (
        (np.abs(steering_medio) <= LIMIAR_CHICOTE_IDEAL_GRAUS) &
        (np.abs(piloto_steer) >= LIMIAR_CHICOTE_PILOTO_GRAUS)
    )
    mascara_overshoot = np.abs(delta) > LIMIAR_OVERSHOOT_GRAUS
    mascara_a = (
        (sinal_oposto & magnitude_ok & eh_curva) | mascara_chicote | mascara_overshoot
    ) & (dtw_scores > LIMIAR_DTW_SCORE)
    mascara_b = eh_reta & (np.abs(piloto_steer) > LIMIAR_DESVIO_RETA_GRAUS) & (dtw_scores > LIMIAR_DTW_SCORE)

    steer_suav = pd.Series(piloto_steer).rolling(
        window=JANELA_SUAVIZACAO_DERIV, center=True, min_periods=1
    ).mean().values
    derivada = np.abs(np.gradient(steer_suav, eixo_pct))
    mascara_c = derivada > LIMIAR_DERIVADA

    regioes_a = mesclar_e_filtrar(
        agrupar_regioes(mascara_a, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    regioes_b = mesclar_e_filtrar(
        agrupar_regioes(mascara_b, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    regioes_b = filtrar_por_pico(regioes_b, piloto_steer, LIMIAR_DESVIO_RETA_PICO_GRAUS)

    regioes_c = mesclar_e_filtrar(
        agrupar_regioes(mascara_c, eixo_pct), eixo_pct, TOLERANCIA_GAP_PCT, DURACAO_MINIMA_PCT
    )
    regioes_c = [
        (i, f) for i, f in regioes_c
        if len(derivada[i : f + 1]) > 0 and np.mean(derivada[i : f + 1]) >= LIMIAR_DERIVADA_MEDIA
    ]

    regioes_a = centralizar_no_pico(regioes_a, delta)
    regioes_b = centralizar_no_pico(regioes_b, delta)
    regioes_c = centralizar_no_pico(regioes_c, derivada)

    regioes_a, regioes_b = coalescer_recuperacoes(regioes_a, regioes_b, eixo_pct)
    regioes_a, regioes_c = coalescer_recuperacoes(regioes_a, regioes_c, eixo_pct)

    anomalias = []
    for tipo, regioes in [("A", regioes_a), ("B", regioes_b), ("C", regioes_c)]:
        for ini_idx, fim_idx in regioes:
            anomalias.append(
                {
                    "tipo": tipo,
                    "ini_idx": ini_idx,
                    "fim_idx": fim_idx,
                    "ini_pct": eixo_pct[ini_idx],
                    "fim_pct": eixo_pct[fim_idx],
                }
            )
    return anomalias, derivada


def carregar_piloto(nome, caminhos, df_meta, sessao_nome):
    df_pupil = pd.read_csv(str(caminhos["pupila"]), sep=None, engine="python", on_bad_lines="skip")
    df_pupil.columns = [str(c).strip() for c in df_pupil.columns]

    c_p_m = [c for c in df_pupil.columns if "method" in c.lower()]
    if c_p_m:
        count_2d = df_pupil[c_p_m[0]].astype(str).str.contains(
            r"2d c\+\+", regex=True, case=False
        ).sum()
        count_3d = df_pupil[c_p_m[0]].astype(str).str.contains(
            "pye3d", regex=True, case=False
        ).sum()
        metodo = "pye3d" if count_3d > count_2d else r"2d c\+\+"
        df_pupil = df_pupil[
            df_pupil[c_p_m[0]].astype(str).str.contains(metodo, regex=True, case=False, na=False)
        ]

    c_p_t = [c for c in df_pupil.columns if "timestamp" in c.lower()][0]
    c_p_wi = [c for c in df_pupil.columns if "world_index" in c.lower()][0]
    c_p_d_list = [c for c in df_pupil.columns if "diameter_3d" in c.lower()]
    if not c_p_d_list or df_pupil[c_p_d_list[0]].isna().all():
        c_p_d_list = [c for c in df_pupil.columns if "diameter" in c.lower()]
    c_p_d = c_p_d_list[0]

    meta_piloto = df_meta[df_meta["piloto"] == nome].iloc[0]
    t_sync_m = meta_piloto["t_sync_m"]

    df_pupil[c_p_t] = df_pupil[c_p_t].apply(force_float)
    df_pupil[c_p_d] = df_pupil[c_p_d].apply(limpa_diametro)
    df_pupil = df_pupil.dropna(subset=[c_p_t, c_p_d])

    from backend.database import SessionLocal
    from backend.db_ops import get_or_create_piloto as _get_piloto
    from backend.db_ops import get_or_create_sessao as _get_sessao
    from backend.models import ParametrosSync

    with SessionLocal() as _db:
        _sessao = _get_sessao(_db, sessao_nome)
        _piloto = _get_piloto(_db, nome)
        _params = _db.query(ParametrosSync).filter_by(
            sessao_id=_sessao.id, piloto_id=_piloto.id
        ).first()
        if not _params or _params.frame_sync is None:
            raise Exception(
                f"frame_sync ausente para '{nome}' na sessao '{sessao_nome}'. "
                "Execute sincronizacao.py antes."
            )
        frame_sync = _params.frame_sync

    print(f"   [{nome}] frame_sync lido do banco: {frame_sync}")
    t_sync_p = atirar_com_sniper(frame_sync, df_pupil, c_p_wi, c_p_t)

    t_raw = df_pupil[c_p_t].values.astype(float) - t_sync_p
    mediana_abs = np.nanmedian(np.abs(t_raw))
    if mediana_abs > 100_000:
        escala = 1_000_000.0
        print(f"   [{nome}] Pupila em us -> s")
    elif mediana_abs > 500:
        escala = 1_000.0
        print(f"   [{nome}] Pupila em ms -> s")
    else:
        escala = 1.0
        print(f"   [{nome}] Pupila ja em s")

    t_pupila = t_raw / escala
    diam_pupila = pd.Series(df_pupil[c_p_d].values).rolling(window=5, center=True).mean().values

    df_m = pd.read_csv(
        str(caminhos["motec"]),
        skiprows=14,
        sep=None,
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    df_m.columns = [str(c).strip() for c in df_m.columns]
    df_m["t_sync"] = clean_col(df_m, ["Time"]) - t_sync_m
    df_m["steer"] = clean_col(df_m, ["Steering Angle"])
    df_m["acel"] = clean_col(df_m, ["Throttle Pos"])
    df_m["freio"] = clean_col(df_m, ["Brake Pos"])
    df_m["lap_count"] = clean_col(df_m, ["Session Lap Count"])
    df_m = df_m.dropna(subset=["t_sync"])

    return df_m, t_pupila, diam_pupila, t_sync_m


def executar():
    validar_arquivos_base()
    if not os.path.exists(ARQUIVO_IDEAL):
        raise Exception("Rode o Codigo 1 primeiro.")
    if not os.path.exists(ARQUIVO_VOLTAS):
        raise Exception("Arquivo de metadados nao encontrado. Rode o Codigo 1 primeiro.")

    sessao_nome = input("Nome da sessao (deve coincidir com sincronizacao.py, ex: 'InterTatus'): ").strip() or "InterTatus"

    df_ideal = pd.read_csv(ARQUIVO_IDEAL)
    df_meta = pd.read_csv(ARQUIVO_VOLTAS)

    n_pontos_ideal = len(df_ideal)
    eixo_pct = np.linspace(0.0, 100.0, n_pontos_ideal)

    steering_medio = df_ideal["steering_medio"].values
    steering_sigma = df_ideal["steering_sigma"].values
    acel_medio = df_ideal["acel_medio"].values
    freio_medio = df_ideal["freio_medio"].values
    pupila_medio = df_ideal["pupila_medio"].values

    print(f"Baseline carregado: {n_pontos_ideal} pontos")
    print(f"Metadados: {len(df_meta)} volta(s) de {df_meta['piloto'].nunique()} piloto(s)")

    cores_tipo = {"A": "#e74c3c", "B": "#e67e22", "C": "#8e44ad"}
    labels_tipo = {"A": "Sinal Invertido", "B": "Desvio na Reta", "C": "Correcao Brusca"}

    todas_anomalias_registro = []
    imagens_geradas = 0

    for nome, caminhos in PILOTOS.items():
        if df_meta[df_meta["piloto"] == nome].empty:
            print(f"Nenhuma entrada de sincronizacao para {nome} nos metadados")
            continue

        print(f"\n{'=' * 60}")
        print(f"   CARREGANDO: {nome.upper()}")
        print(f"{'=' * 60}")

        df_m, t_pupila, diam_pupila, t_sync_m = carregar_piloto(nome, caminhos, df_meta, sessao_nome)

        lap_counts = sorted(df_m["lap_count"].dropna().unique())
        if len(lap_counts) > 1:
            lap_counts = lap_counts[:-1]
        else:
            lap_counts = []
        print(f"   Voltas encontradas (excl. ultima): {[int(lc) for lc in lap_counts]}")

        # Duracao mediana das voltas lancadas (lap > 0) — usada para cortar o trecho do grid da Volta 0
        duracoes_standard = []
        for lc in lap_counts:
            if int(lc) > 0:
                df_lc = df_m[df_m["lap_count"] == lc]
                if len(df_lc) >= 10:
                    duracoes_standard.append(
                        float(df_lc["t_sync"].max()) - float(df_lc["t_sync"].min())
                    )
        duracao_ref = float(np.median(duracoes_standard)) if duracoes_standard else None
        if duracao_ref is not None:
            print(f"   Duracao de referencia (mediana voltas 1+): {duracao_ref:.2f}s")

        for lap_count in lap_counts:
            volta_num = int(lap_count)
            df_v = df_m[df_m["lap_count"] == lap_count].sort_values("t_sync").reset_index(drop=True)
            t_ini = float(df_v["t_sync"].min())
            t_fim = float(df_v["t_sync"].max())

            print(f"\nVolta {volta_num}: {t_ini:.2f}s -> {t_fim:.2f}s")

            # Volta 0: o carro sai do grid (antes da linha de largada), gerando um trecho inicial
            # extra que nao existe nas outras voltas. Ancoramos pelo final (linha de chegada) e
            # descartamos tudo antes de t_corte, de modo que a Volta 0 passe a ter a mesma
            # duracao das voltas lancadas e o ponto zero coincida com a linha de largada/chegada.
            if volta_num == 0 and duracao_ref is not None:
                t_corte = t_fim - duracao_ref
                df_v = df_v[df_v["t_sync"] >= t_corte].reset_index(drop=True)
                t_ini = float(df_v["t_sync"].min())
                print(f"   Volta 0: trecho do grid descartado. Novo inicio: {t_ini:.2f}s "
                      f"(corte de {t_corte - (t_fim - duracao_ref - (t_ini - t_corte)):.2f}s mantidos)")

            mask_p = (t_pupila >= t_ini) & (t_pupila <= t_fim)

            if len(df_v) < 10:
                print(f"Poucos dados MoTeC ({len(df_v)} amostras) - pulando")
                continue

            t_pct_v = np.linspace(0, 100, len(df_v))
            steer_v = np.interp(eixo_pct, t_pct_v, df_v["steer"].values)
            acel_v  = np.interp(eixo_pct, t_pct_v, df_v["acel"].values)
            freio_v = np.interp(eixo_pct, t_pct_v, df_v["freio"].values)

            n_pup = mask_p.sum()
            if n_pup > 5:
                t_pct_pup = np.linspace(0, 100, n_pup)
                pup_v = np.interp(eixo_pct, t_pct_pup, diam_pupila[mask_p])
            else:
                pup_v = np.full(n_pontos_ideal, np.nan)
                print(f"Poucos dados de pupila ({n_pup} amostras) - pupila ausente nesta volta")

            anomalias, derivada = detectar_anomalias(steer_v, steering_medio, steering_sigma, eixo_pct)
            print(f"{len(anomalias)} anomalia(s) detectada(s)")

            for idx_a, anom in enumerate(anomalias):
                todas_anomalias_registro.append(
                    {
                        "piloto": nome,
                        "volta_num": volta_num,
                        "anom_num": idx_a + 1,
                        "tipo": anom["tipo"],
                        "ini_pct": anom["ini_pct"],
                        "fim_pct": anom["fim_pct"],
                        "t_ini_volta": t_ini,
                        "t_fim_volta": t_fim,
                        "t_sync_m": t_sync_m,
                    }
                )

            eh_reta = np.abs(steering_medio) < LIMIAR_RETA_GRAUS
            eh_curva = ~eh_reta

            fig = plt.figure(figsize=(20, 16))
            fig.suptitle(
                f"Volta {volta_num} - {nome} | {len(anomalias)} anomalia(s)",
                fontsize=14,
                fontweight="bold",
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
                eixo_pct,
                steering_medio - steering_sigma,
                steering_medio + steering_sigma,
                color="gray",
                alpha=0.15,
                label="+/-1sigma ideal",
            )
            ax_steer.plot(eixo_pct, steering_medio, color="gray", linewidth=2, linestyle="--", label="Ideal", zorder=4)
            ax_steer.plot(eixo_pct, steer_v, color="#2980b9", linewidth=1.5, label=f"{nome} - Volta {volta_num}", zorder=5)
            ax_steer.set_ylabel("Steering (graus)", fontsize=9)
            ax_steer.legend(loc="upper right", fontsize=7)
            ax_steer.grid(True, alpha=0.3)

            desvio_interp = steer_v - steering_medio
            ax_ideal.axhline(0, color="gray", linewidth=1, linestyle="--")
            ax_ideal.fill_between(eixo_pct, 0, desvio_interp, where=desvio_interp > 0, color="#e74c3c", alpha=0.4, label="Acima do ideal")
            ax_ideal.fill_between(eixo_pct, 0, desvio_interp, where=desvio_interp < 0, color="#3498db", alpha=0.4, label="Abaixo do ideal")
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

            labels_plotados = set()
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
                idx = np.argmin(np.abs(eixo_pct - meio))
                y = steer_v[idx]
                off = 15 if y >= 0 else -15
                ax_steer.annotate(
                    f"{anom['tipo']}{idx_a + 1}",
                    xy=(meio, y),
                    xytext=(meio, y + off),
                    fontsize=7,
                    color=cor,
                    fontweight="bold",
                    ha="center",
                    arrowprops=dict(arrowstyle="->", color=cor, lw=0.8),
                )

            ax_steer.legend(loc="upper right", fontsize=7)

            nome_arquivo = f"volta_{volta_num:02d}_{nome}.png"
            caminho_img = os.path.join(GRAFICOS_VOLTAS_DIR, nome_arquivo)
            plt.savefig(caminho_img, dpi=150, bbox_inches="tight")
            plt.close()
            imagens_geradas += 1
            print(f"Salvo: {nome_arquivo}")

    df_anom = pd.DataFrame(todas_anomalias_registro)
    df_anom.to_csv(ARQUIVO_ANOMALIAS, index=False)

    _persistir_banco_anomalias(todas_anomalias_registro, sessao_nome)

    print(f"\n{'=' * 60}")
    print(f"{imagens_geradas} imagem(ns) gerada(s) em: {GRAFICOS_VOLTAS_DIR}")
    print(f"{len(todas_anomalias_registro)} anomalia(s) registrada(s) em: {ARQUIVO_ANOMALIAS}")
    print(f"{'=' * 60}")


def _persistir_banco_anomalias(todas_anomalias_registro, sessao_nome="InterTatus"):
    try:
        from backend.database import SessionLocal
        from backend.db_ops import (
            get_or_create_piloto, get_or_create_sessao,
            upsert_volta, upsert_anomalia,
        )
        from backend.models import TracadoIdeal as TracadoIdealModel

        db = SessionLocal()
        try:
            sessao = get_or_create_sessao(db, sessao_nome)
            ti = db.query(TracadoIdealModel).filter_by(sessao_id=sessao.id).first()
            ti_id = ti.id if ti else None

            count = 0
            for rec in todas_anomalias_registro:
                piloto = get_or_create_piloto(db, rec["piloto"])
                t_ini = float(rec["t_ini_volta"])
                t_fim = float(rec["t_fim_volta"])
                volta = upsert_volta(
                    db, sessao.id, piloto.id,
                    numero_volta=int(rec["volta_num"]),
                    t_ini=t_ini,
                    t_fim=t_fim,
                    duracao=t_fim - t_ini,
                )
                upsert_anomalia(
                    db, volta.id,
                    numero_anomalia=int(rec["anom_num"]),
                    tipo=str(rec["tipo"]),
                    ini_pct=float(rec["ini_pct"]),
                    fim_pct=float(rec["fim_pct"]),
                    t_ini_s=t_ini,
                    t_fim_s=t_fim,
                    tracado_ideal_id=ti_id,
                )
                count += 1
            db.commit()
            print(f"✅ [DB] {count} anomalia(s) persistida(s).")
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  [DB] Falha ao persistir anomalias — análise não afetada. Erro: {e}")


def main():
    try:
        executar()
    except Exception as e:
        import traceback

        print(f"\nDEU RUIM: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
