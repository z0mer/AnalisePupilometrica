import io
import os
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

from codigos_tcc.configuracao import (
    ARQUIVO_ANOMALIAS,
    ARQUIVO_IDEAL,
    ARQUIVO_RELATORIO_TR,
    GRAFICOS_TR_DIR,
    GRAFICOS_VOLTAS_DIR,
    NIVEL_PILOTOS,
    PILOTOS,
    validar_arquivos_base,
)

# ── Parâmetros ─────────────────────────────────────────────────────────────────
PASTA_SAIDA_PDF = GRAFICOS_TR_DIR
PASTA_SAIDA_CSV_IND = GRAFICOS_TR_DIR
ARQUIVO_BASE_ANOVA = GRAFICOS_TR_DIR.parent / "base_consolidada_anova.csv"
JANELA_REACAO_SEG = 3.0
JANELA_POS_ANOMALIA_SEG = 2.0
LIMIAR_ONSET_PUPILA_MM = 0.5
LIMIAR_ONSET_PEDAL_PCT = 5.0
LIMIAR_ONSET_STEERING_GRAUS = 5.0

LIMIAR_FIXACAO_CURTA_MS = 100.0
LIMIAR_FIXACAO_LONGA_MS = 800.0
LIMIAR_PICO_DILATACAO_MM = 0.8
N_SETORES = 10

LABELS_TIPO = {
    "A": "Sinal Invertido (curva lado errado)",
    "B": "Desvio Excessivo na Reta",
    "C": "Correcao Brusca de Volante",
}
CORES_TIPO = {"A": "#e74c3c", "B": "#e67e22", "C": "#8e44ad"}


# ── Utilitários gerais ─────────────────────────────────────────────────────────

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
    idx = (df[col_wi] - frame_alvo).abs().idxmin()
    return force_float(df.loc[idx, col_t])


def clean_col(df, name_list):
    for name in name_list:
        target = [c for c in df.columns if c.lower() == name.lower()]
        if not target:
            target = [c for c in df.columns if name.lower() in c.lower()]
        if target:
            return pd.to_numeric(
                df[target[0]].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
    return None


def encontrar_onset(t_sinal, v_sinal, t_ref, janela_seg, limiar):
    mask = (t_sinal >= t_ref - janela_seg) & (t_sinal <= t_ref)
    if mask.sum() < 3:
        return None
    t_j = t_sinal[mask]
    v_j = v_sinal[mask]
    n_base = max(1, int(len(v_j) * 0.2))
    baseline = np.nanmean(v_j[:n_base])
    for i in range(len(v_j) - 1, -1, -1):
        if abs(v_j[i] - baseline) <= limiar:
            return t_j[i]
    return t_j[0]


def pct_para_tempo_real(pct_alvo, t_ini_volta, t_fim_volta):
    return t_ini_volta + (pct_alvo / 100.0) * (t_fim_volta - t_ini_volta)


def fig_para_bytes(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=130, bbox_inches="tight")
    buffer.seek(0)
    return buffer


def _fmt(v, sufixo=""):
    return f"{v:.3f}{sufixo}" if (v is not None and not np.isnan(v)) else "N/D"


# ── Carregamento Pupil Labs ────────────────────────────────────────────────────

def inferir_contexto_pista(tipo: str, s_window) -> str:
    if tipo == "A":
        return "Curva"
    if tipo == "B":
        return "Reta"
    if s_window is not None and len(s_window) > 0:
        return "Curva" if np.nanmean(np.abs(s_window)) > 15.0 else "Reta"
    return "Indefinido"


_COLUNAS_ANOVA = {
    # Identificação e contexto
    "t_anom_ini":                "Timestamp",
    "piloto":                    "ID_Piloto",
    "nivel_piloto":              "Nivel_Piloto",
    "volta_num":                 "Volta",
    "tipo":                      "Tipo_Anomalia",
    "contexto_pista":            "Contexto_Pista",
    "duracao_anom":              "Duracao_Anomalia_s",
    # Dimensões da pupila (Goals 3 e 4)
    "diam_antes_mm":             "Diam_Antes_mm",
    "diam_durante_mm":           "Diam_Durante_mm",
    "diam_depois_mm":            "Diam_Depois_mm",
    "delta_diam_mm":             "Delta_Diam_mm",
    "tipo_resposta_pupilar":     "Tipo_Resposta_Pupilar",
    # Tempos de reação (Goals 1 e 2)
    "TR_pupila_s":               "TR_Pupila_s",
    "TR_steering_s":             "TR_Steering_s",
    "TR_acelerador_s":           "TR_Acelerador_s",
    "TR_freio_s":                "TR_Freio_s",
    "primeiro_sinal":            "Primeiro_Sinal",
    # Picos de esforço cognitivo (Goal 5)
    "n_picos_cognitivos_janela": "N_Picos_Cognitivos",
    "intensidade_media_picos":   "Intensidade_Media_Picos",
    # Métricas de fixação (co-variáveis comportamentais)
    "n_fixacoes_janela":         "N_Fixacoes",
    "dur_media_fix_ms":          "Dur_Media_Fixacao_ms",
    "fix_curtas":                "Fix_Curtas",
    "fix_longas":                "Fix_Longas",
    "comportamento_visual":      "Comportamento_Visual",
    # Novas métricas para ANOVA
    "tempo_reacao_pupilar_s":       "Tempo_Reacao_Pupilar_s",
    "media_tamanho_pupilar":        "Media_Tamanho_Pupilar",
    "crescimento_pupilar_derivada": "Crescimento_Pupilar_Derivada",
    "tempo_no_escuro_s":            "Tempo_No_Escuro_s",
    "distancia_no_escuro_m":        "Distancia_No_Escuro_m",
}


def salvar_csv_individual(nome: str, todos_registros: list, pasta) -> str:
    registros_piloto = [r for r in todos_registros if r.get("piloto") == nome]
    if not registros_piloto:
        return ""
    nivel = NIVEL_PILOTOS.get(nome, "Amador")
    for r in registros_piloto:
        r["nivel_piloto"] = nivel
    df_fonte = pd.DataFrame(registros_piloto)
    colunas_presentes = {k: v for k, v in _COLUNAS_ANOVA.items() if k in df_fonte.columns}
    df = df_fonte[list(colunas_presentes.keys())].rename(columns=colunas_presentes)
    caminho = str(Path(pasta) / f"CSV_{nome}.csv")
    df.to_csv(caminho, index=False, encoding="utf-8")
    print(f"  CSV individual salvo: {caminho}")
    return caminho


def consolidar_csvs_anova(caminhos_csv: list, arquivo_saida) -> None:
    dfs = [pd.read_csv(str(p)) for p in caminhos_csv if p and Path(p).exists()]
    if dfs:
        pd.concat(dfs, ignore_index=True).to_csv(str(arquivo_saida), index=False, encoding="utf-8")
        print(f"\nBase consolidada ANOVA salva: {arquivo_saida}")


def carregar_world_timestamps(caminho_wt):
    """Load world_timestamps.csv → DataFrame(ts_s, frame_idx)."""
    try:
        df = pd.read_csv(str(caminho_wt))
        col_ts = df.columns[0]
        col_pts = df.columns[1] if len(df.columns) > 1 else None
        out = pd.DataFrame()
        out["ts_s"] = pd.to_numeric(df[col_ts], errors="coerce")
        out["frame_idx"] = (
            pd.to_numeric(df[col_pts], errors="coerce")
            if col_pts else pd.Series(range(len(df)))
        )
        return out.dropna(subset=["ts_s"]).reset_index(drop=True)
    except Exception as exc:
        print(f"  Aviso world_timestamps: {exc}")
        return pd.DataFrame(columns=["ts_s", "frame_idx"])


def carregar_fixacoes(caminho_fix, t_sync_p, escala):
    """Load fixations.csv, sync timestamps → DataFrame(t_sync, duration_ms, norm_x, norm_y, confidence, dispersion)."""
    try:
        df = pd.read_csv(str(caminho_fix), sep=None, engine="python", on_bad_lines="skip")
        df.columns = [str(c).strip() for c in df.columns]

        col_ts = next(
            (c for c in df.columns if "start_timestamp" in c.lower()),
            next((c for c in df.columns if "timestamp" in c.lower()), None),
        )
        if col_ts is None:
            print("  Aviso: coluna timestamp ausente em fixations.csv")
            return pd.DataFrame(columns=["t_sync", "duration_ms", "norm_x", "norm_y", "confidence", "dispersion"])

        col_dur = next((c for c in df.columns if "duration" in c.lower()), None)
        col_x = next((c for c in df.columns if "norm_pos_x" in c.lower()), None)
        col_y = next((c for c in df.columns if "norm_pos_y" in c.lower()), None)
        col_conf = next((c for c in df.columns if "confidence" in c.lower()), None)
        col_disp = next((c for c in df.columns if "dispersion" in c.lower()), None)

        ts_raw = pd.to_numeric(df[col_ts].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        out = pd.DataFrame()
        out["t_sync"] = (ts_raw - t_sync_p) / escala

        if col_dur is not None:
            dur_raw = pd.to_numeric(df[col_dur].astype(str).str.replace(",", ".", regex=False), errors="coerce")
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
        print(f"  Aviso fixations: {exc}")
        return pd.DataFrame(columns=["t_sync", "duration_ms", "norm_x", "norm_y", "confidence", "dispersion"])


def carregar_blinks(caminho_blinks, t_sync_p, escala):
    """Load blinks.csv, sync timestamps → DataFrame(t_ini, t_fim, duracao_s, confidence)."""
    try:
        df = pd.read_csv(str(caminho_blinks), sep=None, engine="python", on_bad_lines="skip")
        df.columns = [str(c).strip() for c in df.columns]
        col_ini = next((c for c in df.columns if "start_timestamp" in c.lower()), None)
        col_fim = next((c for c in df.columns if "end_timestamp" in c.lower()), None)
        col_dur = next((c for c in df.columns if "duration" in c.lower()), None)
        col_conf = next((c for c in df.columns if "confidence" in c.lower()), None)
        if col_ini is None:
            print("  Aviso: coluna start_timestamp ausente em blinks.csv")
            return pd.DataFrame(columns=["t_ini", "t_fim", "duracao_s", "confidence"])
        ts_ini = pd.to_numeric(df[col_ini].astype(str).str.replace(",", ".", regex=False), errors="coerce")
        out = pd.DataFrame()
        out["t_ini"] = (ts_ini - t_sync_p) / escala
        if col_fim is not None:
            ts_fim = pd.to_numeric(df[col_fim].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            out["t_fim"] = (ts_fim - t_sync_p) / escala
        elif col_dur is not None:
            dur_raw = pd.to_numeric(df[col_dur].astype(str).str.replace(",", ".", regex=False), errors="coerce")
            med = dur_raw.dropna().median()
            dur_s = dur_raw / 1000.0 if (not np.isnan(med) and med > 10) else dur_raw
            out["t_fim"] = out["t_ini"] + dur_s
        else:
            out["t_fim"] = out["t_ini"] + 0.3
        out["duracao_s"] = out["t_fim"] - out["t_ini"]
        out["confidence"] = pd.to_numeric(df[col_conf], errors="coerce") if col_conf else np.nan
        return out.dropna(subset=["t_ini"]).reset_index(drop=True)
    except Exception as exc:
        print(f"  Aviso blinks: {exc}")
        return pd.DataFrame(columns=["t_ini", "t_fim", "duracao_s", "confidence"])


# ── Análise de fixações ────────────────────────────────────────────────────────

def filtrar_fixacoes_janela(df_fix, t_ini, t_fim):
    if df_fix.empty or "t_sync" not in df_fix.columns:
        return pd.DataFrame(columns=df_fix.columns if not df_fix.empty else ["t_sync"])
    return df_fix[(df_fix["t_sync"] >= t_ini) & (df_fix["t_sync"] <= t_fim)].copy()


def estatisticas_fixacao(df_fix):
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


def classificar_comportamento_fixacao(stats):
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


# ── Estatísticas globais ───────────────────────────────────────────────────────

def _estatisticas_globais(lista_anomalias_dados):
    from collections import Counter
    if not lista_anomalias_dados:
        return {}

    def _safe_vals(chave):
        return [
            d[chave] for d in lista_anomalias_dados
            if chave in d and d[chave] is not None and not np.isnan(d[chave])
        ]

    tipos = [d["tipo"] for d in lista_anomalias_dados]
    deltas = _safe_vals("delta_diam")
    durs = [d["duracao_anom"] for d in lista_anomalias_dados]
    primeiros = [d.get("primeiro_sinal") for d in lista_anomalias_dados if d.get("primeiro_sinal")]
    mais_freq = Counter(primeiros).most_common(1)
    trs_s = _safe_vals("TR_steering_s")
    trs_p = _safe_vals("TR_pupila_s")

    return {
        "total": len(lista_anomalias_dados),
        "por_tipo": dict(Counter(tipos)),
        "dur_media": float(np.nanmean(durs)) if durs else np.nan,
        "dur_max": float(np.nanmax(durs)) if durs else np.nan,
        "dur_min": float(np.nanmin(durs)) if durs else np.nan,
        "delta_medio": float(np.nanmean(deltas)) if deltas else np.nan,
        "n_dilatacoes": sum(1 for v in deltas if v > 0),
        "n_contracoes": sum(1 for v in deltas if v < 0),
        "primeiro_sinal_mais_freq": mais_freq[0][0] if mais_freq else "N/D",
        "n_fixacoes_total_anomalias": sum(
            d.get("stats_fixacao", {}).get("n_fixacoes", 0) for d in lista_anomalias_dados
        ),
        "voltas_afetadas": sorted({d["volta_num"] for d in lista_anomalias_dados}),
        "tr_steering_medio": float(np.nanmean(trs_s)) if trs_s else np.nan,
        "tr_pupila_medio": float(np.nanmean(trs_p)) if trs_p else np.nan,
    }


# ── Textos analíticos para o PDF ───────────────────────────────────────────────

def _analise_perfil_pupilar_texto(perfis_por_volta, picos_cognitivos, e_analise):
    from reportlab.platypus import Paragraph

    paragrafos = []

    if not picos_cognitivos:
        paragrafos.append(Paragraph(
            "<b>Picos de Dilatacao Pupilar:</b> Nenhum pico de dilatacao significativo "
            f"(acima de {LIMIAR_PICO_DILATACAO_MM:.1f}mm em relacao a mediana movel) foi "
            "identificado na sessao analisada, o que pode indicar ausencia de estressores "
            "cognitivos proeminentes ou limitacao na resolucao dos dados.",
            e_analise,
        ))
    else:
        n_p = len(picos_cognitivos)
        paragrafos.append(Paragraph(
            f"<b>Picos de Dilatacao Pupilar:</b> Ao longo da sessao, foram detectados "
            f"<b>{n_p} pico(s)</b> de dilatacao pupilar acima do limiar de "
            f"{LIMIAR_PICO_DILATACAO_MM:.1f}mm em relacao a mediana movel. Esse padrao "
            "pode indicar momentos de elevada carga cognitiva ou resposta de alerta "
            "durante a conducao.",
            e_analise,
        ))

    if perfis_por_volta:
        medias_por_setor = [[] for _ in range(N_SETORES)]
        for perfil in perfis_por_volta:
            for item in perfil:
                idx = item["setor"] - 1
                if not np.isnan(item["media"]):
                    medias_por_setor[idx].append(item["media"])
        pct_centros = [(s + 0.5) * (100 / N_SETORES) for s in range(N_SETORES)]
        medias_agg = [np.mean(v) if v else np.nan for v in medias_por_setor]
        validas = [(i, m) for i, m in enumerate(medias_agg) if not np.isnan(m)]

        if validas:
            s_max = max(validas, key=lambda x: x[1])
            s_min = min(validas, key=lambda x: x[1])
            amplitude = s_max[1] - s_min[1]
            variab_str = "alta variabilidade pupilar ao longo da pista" if amplitude > 0.5 else "variacao moderada entre setores"
            pct_max_ini = s_max[0] * (100 / N_SETORES)
            pct_max_fim = (s_max[0] + 1) * (100 / N_SETORES)
            paragrafos.append(Paragraph(
                f"<b>Perfil Pupilar por Setor:</b> O perfil medio revela diametro mais "
                f"elevado no Setor {s_max[0]+1} ({pct_max_ini:.0f}%–{pct_max_fim:.0f}% da pista, "
                f"media={s_max[1]:.3f}mm) e o menor diametro no Setor {s_min[0]+1} "
                f"(media={s_min[1]:.3f}mm). A amplitude de variacao entre setores foi de "
                f"{amplitude:.3f}mm, indicando {variab_str}.",
                e_analise,
            ))
        else:
            paragrafos.append(Paragraph(
                "<b>Perfil Pupilar por Setor:</b> Dados insuficientes para calcular o perfil por setor.",
                e_analise,
            ))

    if len(perfis_por_volta) > 1:
        paragrafos.append(Paragraph(
            f"<b>Consistencia entre Voltas:</b> O perfil foi calculado com base em "
            f"{len(perfis_por_volta)} volta(s). A consistencia do padrao entre voltas "
            "pode indicar estabilidade na resposta pupilar ao longo da sessao ou, se "
            "houver divergencia, variabilidade situacional associada ao estado do piloto.",
            e_analise,
        ))

    return paragrafos


def _analise_fixacoes_texto(df_fix_v, stats_fix, e_analise):
    from reportlab.platypus import Paragraph

    n = stats_fix.get("n_fixacoes", 0)
    if n == 0:
        return [Paragraph(
            "Nao foram registradas fixacoes nesta volta ou os dados nao estao disponiveis.",
            e_analise,
        )]

    dur_media = stats_fix.get("dur_media_ms", np.nan)
    n_curtas = stats_fix.get("n_curtas", 0)
    n_longas = stats_fix.get("n_longas", 0)
    pct_curtas = n_curtas / n * 100
    pct_longas = n_longas / n * 100
    comportamento = classificar_comportamento_fixacao(stats_fix)

    dur_str = f"A duracao media foi de <b>{dur_media:.0f}ms</b>. " if not np.isnan(dur_media) else ""
    p1 = Paragraph(
        f"<b>Resumo de Fixacoes:</b> Nesta volta foram registradas <b>{n} fixacao(oes)</b> oculares. "
        f"{dur_str}"
        f"Das fixacoes, <b>{pct_curtas:.0f}%</b> foram curtas (&lt;{LIMIAR_FIXACAO_CURTA_MS:.0f}ms) "
        f"e <b>{pct_longas:.0f}%</b> foram longas (&gt;{LIMIAR_FIXACAO_LONGA_MS:.0f}ms).",
        e_analise,
    )

    interp_map = {
        "Busca visual dispersa (muitas fixacoes curtas)":
            "Fixacoes curtas em alta frequencia indicam busca visual ativa, possivelmente "
            "associada a incerteza ou sobrecarga de informacoes.",
        "Visao em tunel (fixacoes excessivamente longas)":
            "Fixacoes longas excessivas podem indicar visao em tunel, com reducao da "
            "varredura do ambiente visual e potencial perda de informacoes perifericas.",
        "Exploracao visual normal":
            "O padrao de exploracao visual encontra-se dentro dos parametros esperados "
            "para conducao sob demanda moderada.",
    }
    interp = interp_map.get(comportamento, "O padrao misto nao permite classificacao definitiva.")
    p2 = Paragraph(
        f"<b>Interpretacao:</b> Classificacao: <i>{comportamento}</i>. {interp}",
        e_analise,
    )

    return [p1, p2]


def _analise_anomalia_texto(d, e_analise):
    from reportlab.platypus import Paragraph

    tipo = d.get("tipo", "?")
    volta_num = d.get("volta_num", "?")
    anom_num = d.get("anom_num", "?")
    ini_pct = d.get("ini_pct", np.nan)
    fim_pct = d.get("fim_pct", np.nan)
    dur_anom = d.get("duracao_anom", np.nan)
    primeiro_sinal = d.get("primeiro_sinal") or "N/D"
    ordem_reacao = d.get("ordem_reacao", "N/D")

    delta_d = d.get("delta_diam", np.nan)
    d_antes = d.get("diam_antes", np.nan)
    d_durante = d.get("diam_durante", np.nan)
    d_depois = d.get("diam_depois", np.nan)

    tr_p = d.get("TR_pupila_s", np.nan)
    tr_s = d.get("TR_steering_s", np.nan)
    tr_a = d.get("TR_acelerador_s", np.nan)
    tr_f = d.get("TR_freio_s", np.nan)

    stats_fix = d.get("stats_fixacao", {})
    n_fix = stats_fix.get("n_fixacoes", 0)
    comportamento = d.get("comportamento_visual", "N/D")

    pos_str = (
        f"{ini_pct:.1f}%–{fim_pct:.1f}%"
        if not (np.isnan(ini_pct) or np.isnan(fim_pct))
        else "N/D"
    )
    p1 = Paragraph(
        f"<b>Contexto:</b> Anomalia do tipo <b>{tipo}</b> ({LABELS_TIPO.get(tipo, tipo)}) "
        f"na Volta {volta_num}, entre <b>{pos_str}</b> da pista, duracao de "
        f"<b>{_fmt(dur_anom, 's')}</b>. Primeiro sinal detectado: <b>{primeiro_sinal}</b>. "
        f"Sequencia de resposta: <b>{ordem_reacao}</b>.",
        e_analise,
    )

    if not np.isnan(delta_d) and abs(delta_d) > 0.3:
        if delta_d > 0:
            delta_interp = (
                f"dilatacao pupilar de <b>{_fmt(delta_d, 'mm')}</b>, o que pode estar "
                "associado a aumento de carga cognitiva ou resposta de alerta"
            )
        else:
            delta_interp = (
                f"contracao pupilar de <b>{_fmt(delta_d, 'mm')}</b>"
            )
    else:
        delta_interp = "sem variacao pupilar expressiva detectada (delta &lt; 0,3mm)"

    vel_str = ""
    if (tr_p is not None and not np.isnan(tr_p) and tr_p != 0.0 and
            not np.isnan(delta_d)):
        vel_pupilar = abs(delta_d) / abs(tr_p)
        vel_str = f" A velocidade de resposta pupilar estimada foi de <b>{vel_pupilar:.3f}mm/s</b>."

    recup_str = ""
    if not (np.isnan(d_depois) or np.isnan(d_durante)):
        recup = d_depois - d_durante
        if recup > 0.1:
            recup_str = (
                f" Recuperacao pupilar pos-anomalia: <b>{recup:+.3f}mm</b>, "
                "sugerindo retorno progressivo ao estado basal."
            )
        elif recup < -0.1:
            recup_str = (
                f" Recuperacao pupilar pos-anomalia: <b>{recup:+.3f}mm</b>, "
                "indicando manutencao da ativacao fisiologica."
            )

    p2 = Paragraph(
        f"<b>Resposta Pupilar:</b> Diametro medio antes: <b>{_fmt(d_antes, 'mm')}</b> | "
        f"durante: <b>{_fmt(d_durante, 'mm')}</b> | apos: <b>{_fmt(d_depois, 'mm')}</b>. "
        f"Variacao (delta): {delta_interp}.{vel_str}{recup_str}",
        e_analise,
    )

    todos_tr_nan = all(
        v is None or np.isnan(v) for v in [tr_s, tr_a, tr_f, tr_p]
    )
    if todos_tr_nan:
        p3 = Paragraph(
            "<b>Tempos de Reacao:</b> Nao foi possivel calcular os tempos de reacao "
            "para esta anomalia.",
            e_analise,
        )
    else:
        p3 = Paragraph(
            f"<b>Tempos de Reacao</b> (relativos ao primeiro sinal): "
            f"Steering={_fmt(tr_s, 's')} | "
            f"Acelerador={_fmt(tr_a, 's')} | "
            f"Freio={_fmt(tr_f, 's')} | "
            f"Pupila={_fmt(tr_p, 's')}. "
            "Valores negativos indicam antecipacao ao sinal principal; "
            "valores proximos de zero indicam reacao simultanea.",
            e_analise,
        )

    interp_fix_map = {
        "Busca visual dispersa (muitas fixacoes curtas)":
            "Esse padrao pode estar associado a busca ativa de referencias visuais "
            "durante situacao de incerteza ou sobrecarga.",
        "Visao em tunel (fixacoes excessivamente longas)":
            "Fixacoes excessivamente longas podem refletir foco intenso em elemento "
            "especifico, com reducao da varredura periferica.",
        "Exploracao visual normal":
            "O comportamento visual sugere manutencao da atencao distribuida "
            "durante o evento.",
    }
    if n_fix > 0:
        interp_fix = interp_fix_map.get(comportamento, "")
        fix_interp_str = f" {interp_fix}" if interp_fix else ""
        p4 = Paragraph(
            f"<b>Comportamento Visual:</b> {n_fix} fixacao(oes) registradas na janela "
            f"de analise. Classificacao: <i>{comportamento}</i>.{fix_interp_str}",
            e_analise,
        )
    else:
        p4 = Paragraph(
            "<b>Comportamento Visual:</b> Nenhuma fixacao registrada na janela de analise "
            "desta anomalia.",
            e_analise,
        )

    return [p1, p2, p3, p4]


# ── Análise pupilar ────────────────────────────────────────────────────────────

def detectar_picos_pupila(t_pupila, diam_pupila, janela=15):
    """Detect sudden dilation spikes above LIMIAR_PICO_DILATACAO_MM over rolling median."""
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


def calcular_crescimento_pupilar_derivada(t_pupila, diam_pupila, t_ini, t_fim):
    """Return max positive derivative (mm/s) of the pupil signal during the anomaly window."""
    mask = (t_pupila >= t_ini) & (t_pupila <= t_fim)
    if mask.sum() < 3:
        return np.nan
    t_seg = t_pupila[mask]
    d_seg = diam_pupila[mask]
    dt = np.diff(t_seg)
    dt[dt == 0] = np.nan
    derivadas = np.diff(d_seg) / dt
    valid = derivadas[~np.isnan(derivadas)]
    if len(valid) == 0:
        return np.nan
    return float(np.nanmax(valid))


def calcular_metricas_blinks(df_blinks, t_jan_ini, t_jan_fim, t_motec, vel_ms):
    """Return (tempo_total_s, distancia_total_m) for blinks overlapping the analysis window."""
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


def calcular_perfil_pupilar_por_setor(t_pupila, diam_pupila, t_ini_volta, t_fim_volta):
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


# ── Gráficos ───────────────────────────────────────────────────────────────────

def gerar_grafico_anomalia(
    nome, tipo, volta_num, anom_num,
    t_m_jan, s_jan, a_jan, f_jan,
    t_p_jan, d_jan,
    t_anom_ini, t_anom_fim,
    df_fix_janela,
    eixo_pct, steer_med, ini_pct, fim_pct,
    t_jan_ini, t_jan_fim,
    onsets_validos, ordem_reacao, primeiro_sinal,
    d_antes, delta_d,
    cor,
    steer_sigma=None,
):
    """
    Gráfico de anomalia individual com 4 painéis (de cima para baixo):
      1. Média x Volta — steering piloto vs ideal (±1σ) + marcadores de TR
      2. Desvio         — delta em relação ao ideal
      3. Pupila         — diâmetro suavizado + fixações
      4. Pedais         — acelerador e freio
    """
    cores_onset = {
        "Steering": "#2980b9",
        "Acelerador": "#e67e22",
        "Freio": "#27ae60",
        "Pupila": "#8e44ad",
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
    ax_pup    = fig.add_subplot(gs[2], sharex=ax_steer)
    ax_pedal  = fig.add_subplot(gs[3], sharex=ax_steer)

    # ── Painel 1: Média x Volta (steering piloto vs ideal) ───────────────────
    steer_ideal_interp = None
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
        if t_primeiro is not None and sinal != primeiro_sinal:
            s_min = np.nanmin(s_jan)
            y_seta = s_min * 0.85 if s_min < 0 else 5.0
            ax_steer.annotate(
                "",
                xy=(t_on, y_seta), xytext=(t_primeiro, y_seta),
                arrowprops=dict(arrowstyle="<->", color=cores_onset[sinal], lw=1.2),
            )
            ax_steer.text(
                (t_on + t_primeiro) / 2, y_seta * 1.15,
                f"TR={tr:+.3f}s", fontsize=6, color=cores_onset[sinal],
                ha="center", fontweight="bold",
            )

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
        n_fix = len(df_fix_janela) if not df_fix_janela.empty else 0
        sinal_d = "+" if (not np.isnan(delta_d) and delta_d > 0) else ""
        reacao_p = "dilatou" if (not np.isnan(delta_d) and delta_d > 0) else "contraiu"
        titulo_pup = "Pupila"
        if not np.isnan(delta_d):
            titulo_pup += f" | Delta={sinal_d}{delta_d:.2f}mm ({reacao_p})"
        titulo_pup += f" | {n_fix} fixacao(oes)"
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

    partes_caption = []
    if not np.isnan(delta_d):
        sinal_c = "+" if delta_d > 0 else ""
        partes_caption.append(f"ΔPupila={sinal_c}{delta_d:.3f}mm")
    n_fix_cap = len(df_fix_janela) if not df_fix_janela.empty else 0
    partes_caption.append(f"Fixacoes={n_fix_cap}")
    if t_primeiro is not None:
        for sinal_on, t_on in onsets_validos.items():
            tr_val = t_on - t_primeiro
            partes_caption.append(f"TR_{sinal_on}={tr_val:+.3f}s")
    if partes_caption:
        fig.text(0.5, 0.01, "  |  ".join(partes_caption),
                 ha="center", va="bottom", fontsize=7, color="#555555", style="italic")

    fb = fig_para_bytes(fig)
    plt.close(fig)
    return fb


def gerar_grafico_perfil_pupilar(nome, perfis_por_volta, t_pupila_total, diam_pupila_total, picos):
    if not perfis_por_volta:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    fig.suptitle(f"Perfil Pupilar - {nome}", fontsize=12, fontweight="bold")

    # Aggregate per-sector across all laps
    medias_por_setor = [[] for _ in range(N_SETORES)]
    for perfil in perfis_por_volta:
        for item in perfil:
            idx = item["setor"] - 1
            if not np.isnan(item["media"]):
                medias_por_setor[idx].append(item["media"])

    pct_centros = [(s + 0.5) * (100 / N_SETORES) for s in range(N_SETORES)]
    medias_agg = [np.mean(v) if v else np.nan for v in medias_por_setor]
    desvios_agg = [np.std(v) if len(v) > 1 else 0.0 for v in medias_por_setor]

    ax1 = axes[0]
    bars = ax1.bar(pct_centros, medias_agg, width=100 / N_SETORES * 0.8,
                   color="#8e44ad", alpha=0.7, label="Diâmetro médio")
    ax1.errorbar(pct_centros, medias_agg, yerr=desvios_agg,
                 fmt="none", color="black", capsize=4, linewidth=1.2)
    ax1.set_xlabel("Progresso na Pista (%)", fontsize=9)
    ax1.set_ylabel("Diâmetro Pupilar (mm)", fontsize=9)
    ax1.set_title("Perfil Pupilar Médio por Setor (média entre voltas)", fontsize=10)
    ax1.set_xlim(0, 100)
    ax1.grid(True, alpha=0.3, axis="y")
    ax1.legend(fontsize=8)

    validas_agg = [(i, m) for i, m in enumerate(medias_agg) if not np.isnan(m)]
    if validas_agg:
        idx_max = max(validas_agg, key=lambda x: x[1])
        idx_min = min(validas_agg, key=lambda x: x[1])
        ax1.annotate(
            f"Max\n{idx_max[1]:.3f}mm",
            xy=(pct_centros[idx_max[0]], idx_max[1]),
            xytext=(0, 10), textcoords="offset points",
            ha="center", fontsize=7, color="#8e44ad", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#8e44ad", lw=0.8),
        )
        ax1.annotate(
            f"Min\n{idx_min[1]:.3f}mm",
            xy=(pct_centros[idx_min[0]], idx_min[1]),
            xytext=(0, 10), textcoords="offset points",
            ha="center", fontsize=7, color="#2980b9", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#2980b9", lw=0.8),
        )

    # Timeline with spikes
    ax2 = axes[1]
    if len(t_pupila_total) > 1:
        ax2.plot(t_pupila_total, diam_pupila_total, color="purple", linewidth=0.8,
                 alpha=0.6, label="Pupila")
        series_d = pd.Series(diam_pupila_total)
        bl = series_d.rolling(window=50, center=True, min_periods=3).median().values
        ax2.plot(t_pupila_total, bl, color="gray", linewidth=1.2, linestyle="--",
                 alpha=0.8, label="Mediana móvel")
        if picos:
            t_p = [p[0] for p in picos]
            d_p = []
            for tp in t_p:
                idx_near = int(np.argmin(np.abs(t_pupila_total - tp)))
                d_p.append(diam_pupila_total[idx_near])
            ax2.scatter(t_p, d_p, color="red", s=45, zorder=6, marker="^",
                        label=f"Picos cognitivos ({len(picos)})")
    ax2.set_xlabel("Tempo Sincronizado (s)", fontsize=9)
    ax2.set_ylabel("Diâmetro Pupilar (mm)", fontsize=9)
    ax2.set_title("Linha do Tempo Pupilar com Picos de Estresse Cognitivo", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    fb = fig_para_bytes(fig)
    plt.close(fig)
    return fb


def gerar_grafico_fixacoes_volta(nome, df_fix_sync, t_ini_volta, t_fim_volta, volta_num):
    if df_fix_sync.empty or "t_sync" not in df_fix_sync.columns:
        return None
    dur = t_fim_volta - t_ini_volta
    if dur <= 0:
        return None
    mask = (df_fix_sync["t_sync"] >= t_ini_volta) & (df_fix_sync["t_sync"] <= t_fim_volta)
    df_v = df_fix_sync[mask].copy()
    if df_v.empty:
        return None
    df_v["pct_pista"] = (df_v["t_sync"] - t_ini_volta) / dur * 100.0

    stats_v = estatisticas_fixacao(df_v)
    n_fix_v = stats_v.get("n_fixacoes", 0)
    dur_m_v = stats_v.get("dur_media_ms", np.nan)
    dur_str_t = f" | Dur. media: {dur_m_v:.0f}ms" if not np.isnan(dur_m_v) else ""

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7))
    fig.suptitle(
        f"Analise de Fixacoes - {nome} - Volta {volta_num} | {n_fix_v} fixacao(oes){dur_str_t}",
        fontsize=11, fontweight="bold",
    )

    # Scatter mapa de fixações
    durs_clip = df_v["duration_ms"].clip(20, 1000) if "duration_ms" in df_v.columns else pd.Series([50] * len(df_v))
    norm_y_col = df_v["norm_y"] if "norm_y" in df_v.columns else pd.Series([0.5] * len(df_v))
    sc = ax1.scatter(
        df_v["pct_pista"], norm_y_col,
        c=df_v["duration_ms"] if "duration_ms" in df_v.columns else durs_clip,
        cmap="YlOrRd", s=durs_clip / 5, alpha=0.75,
        edgecolors="gray", linewidths=0.3,
    )
    plt.colorbar(sc, ax=ax1, label="Duração (ms)")
    ax1.set_xlabel("Progresso na Pista (%)", fontsize=9)
    ax1.set_ylabel("Posição Y normalizada", fontsize=9)
    ax1.set_title("Mapa de Fixações por Setor (tamanho e cor = duração)", fontsize=10)
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 1)
    ax1.grid(True, alpha=0.3)

    # Histograma de durações
    if "duration_ms" in df_v.columns:
        durs = df_v["duration_ms"].dropna()
        if len(durs) > 0:
            ax2.hist(durs, bins=min(30, len(durs)), color="#8e44ad", alpha=0.7,
                     edgecolor="white", linewidth=0.5)
            ax2.axvline(LIMIAR_FIXACAO_CURTA_MS, color="red", linestyle="--", linewidth=1.5,
                        label=f"Limite curta ({LIMIAR_FIXACAO_CURTA_MS:.0f}ms)")
            ax2.axvline(LIMIAR_FIXACAO_LONGA_MS, color="orange", linestyle="--", linewidth=1.5,
                        label=f"Limite longa ({LIMIAR_FIXACAO_LONGA_MS:.0f}ms)")
            ax2.axvline(float(durs.mean()), color="blue", linestyle="-", linewidth=1.5,
                        label=f"Média: {durs.mean():.0f}ms")
            ax2.set_xlabel("Duração da Fixação (ms)", fontsize=9)
            ax2.set_ylabel("Frequência", fontsize=9)
            ax2.set_title("Distribuição de Duração das Fixações", fontsize=10)
            ax2.legend(fontsize=8)
            ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    fb = fig_para_bytes(fig)
    plt.close(fig)
    return fb


# ── Geração do PDF ─────────────────────────────────────────────────────────────

def gerar_pdf_piloto(
    nome, lista_anomalias_dados, pasta_saida,
    perfis_por_volta, picos_cognitivos,
    t_pupila_total, diam_pupila_total,
    df_fix_sync, lista_voltas,
):
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    caminho_pdf = os.path.join(pasta_saida, f"Relatorio_TR_{nome}.pdf")
    doc = SimpleDocTemplate(
        caminho_pdf, pagesize=A4,
        rightMargin=1.5 * cm, leftMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )
    largura_pagina, _ = A4
    estilos = getSampleStyleSheet()

    e_titulo = ParagraphStyle("TituloDoc", parent=estilos["Title"],
        fontSize=18, textColor=colors.HexColor("#2c3e50"), spaceAfter=6, alignment=TA_CENTER)
    e_sub = ParagraphStyle("Subtitulo", parent=estilos["Heading2"],
        fontSize=11, textColor=colors.HexColor("#7f8c8d"), spaceAfter=4, alignment=TA_CENTER)
    e_sec = ParagraphStyle("Secao", parent=estilos["Heading1"],
        fontSize=13, textColor=colors.HexColor("#2980b9"), spaceBefore=14, spaceAfter=6)
    e_sec_cog = ParagraphStyle("SecaoCog", parent=estilos["Heading1"],
        fontSize=13, textColor=colors.HexColor("#8e44ad"), spaceBefore=14, spaceAfter=6)
    e_rodape = ParagraphStyle("Rodape", parent=estilos["Normal"],
        fontSize=7, textColor=colors.HexColor("#95a5a6"), alignment=TA_RIGHT)
    e_analise = ParagraphStyle("Analise", parent=estilos["Normal"],
        fontSize=9, leading=13, spaceAfter=4, spaceBefore=2,
        textColor=colors.HexColor("#2c3e50"))

    cor_tipo = {
        "A": colors.HexColor("#e74c3c"),
        "B": colors.HexColor("#e67e22"),
        "C": colors.HexColor("#8e44ad"),
    }

    historia = []

    glob = _estatisticas_globais(lista_anomalias_dados)
    voltas_afetadas = glob.get("voltas_afetadas", [])
    voltas_str = ", ".join(str(v) for v in voltas_afetadas) or "N/D"
    por_tipo = glob.get("por_tipo", {})

    # ── Capa ──────────────────────────────────────────────────────────────────
    historia.append(Spacer(1, 1.0 * cm))
    historia.append(Paragraph("Relatorio de Tempo de Reacao e Analise Pupilar", e_titulo))
    historia.append(Paragraph(f"Piloto: {nome}", e_sub))
    historia.append(Paragraph(
        f"Gerado em: {data_hora} | Anomalias: {len(lista_anomalias_dados)} | "
        f"Picos cognitivos detectados: {len(picos_cognitivos)}",
        e_sub,
    ))
    historia.append(HRFlowable(width="100%", thickness=2,
                                color=colors.HexColor("#2980b9"), spaceAfter=12))

    # ── Introdução ────────────────────────────────────────────────────────────
    historia.append(Paragraph("Introducao", e_sec))
    historia.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#2980b9"), spaceAfter=6))
    historia.append(Paragraph(
        f"Este relatorio apresenta a analise individualizada de anomalias de conducao "
        f"detectadas na sessao de simulacao do piloto <b>{nome}</b>. Foram identificadas "
        f"<b>{len(lista_anomalias_dados)} anomalia(s)</b> distribuidas em "
        f"<b>{len(voltas_afetadas)} volta(s)</b> (Voltas: {voltas_str}). Os dados "
        "compreendem sinais de controle do veiculo (volante, acelerador, freio) "
        "sincronizados com dados de pupilometria (dilatacao pupilar e fixacoes oculares) "
        "registrados pelo Pupil Labs.",
        e_analise,
    ))
    historia.append(Paragraph(
        "As anomalias de steering sao classificadas em tres tipos: "
        "<b>Tipo A</b> — Sinal Invertido (curva realizada no sentido oposto ao ideal); "
        "<b>Tipo B</b> — Desvio Excessivo na Reta (saida indevida da trajetoria em trechos retos); "
        "<b>Tipo C</b> — Correcao Brusca de Volante (input abrupto com alta taxa de variacao). "
        "Para cada evento anomalo, sao calculados os tempos de reacao (TR) de quatro sinais: "
        "Steering, Acelerador, Freio e Pupila.",
        e_analise,
    ))
    historia.append(Spacer(1, 0.3 * cm))

    # ── Resumo de anomalias ────────────────────────────────────────────────────
    resumo_data = [["Volta", "Anomalia", "Tipo", "Posicao", "Duracao",
                    "1o Sinal", "Fix.", "Ordem de Reacao"]]
    for d in lista_anomalias_dados:
        n_fix = d.get("stats_fixacao", {}).get("n_fixacoes", 0)
        resumo_data.append([
            str(d["volta_num"]),
            f"{d['tipo']}{d['anom_num']}",
            LABELS_TIPO.get(d["tipo"], d["tipo"]),
            f"{d['ini_pct']:.1f}%-{d['fim_pct']:.1f}%",
            f"{d['duracao_anom']:.2f}s",
            d.get("primeiro_sinal", "N/D"),
            str(n_fix),
            d.get("ordem_reacao", "N/D"),
        ])
    tab_res = Table(
        resumo_data,
        colWidths=[1.1*cm, 1.4*cm, 4.0*cm, 2.8*cm, 1.7*cm, 2.0*cm, 1.0*cm, 4.5*cm],
    )
    tab_res.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2980b9")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#ecf0f1"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(tab_res)
    historia.append(Spacer(1, 0.5 * cm))

    # ── Metodologia ───────────────────────────────────────────────────────────
    historia.append(Paragraph("Metodologia", e_sec))
    historia.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#2980b9"), spaceAfter=6))
    historia.append(Paragraph(
        "Para cada anomalia detectada, foi extraida uma janela temporal de "
        "<b>3,0 segundos</b> antes do inicio e <b>2,0 segundos</b> apos o termino do evento. "
        "Nessa janela foram analisados os seguintes sinais: "
        "(1) <b>Steering</b> — angulo do volante (graus), comparado ao perfil ideal calculado "
        "sobre as voltas sem anomalia; "
        "(2) <b>Acelerador e Freio</b> — posicao dos pedais (%), capturados via telemetria MoTeC; "
        "(3) <b>Pupila</b> — diametro pupilar (mm) registrado pelo Pupil Labs, sincronizado "
        "via frame de referencia ('marco zero') informado manualmente.",
        e_analise,
    ))
    historia.append(Paragraph(
        "O <b>Tempo de Reacao (TR)</b> de cada sinal e calculado como a diferenca temporal "
        "entre o onset do sinal e o onset do primeiro sinal detectado na janela. "
        "Valores negativos indicam antecipacao; valores positivos indicam latencia. "
        "O <b>perfil pupilar global</b> e calculado dividindo-se a pista em "
        f"<b>{N_SETORES} setores</b> de igual duracao temporal, computando-se a media "
        "do diametro pupilar em cada setor por volta. "
        "As <b>fixacoes oculares</b> sao classificadas como curtas "
        f"(&lt;{LIMIAR_FIXACAO_CURTA_MS:.0f}ms) ou longas "
        f"(&gt;{LIMIAR_FIXACAO_LONGA_MS:.0f}ms).",
        e_analise,
    ))
    historia.append(Spacer(1, 0.3 * cm))

    # ── Resumo cognitivo global ────────────────────────────────────────────────
    historia.append(Paragraph("Resumo Cognitivo Global", e_sec_cog))
    stats_glob = estatisticas_fixacao(df_fix_sync)
    comp_glob = classificar_comportamento_fixacao(stats_glob)
    dur_m = stats_glob.get("dur_media_ms", np.nan)
    cog_rows = [
        ["Metrica Cognitiva", "Valor"],
        ["Total de Fixacoes (sessao)", str(stats_glob.get("n_fixacoes", "N/D"))],
        ["Duracao Media de Fixacao",
         f"{dur_m:.0f} ms" if not np.isnan(dur_m) else "N/D"],
        ["Fixacoes Curtas (<100ms)", str(stats_glob.get("n_curtas", "N/D"))],
        ["Fixacoes Longas (>800ms)", str(stats_glob.get("n_longas", "N/D"))],
        ["Picos de Dilatacao Pupilar", str(len(picos_cognitivos))],
        ["Classificacao do Comportamento Visual", comp_glob],
    ]
    tab_cog = Table(cog_rows, colWidths=[8 * cm, 9 * cm])
    tab_cog.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8e44ad")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.HexColor("#f5eef8"), colors.HexColor("#fdfefe")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(tab_cog)
    historia.append(Spacer(1, 0.4 * cm))

    # ── Gráfico de perfil pupilar global ──────────────────────────────────────
    fig_perf = gerar_grafico_perfil_pupilar(
        nome, perfis_por_volta, t_pupila_total, diam_pupila_total, picos_cognitivos
    )
    if fig_perf:
        fig_perf.seek(0)
        historia.append(Image(fig_perf, width=largura_pagina - 3 * cm, height=11 * cm))
    historia.append(Spacer(1, 0.3 * cm))
    for p in _analise_perfil_pupilar_texto(perfis_por_volta, picos_cognitivos, e_analise):
        historia.append(p)
    historia.append(Spacer(1, 0.3 * cm))

    # ── Seção: Gráfico geral por volta (visão completa) ───────────────────────
    # Busca as imagens geradas por anomalias.py salvas em graficos_voltas/
    imgs_volta = sorted(GRAFICOS_VOLTAS_DIR.glob(f"volta_*_{nome}.png"))
    if imgs_volta:
        historia.append(PageBreak())
        historia.append(Paragraph("Analise Geral por Volta", e_sec))
        historia.append(HRFlowable(width="100%", thickness=2,
                                   color=colors.HexColor("#2980b9"), spaceAfter=8))
        historia.append(Paragraph(
            "Para cada volta sao exibidos (de cima para baixo): contexto da pista "
            "(reta/curva), esterçamento do piloto vs media ideal (±1σ), "
            "desvio em relacao ao ideal, pedais (acelerador e freio com referencia ideal) "
            "e diametro pupilar. As anomalias detectadas estao destacadas em cor.",
            e_analise,
        ))
        for img_path in imgs_volta:
            # Extrai numero da volta do nome "volta_01_Nome.png"
            try:
                volta_n = int(img_path.stem.split("_")[1])
            except (IndexError, ValueError):
                volta_n = 0
            historia.append(PageBreak())
            historia.append(Paragraph(f"Volta {volta_n}", e_sec))
            historia.append(HRFlowable(width="100%", thickness=1,
                                       color=colors.HexColor("#2980b9"), spaceAfter=6))
            historia.append(
                Image(str(img_path), width=largura_pagina - 3 * cm, height=14 * cm)
            )
            historia.append(Spacer(1, 0.2 * cm))
            historia.append(Paragraph(
                f"Relatorio TCC - {nome} | Volta {volta_n} | {data_hora}",
                e_rodape,
            ))

    # ── Páginas de fixação por volta ───────────────────────────────────────────
    for v_info in lista_voltas:
        fig_fix = gerar_grafico_fixacoes_volta(
            nome, df_fix_sync, v_info["t_ini"], v_info["t_fim"], v_info["volta_num"]
        )
        if fig_fix:
            historia.append(PageBreak())
            historia.append(
                Paragraph(f"Analise de Fixacoes - Volta {v_info['volta_num']}", e_sec_cog)
            )
            historia.append(HRFlowable(width="100%", thickness=1.5,
                                        color=colors.HexColor("#8e44ad"), spaceAfter=8))
            fig_fix.seek(0)
            historia.append(Image(fig_fix, width=largura_pagina - 3 * cm, height=11 * cm))
            historia.append(Spacer(1, 0.3 * cm))
            if not df_fix_sync.empty and "t_sync" in df_fix_sync.columns:
                df_fix_v = df_fix_sync[
                    (df_fix_sync["t_sync"] >= v_info["t_ini"]) &
                    (df_fix_sync["t_sync"] <= v_info["t_fim"])
                ]
                stats_fix_v = estatisticas_fixacao(df_fix_v)
            else:
                stats_fix_v = estatisticas_fixacao(pd.DataFrame())
                df_fix_v = pd.DataFrame()
            for p in _analise_fixacoes_texto(df_fix_v, stats_fix_v, e_analise):
                historia.append(p)
            historia.append(Spacer(1, 0.3 * cm))

    # ── Páginas de anomalias individuais ──────────────────────────────────────
    for d in lista_anomalias_dados:
        historia.append(PageBreak())

        tipo = d["tipo"]
        volta_num = d["volta_num"]
        anom_num = d["anom_num"]
        cor_sec = cor_tipo.get(tipo, colors.HexColor("#2980b9"))

        historia.append(Paragraph(f"Anomalia {tipo}{anom_num} - Volta {volta_num}", e_sec))
        historia.append(HRFlowable(width="100%", thickness=1.5, color=cor_sec, spaceAfter=8))

        delta_d = d.get("delta_diam", np.nan)
        d_antes = d.get("diam_antes", np.nan)
        d_durante = d.get("diam_durante", np.nan)
        d_depois = d.get("diam_depois", np.nan)

        sinal_delta = "+" if (not np.isnan(delta_d) and delta_d > 0) else ""
        reacao_pupila = "dilatou" if (not np.isnan(delta_d) and delta_d > 0) else "contraiu"

        meta_rows = [
            ["Campo", "Valor"],
            ["Tipo de Anomalia", LABELS_TIPO.get(tipo, tipo)],
            ["Posicao na Pista", f"{d['ini_pct']:.1f}% -> {d['fim_pct']:.1f}%"],
            ["Duracao da Anomalia", f"{d['duracao_anom']:.3f}s"],
            ["1o Sinal Detectado", d.get("primeiro_sinal", "N/D")],
            ["Ordem de Reacao", d.get("ordem_reacao", "N/D")],
            ["Pupila - Antes", _fmt(d_antes, " mm")],
            ["Pupila - Durante", _fmt(d_durante, " mm")],
            ["Pupila - Depois", _fmt(d_depois, " mm")],
            ["Delta Pupila", f"{sinal_delta}{_fmt(delta_d, ' mm')} ({reacao_pupila})"],
        ]

        for sinal in ["Steering", "Acelerador", "Freio", "Pupila"]:
            chave_tr = f"TR_{sinal.lower()}_s"
            val_tr = d.get(chave_tr, np.nan)
            if val_tr is not None and not np.isnan(val_tr):
                meta_rows.append([f"TR {sinal}", f"{val_tr:+.3f}s"])

        stats_fix = d.get("stats_fixacao", {})
        if stats_fix and stats_fix.get("n_fixacoes", 0) > 0:
            dur_fix = stats_fix.get("dur_media_ms", np.nan)
            meta_rows.extend([
                ["── Fixacoes na Janela ──", ""],
                ["N. Fixacoes", str(stats_fix["n_fixacoes"])],
                ["Duracao Media Fix.",
                 f"{dur_fix:.0f}ms" if not np.isnan(dur_fix) else "N/D"],
                ["Fix. Curtas (<100ms)", str(stats_fix.get("n_curtas", 0))],
                ["Fix. Longas (>800ms)", str(stats_fix.get("n_longas", 0))],
                ["Classificacao Visual",
                 d.get("comportamento_visual", classificar_comportamento_fixacao(stats_fix))],
            ])

        tab_meta = Table(meta_rows, colWidths=[6 * cm, 10 * cm])
        tab_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cor_sec),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.HexColor("#fdfefe"), colors.HexColor("#f2f3f4")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        historia.append(tab_meta)
        historia.append(Spacer(1, 0.4 * cm))

        if d.get("fig_bytes") is not None:
            d["fig_bytes"].seek(0)
            img = Image(d["fig_bytes"], width=largura_pagina - 3 * cm, height=10 * cm)
            historia.append(img)

        historia.append(Spacer(1, 0.3 * cm))
        for p in _analise_anomalia_texto(d, e_analise):
            historia.append(p)
        historia.append(Spacer(1, 0.2 * cm))
        historia.append(Paragraph(
            f"Relatorio TCC - {nome} | Anomalia {tipo}{anom_num} | Volta {volta_num} | {data_hora}",
            e_rodape,
        ))

    # ── Conclusão ─────────────────────────────────────────────────────────────
    historia.append(PageBreak())
    historia.append(Paragraph("Conclusao e Consideracoes Finais", e_sec))
    historia.append(HRFlowable(width="100%", thickness=2,
                                color=colors.HexColor("#2980b9"), spaceAfter=8))

    n_a = por_tipo.get("A", 0)
    n_b = por_tipo.get("B", 0)
    n_c = por_tipo.get("C", 0)
    historia.append(Paragraph(
        f"<b>Sintese Quantitativa:</b> A sessao do piloto <b>{nome}</b> registrou "
        f"<b>{glob.get('total', 0)} anomalia(s)</b> de steering — "
        f"Tipo A: {n_a} | Tipo B: {n_b} | Tipo C: {n_c}. "
        f"Duracao media das anomalias: <b>{_fmt(glob.get('dur_media', np.nan), 's')}</b> "
        f"(min: {_fmt(glob.get('dur_min', np.nan), 's')} / "
        f"max: {_fmt(glob.get('dur_max', np.nan), 's')}). "
        f"Anomalias ocorreram nas voltas: {voltas_str}.",
        e_analise,
    ))

    delta_m = glob.get("delta_medio", np.nan)
    if not np.isnan(delta_m):
        if delta_m > 0.2:
            delta_interp = "tendencia de ativacao pupilar associada aos eventos de anomalia"
        elif delta_m < -0.2:
            delta_interp = "tendencia de subarousal ou adaptacao fisiologica durante as anomalias"
        else:
            delta_interp = "ausencia de padrao predominante de resposta pupilar"
        delta_txt = (
            f"O delta medio de diametro pupilar foi de <b>{_fmt(delta_m, 'mm')}</b>, "
            f"sugerindo {delta_interp}. "
        )
    else:
        delta_txt = "O delta medio de diametro pupilar nao pode ser calculado. "

    historia.append(Paragraph(
        f"<b>Padrao de Resposta:</b> O primeiro sinal de reacao mais frequente foi "
        f"<b>{glob.get('primeiro_sinal_mais_freq', 'N/D')}</b>. "
        f"{glob.get('n_dilatacoes', 0)} anomalia(s) apresentaram dilatacao pupilar e "
        f"{glob.get('n_contracoes', 0)} apresentaram contracao. "
        f"{delta_txt}"
        f"O total de fixacoes registradas nas janelas de analise foi de "
        f"<b>{glob.get('n_fixacoes_total_anomalias', 0)}</b>.",
        e_analise,
    ))

    historia.append(Paragraph(
        "<b>Limitacoes Metodologicas:</b> "
        "(1) A sincronizacao entre pupilometria e telemetria e realizada por um unico ponto "
        "de referencia manual ('marco zero'), o que pode introduzir derivacao temporal acumulada; "
        "(2) os dados de dilatacao pupilar sao influenciados por luminosidade ambiental, "
        "piscadas e artefatos de rastreamento; "
        "(3) os tempos de reacao calculados sao relativos ao primeiro sinal detectado na "
        "janela, e nao ao estimulo objetivo externo.",
        e_analise,
    ))

    historia.append(Paragraph(
        "<b>Sugestoes:</b> "
        "Recomenda-se a analise comparativa entre pilotos para validacao dos padroes "
        "identificados. Anomalias recorrentes no mesmo setor da pista (especialmente Tipos A e C) "
        "podem indicar pontos de dificuldade sistematica que merecem atencao no treinamento. "
        "A integracao dos dados de fixacao com os setores de alta variacao pupilar pode "
        "oferecer indicios adicionais sobre a atencao visual durante eventos criticos. "
        "Dados adicionais uteis incluiriam: frequencia cardiaca, condutancia eletrodermica, "
        "e multiplos pontos de sincronizacao para reduzir a derivacao temporal.",
        e_analise,
    ))
    historia.append(Spacer(1, 0.3 * cm))

    doc.build(historia)
    print(f"PDF gerado: {caminho_pdf}")
    return caminho_pdf


# ── Execução ───────────────────────────────────────────────────────────────────

def executar():
    if not REPORTLAB_DISPONIVEL:
        raise ImportError(
            "A biblioteca 'reportlab' nao esta instalada. "
            "Instale com: pip install reportlab"
        )
    validar_arquivos_base()
    if not os.path.exists(ARQUIVO_IDEAL):
        raise Exception("Rode o Codigo 1 primeiro.")
    if not os.path.exists(ARQUIVO_ANOMALIAS):
        raise Exception("Rode o Codigo 3 (anomalias.py) primeiro para gerar anomalias_detectadas.csv.")

    sessao_nome = input("Nome da sessao (deve coincidir com sincronizacao.py, ex: 'Interlagos'): ").strip() or "Interlagos"

    df_ideal = pd.read_csv(ARQUIVO_IDEAL)
    df_anom = pd.read_csv(ARQUIVO_ANOMALIAS)
    eixo_pct = df_ideal["progresso_pct"].values
    steer_med = df_ideal["steering_medio"].values
    steer_sigma = df_ideal["steering_sigma"].values if "steering_sigma" in df_ideal.columns else None

    print(f"Baseline: {len(eixo_pct)} pontos")
    print(f"Anomalias para analisar: {len(df_anom)}")

    pdfs_gerados = []
    registros_csv = []
    csvs_individuais = []

    for nome in df_anom["piloto"].unique():
        df_anom_piloto = df_anom[df_anom["piloto"] == nome].reset_index(drop=True)
        df_anom_piloto = df_anom_piloto[df_anom_piloto["volta_num"] != 0].reset_index(drop=True)
        voltas_ordenadas = sorted(df_anom_piloto["volta_num"].unique())
        mapa_voltas = {v: i + 1 for i, v in enumerate(voltas_ordenadas)}
        print(f"\n{'=' * 60}")
        print(f"   CARREGANDO: {nome.upper()} ({len(df_anom_piloto)} anomalia(s))")
        print(f"{'=' * 60}")
        if df_anom_piloto.empty:
            print(f"  Nenhuma anomalia apos remover Volta 0 para {nome} - pulando")
            continue

        caminhos = PILOTOS[nome]
        pasta_piloto = Path(caminhos["pupila"]).parent
        caminho_fixacoes = pasta_piloto / "fixations.csv"
        caminho_world_ts = pasta_piloto / "world_timestamps.csv"

        # Pupil positions
        df_pupil = pd.read_csv(
            str(caminhos["pupila"]), sep=None, engine="python", on_bad_lines="skip"
        )
        df_pupil.columns = [str(c).strip() for c in df_pupil.columns]

        c_p_m = [c for c in df_pupil.columns if "method" in c.lower()]
        if c_p_m:
            count_2d = (df_pupil[c_p_m[0]].astype(str)
                        .str.contains(r"2d c\+\+", regex=True, case=False).sum())
            count_3d = (df_pupil[c_p_m[0]].astype(str)
                        .str.contains("pye3d", regex=True, case=False).sum())
            metodo = "pye3d" if count_3d > count_2d else r"2d c\+\+"
            df_pupil = df_pupil[
                df_pupil[c_p_m[0]].astype(str).str.contains(
                    metodo, regex=True, case=False, na=False
                )
            ]

        c_p_t = [c for c in df_pupil.columns if "timestamp" in c.lower()][0]
        c_p_wi = [c for c in df_pupil.columns if "world_index" in c.lower()][0]
        c_p_d_list = [c for c in df_pupil.columns if "diameter_3d" in c.lower()]
        if not c_p_d_list or df_pupil[c_p_d_list[0]].isna().all():
            c_p_d_list = [c for c in df_pupil.columns if "diameter" in c.lower()]
        c_p_d = c_p_d_list[0]

        # Sincronização
        t_sync_m = float(df_anom_piloto["t_sync_m"].iloc[0])
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
                    f"frame_sync ausente para '{nome}'. Execute sincronizacao.py antes."
                )
            frame_sync = _params.frame_sync
        print(f"  [{nome}] frame_sync lido do banco: {frame_sync}")
        t_sync_p = atirar_com_sniper(frame_sync, df_pupil, c_p_wi, c_p_t)

        df_pupil[c_p_t] = df_pupil[c_p_t].apply(force_float)
        df_pupil[c_p_d] = df_pupil[c_p_d].apply(limpa_diametro)
        df_pupil = df_pupil.dropna(subset=[c_p_t, c_p_d])

        t_raw = df_pupil[c_p_t].values - t_sync_p
        mediana_ab = np.nanmedian(np.abs(t_raw))
        if mediana_ab > 100_000:
            escala = 1_000_000.0
        elif mediana_ab > 500:
            escala = 1_000.0
        else:
            escala = 1.0

        t_pupila = (df_pupil[c_p_t].values - t_sync_p) / escala
        diam_pupila = (
            pd.Series(df_pupil[c_p_d].values).rolling(window=5, center=True).mean().values
        )

        # Fixações e world timestamps
        df_fix_sync = carregar_fixacoes(caminho_fixacoes, t_sync_p, escala)
        print(f"  Fixacoes carregadas: {len(df_fix_sync)}")

        caminho_blinks = pasta_piloto / "blinks.csv"
        df_blinks = carregar_blinks(caminho_blinks, t_sync_p, escala)
        print(f"  Blinks carregados: {len(df_blinks)}")

        if caminho_world_ts.exists():
            df_wt = carregar_world_timestamps(caminho_world_ts)
            print(f"  World timestamps: {len(df_wt)} frames")

        # MoTeC
        df_m = pd.read_csv(
            str(caminhos["motec"]), skiprows=14, sep=None, engine="python",
            encoding="latin1", on_bad_lines="skip",
        )
        df_m.columns = [str(c).strip() for c in df_m.columns]
        t_series = clean_col(df_m, ["Time"])
        df_m["t_sync"] = t_series - t_sync_m
        df_m["steer"] = clean_col(df_m, ["Steering Angle"])
        df_m["acel"] = clean_col(df_m, ["Throttle Pos"])
        df_m["freio"] = clean_col(df_m, ["Brake Pos"])
        _vel_serie = clean_col(df_m, ["Ground Speed", "GPS Speed", "Vehicle Speed", "Speed"])
        df_m["vel"] = _vel_serie / 3.6 if _vel_serie is not None else np.nan
        df_m = df_m.dropna(subset=["t_sync"])

        t_motec = df_m["t_sync"].values
        steer_raw = df_m["steer"].values
        acel_raw = df_m["acel"].values
        freio_raw = df_m["freio"].values
        vel_raw = df_m["vel"].values

        # Voltas únicas presentes nas anomalias
        lista_voltas_unicas = []
        seen_v = set()
        for _, row in df_anom_piloto.iterrows():
            vn = int(row["volta_num"])
            if vn not in seen_v:
                seen_v.add(vn)
                lista_voltas_unicas.append({
                    "volta_num": mapa_voltas[vn],
                    "t_ini": float(row["t_ini_volta"]),
                    "t_fim": float(row["t_fim_volta"]),
                })

        # Perfil pupilar por setor (por volta)
        perfis_por_volta = [
            calcular_perfil_pupilar_por_setor(
                t_pupila, diam_pupila, v["t_ini"], v["t_fim"]
            )
            for v in lista_voltas_unicas
        ]

        # Picos cognitivos (sessão completa)
        picos_cognitivos = detectar_picos_pupila(t_pupila, diam_pupila)
        print(f"  Picos cognitivos detectados: {len(picos_cognitivos)}")

        # ── Análise por anomalia ───────────────────────────────────────────────
        lista_anomalias_piloto = []

        for _, row in df_anom_piloto.iterrows():
            volta_num_orig = int(row["volta_num"])
            volta_num = mapa_voltas[volta_num_orig]
            anom_num = int(row["anom_num"])
            tipo = row["tipo"]
            ini_pct = row["ini_pct"]
            fim_pct = row["fim_pct"]
            t_ini_v = row["t_ini_volta"]
            t_fim_v = row["t_fim_volta"]

            t_anom_ini = pct_para_tempo_real(ini_pct, t_ini_v, t_fim_v)
            t_anom_fim = pct_para_tempo_real(fim_pct, t_ini_v, t_fim_v)
            dur_anom = t_anom_fim - t_anom_ini

            t_jan_ini = t_anom_ini - JANELA_REACAO_SEG
            t_jan_fim = t_anom_fim + JANELA_POS_ANOMALIA_SEG

            mask_m = (t_motec >= t_jan_ini) & (t_motec <= t_jan_fim)
            mask_p = (t_pupila >= t_jan_ini) & (t_pupila <= t_jan_fim)

            if mask_m.sum() < 5:
                print(f"  Dados insuficientes para {tipo}{anom_num} - pulando")
                continue

            t_m_jan = t_motec[mask_m]
            s_jan = steer_raw[mask_m]
            a_jan = acel_raw[mask_m]
            f_jan = freio_raw[mask_m]
            t_p_jan = t_pupila[mask_p]
            d_jan = diam_pupila[mask_p]

            onset_steer = encontrar_onset(
                t_m_jan, s_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_STEERING_GRAUS
            )
            onset_acel = encontrar_onset(
                t_m_jan, a_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PEDAL_PCT
            )
            onset_freio = encontrar_onset(
                t_m_jan, f_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PEDAL_PCT
            )
            onset_pupil = (
                encontrar_onset(
                    t_p_jan, d_jan, t_anom_ini, JANELA_REACAO_SEG, LIMIAR_ONSET_PUPILA_MM
                )
                if len(t_p_jan) > 2
                else None
            )

            onsets = {
                "Steering": onset_steer,
                "Acelerador": onset_acel,
                "Freio": onset_freio,
                "Pupila": onset_pupil,
            }
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
            delta_d = (
                d_durante - d_antes
                if not (np.isnan(d_antes) or np.isnan(d_durante))
                else np.nan
            )

            # Fixações na janela desta anomalia
            df_fix_janela = filtrar_fixacoes_janela(df_fix_sync, t_jan_ini, t_jan_fim)
            stats_fix = estatisticas_fixacao(df_fix_janela)
            comportamento_fix = classificar_comportamento_fixacao(stats_fix)

            # Picos cognitivos na janela desta anomalia
            picos_jan = [(t, d) for (t, d) in picos_cognitivos if t_jan_ini <= t <= t_jan_fim]
            n_picos_jan = len(picos_jan)
            intensidade_picos = (
                round(float(np.mean([d for _, d in picos_jan])), 4) if picos_jan else 0.0
            )

            # Tempo de reação pupilar absoluto (onset pupila - início da anomalia)
            tr_pupilar = (
                round(float(onset_pupil - t_anom_ini), 4)
                if onset_pupil is not None
                else ""
            )

            # Média do tamanho pupilar na janela de análise
            media_pup = (
                round(float(np.nanmean(d_jan)), 4)
                if len(d_jan) > 0 and not np.all(np.isnan(d_jan))
                else ""
            )

            # Crescimento máximo da pupila (derivada) durante a anomalia
            _cresc = calcular_crescimento_pupilar_derivada(t_pupila, diam_pupila, t_anom_ini, t_anom_fim)
            cresc_derivada = round(_cresc, 4) if not np.isnan(_cresc) else ""

            # Blinks: tempo e distância "no escuro" na janela da anomalia
            tempo_escuro, dist_escuro = calcular_metricas_blinks(
                df_blinks, t_jan_ini, t_jan_fim, t_motec, vel_raw
            )

            # Direção da resposta pupilar
            if np.isnan(delta_d):
                tipo_resp_pupilar = ""
            elif delta_d > 0.2:
                tipo_resp_pupilar = "Dilatacao"
            elif delta_d < -0.2:
                tipo_resp_pupilar = "Contracao"
            else:
                tipo_resp_pupilar = "Estavel"

            # Tempos de reação relativos ao primeiro sinal
            trs = {}
            if t_primeiro is not None:
                for sinal, t_on in onsets_validos.items():
                    trs[f"TR_{sinal.lower()}_s"] = round(t_on - t_primeiro, 4)

            cor = CORES_TIPO[tipo]
            fig_bytes = gerar_grafico_anomalia(
                nome, tipo, volta_num, anom_num,
                t_m_jan, s_jan, a_jan, f_jan,
                t_p_jan, d_jan,
                t_anom_ini, t_anom_fim,
                df_fix_janela,
                eixo_pct, steer_med, ini_pct, fim_pct,
                t_jan_ini, t_jan_fim,
                onsets_validos, ordem_reacao, primeiro_sinal,
                d_antes, delta_d,
                cor,
                steer_sigma=steer_sigma,
            )

            dado = {
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
                "fig_bytes": fig_bytes,
                "stats_fixacao": stats_fix,
                "comportamento_visual": comportamento_fix,
            }
            dado.update(trs)
            lista_anomalias_piloto.append(dado)

            registros_csv.append({
                "piloto": nome,
                "volta_num": volta_num,
                "anom_num": anom_num,
                "tipo": tipo,
                "ini_pct": ini_pct,
                "fim_pct": fim_pct,
                "duracao_anom": round(dur_anom, 4),
                "primeiro_sinal": primeiro_sinal,
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
                "contexto_pista": inferir_contexto_pista(tipo, s_jan),
                "tipo_resposta_pupilar": tipo_resp_pupilar,
                "n_picos_cognitivos_janela": n_picos_jan,
                "intensidade_media_picos": intensidade_picos,
                "tempo_reacao_pupilar_s": tr_pupilar,
                "media_tamanho_pupilar": media_pup,
                "crescimento_pupilar_derivada": cresc_derivada,
                "tempo_no_escuro_s": tempo_escuro,
                "distancia_no_escuro_m": dist_escuro,
                **{k: v for k, v in trs.items()},
            })

            print(
                f"  Anomalia {tipo}{anom_num} (Volta {volta_num}): "
                f"1o sinal={primeiro_sinal} | ordem={' -> '.join(ordem_reacao)} | "
                f"fixacoes={stats_fix['n_fixacoes']} | visual={comportamento_fix}"
            )

        if lista_anomalias_piloto:
            caminho_pdf = gerar_pdf_piloto(
                nome,
                lista_anomalias_piloto,
                str(PASTA_SAIDA_PDF),
                perfis_por_volta,
                picos_cognitivos,
                t_pupila,
                diam_pupila,
                df_fix_sync,
                lista_voltas_unicas,
            )
            pdfs_gerados.append(caminho_pdf)
            caminho_csv_ind = salvar_csv_individual(nome, registros_csv, PASTA_SAIDA_CSV_IND)
            csvs_individuais.append(caminho_csv_ind)
        else:
            print(f"  Nenhuma anomalia com dados suficientes para {nome} - PDF nao gerado")

    # Exportar CSV consolidado (relatorio_TR original — sem alteração nas colunas)
    if registros_csv:
        df_csv = pd.DataFrame(registros_csv)
        df_csv.to_csv(str(ARQUIVO_RELATORIO_TR), index=False, encoding="utf-8")
        print(f"\nRelatorio CSV salvo: {ARQUIVO_RELATORIO_TR}")

    # Exportar base consolidada para ANOVA
    consolidar_csvs_anova(csvs_individuais, ARQUIVO_BASE_ANOVA)

    _persistir_banco_individuais(registros_csv, sessao_nome)

    print(f"\n{'=' * 60}")
    print(f"PDFs gerados: {len(pdfs_gerados)}")
    for caminho in pdfs_gerados:
        print(f"  - {caminho}")
    print(f"{'=' * 60}")


def _persistir_banco_individuais(registros_csv, sessao_nome="Interlagos"):
    try:
        from backend.database import SessionLocal
        from backend.db_ops import (
            get_or_create_piloto, get_or_create_sessao,
            upsert_metrica_anomalia, upsert_fixacao_anomalia,
        )
        from backend.models import Anomalia as AnomaliaModel
        from backend.models import Volta as VoltaModel

        db = SessionLocal()
        try:
            sessao = get_or_create_sessao(db, sessao_nome)
            count = 0
            for rec in registros_csv:
                nome = rec.get("piloto")
                if not nome:
                    continue
                piloto = get_or_create_piloto(db, nome)
                volta = db.query(VoltaModel).filter_by(
                    sessao_id=sessao.id,
                    piloto_id=piloto.id,
                    numero_volta=int(rec["volta_num"]),
                ).first()
                if not volta:
                    continue
                anom = db.query(AnomaliaModel).filter_by(
                    volta_id=volta.id,
                    numero_anomalia=int(rec["anom_num"]),
                ).first()
                if not anom:
                    continue
                # Enriquece anomalia com dados calculados aqui
                if not anom.contexto_pista and rec.get("contexto_pista"):
                    anom.contexto_pista = str(rec["contexto_pista"])
                if not anom.duracao_s and rec.get("duracao_anom"):
                    try:
                        anom.duracao_s = float(rec["duracao_anom"])
                    except (TypeError, ValueError):
                        pass
                upsert_metrica_anomalia(db, anom.id, rec)
                upsert_fixacao_anomalia(db, anom.id, rec)
                count += 1
            db.commit()
            print(f"✅ [DB] {count} métrica(s) individual(is) persistida(s).")
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  [DB] Falha ao persistir métricas — análise não afetada. Erro: {e}")


def main():
    try:
        executar()
    except Exception as e:
        import traceback
        print(f"\nDEU RUIM: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
