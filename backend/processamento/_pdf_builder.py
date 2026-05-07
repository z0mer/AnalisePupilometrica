"""
backend/processamento/_pdf_builder.py
=======================================
Geração do relatório PDF de TR em memória (BytesIO → bytes).
Depende de reportlab. Se não disponível, retorna None.
"""
from __future__ import annotations

import io
import math
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.processamento.utils import (
    CORES_TIPO,
    LABELS_TIPO,
    LIMIAR_FIXACAO_CURTA_MS,
    LIMIAR_FIXACAO_LONGA_MS,
    LIMIAR_PICO_DILATACAO_MM,
    N_SETORES,
    fig_para_bytes,
)


def _fmt(v, sufixo: str = "") -> str:
    return f"{v:.3f}{sufixo}" if (v is not None and not math.isnan(float(v))) else "N/D"


def _estatisticas_globais(lista: list[dict]) -> dict:
    from collections import Counter

    if not lista:
        return {}

    def _safe(chave):
        return [
            d[chave] for d in lista
            if chave in d and d[chave] is not None and not math.isnan(float(d[chave]))
        ]

    tipos = [d["tipo"] for d in lista]
    deltas = _safe("delta_diam")
    durs = [d["duracao_anom"] for d in lista]
    primeiros = [d.get("primeiro_sinal") for d in lista if d.get("primeiro_sinal")]
    mais_freq = Counter(primeiros).most_common(1)
    trs_s = _safe("TR_steering_s")
    trs_p = _safe("TR_pupila_s")

    return {
        "total": len(lista),
        "por_tipo": dict(Counter(tipos)),
        "dur_media": float(np.nanmean(durs)) if durs else np.nan,
        "dur_max": float(np.nanmax(durs)) if durs else np.nan,
        "dur_min": float(np.nanmin(durs)) if durs else np.nan,
        "delta_medio": float(np.nanmean(deltas)) if deltas else np.nan,
        "n_dilatacoes": sum(1 for v in deltas if v > 0),
        "n_contracoes": sum(1 for v in deltas if v < 0),
        "primeiro_sinal_mais_freq": mais_freq[0][0] if mais_freq else "N/D",
        "n_fixacoes_total_anomalias": sum(
            d.get("stats_fixacao", {}).get("n_fixacoes", 0) for d in lista
        ),
        "voltas_afetadas": sorted({d["volta_num"] for d in lista}),
        "tr_steering_medio": float(np.nanmean(trs_s)) if trs_s else np.nan,
        "tr_pupila_medio": float(np.nanmean(trs_p)) if trs_p else np.nan,
    }


def _estatisticas_fixacao(df_fix: pd.DataFrame) -> dict:
    vazio = {
        "n_fixacoes": 0, "dur_media_ms": np.nan,
        "n_curtas": 0, "n_longas": 0,
    }
    if df_fix is None or df_fix.empty:
        return vazio
    durs = df_fix["duration_ms"].dropna() if "duration_ms" in df_fix.columns else pd.Series([], dtype=float)
    return {
        "n_fixacoes": len(df_fix),
        "dur_media_ms": float(durs.mean()) if len(durs) > 0 else np.nan,
        "n_curtas": int((durs < LIMIAR_FIXACAO_CURTA_MS).sum()),
        "n_longas": int((durs > LIMIAR_FIXACAO_LONGA_MS).sum()),
    }


def _classificar_fixacao(stats: dict) -> str:
    n = stats.get("n_fixacoes", 0)
    if n == 0:
        return "Sem dados de fixacao"
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


def _gerar_grafico_perfil_pupilar(
    nome: str,
    perfis_por_volta: list,
    t_pupila_total: np.ndarray,
    diam_pupila_total: np.ndarray,
    picos: list,
) -> bytes | None:
    if not perfis_por_volta:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    fig.suptitle(f"Perfil Pupilar - {nome}", fontsize=12, fontweight="bold")

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
    ax1.bar(pct_centros, medias_agg, width=100 / N_SETORES * 0.8,
            color="#8e44ad", alpha=0.7, label="Diametro medio")
    ax1.errorbar(pct_centros, medias_agg, yerr=desvios_agg,
                 fmt="none", color="black", capsize=4, linewidth=1.2)
    ax1.set_xlabel("Progresso na Pista (%)", fontsize=9)
    ax1.set_ylabel("Diametro Pupilar (mm)", fontsize=9)
    ax1.set_title("Perfil Pupilar Medio por Setor", fontsize=10)
    ax1.set_xlim(0, 100)
    ax1.grid(True, alpha=0.3, axis="y")
    ax1.legend(fontsize=8)

    ax2 = axes[1]
    if len(t_pupila_total) > 1:
        ax2.plot(t_pupila_total, diam_pupila_total, color="purple", linewidth=0.8,
                 alpha=0.6, label="Pupila")
        series_d = pd.Series(diam_pupila_total)
        bl = series_d.rolling(window=50, center=True, min_periods=3).median().values
        ax2.plot(t_pupila_total, bl, color="gray", linewidth=1.2, linestyle="--",
                 alpha=0.8, label="Mediana movel")
        if picos:
            t_p_list = [p[0] for p in picos]
            d_p_list = []
            for tp in t_p_list:
                idx_near = int(np.argmin(np.abs(t_pupila_total - tp)))
                d_p_list.append(diam_pupila_total[idx_near])
            ax2.scatter(t_p_list, d_p_list, color="red", s=45, zorder=6, marker="^",
                        label=f"Picos cognitivos ({len(picos)})")
    ax2.set_xlabel("Tempo Sincronizado (s)", fontsize=9)
    ax2.set_ylabel("Diametro Pupilar (mm)", fontsize=9)
    ax2.set_title("Linha do Tempo Pupilar com Picos de Estresse Cognitivo", fontsize=10)
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    b = fig_para_bytes(fig, dpi=130)
    plt.close(fig)
    return b


def gerar_pdf_bytes(
    nome: str,
    lista_anomalias_dados: list[dict],
    perfis_por_volta: list,
    picos_cognitivos: list,
    t_pupila_total: np.ndarray,
    diam_pupila_total: np.ndarray,
    df_fix_sync: pd.DataFrame,
    lista_voltas: list[dict],
) -> bytes | None:
    """
    Gera o relatório PDF completo em memória (bytes).
    Retorna None se reportlab não estiver disponível.
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            HRFlowable, Image, PageBreak, Paragraph,
            SimpleDocTemplate, Spacer, Table, TableStyle,
        )
    except ImportError:
        return None

    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
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

    cor_tipo_rl = {
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
        f"Picos cognitivos: {len(picos_cognitivos)}",
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
        f"do piloto <b>{nome}</b>. Foram identificadas <b>{len(lista_anomalias_dados)} anomalia(s)</b> "
        f"em <b>{len(voltas_afetadas)} volta(s)</b> (Voltas: {voltas_str}). "
        "Tipos: <b>A</b> — Sinal Invertido; <b>B</b> — Desvio na Reta; <b>C</b> — Correcao Brusca.",
        e_analise,
    ))
    historia.append(Spacer(1, 0.3 * cm))

    # ── Tabela resumo de anomalias ────────────────────────────────────────────
    resumo_data = [["Volta", "Anomalia", "Tipo", "Posicao", "Duracao", "1o Sinal", "Fix.", "Ordem"]]
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

    # ── Resumo cognitivo global ────────────────────────────────────────────────
    historia.append(Paragraph("Resumo Cognitivo Global", e_sec_cog))
    stats_glob = _estatisticas_fixacao(df_fix_sync)
    comp_glob = _classificar_fixacao(stats_glob)
    dur_m = stats_glob.get("dur_media_ms", np.nan)
    cog_rows = [
        ["Metrica Cognitiva", "Valor"],
        ["Total de Fixacoes (sessao)", str(stats_glob.get("n_fixacoes", "N/D"))],
        ["Duracao Media de Fixacao", f"{dur_m:.0f} ms" if not np.isnan(dur_m) else "N/D"],
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
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f5eef8"), colors.HexColor("#fdfefe")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    historia.append(tab_cog)
    historia.append(Spacer(1, 0.4 * cm))

    # ── Gráfico de perfil pupilar global ──────────────────────────────────────
    fig_perf = _gerar_grafico_perfil_pupilar(
        nome, perfis_por_volta, t_pupila_total, diam_pupila_total, picos_cognitivos
    )
    if fig_perf:
        historia.append(Image(io.BytesIO(fig_perf), width=largura_pagina - 3 * cm, height=11 * cm))
    historia.append(Spacer(1, 0.3 * cm))

    # ── Páginas de anomalias individuais ──────────────────────────────────────
    for d in lista_anomalias_dados:
        historia.append(PageBreak())

        tipo = d["tipo"]
        volta_num = d["volta_num"]
        anom_num = d["anom_num"]
        cor_sec = cor_tipo_rl.get(tipo, colors.HexColor("#2980b9"))

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
            if val_tr is not None and not math.isnan(float(val_tr)):
                meta_rows.append([f"TR {sinal}", f"{val_tr:+.3f}s"])

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
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fdfefe"), colors.HexColor("#f2f3f4")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        historia.append(tab_meta)
        historia.append(Spacer(1, 0.4 * cm))

        if d.get("fig_bytes") is not None:
            fb = d["fig_bytes"]
            fb.seek(0)
            historia.append(Image(fb, width=largura_pagina - 3 * cm, height=10 * cm))

        historia.append(Spacer(1, 0.3 * cm))
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
        f"<b>Sintese:</b> Piloto <b>{nome}</b> — "
        f"{glob.get('total', 0)} anomalia(s): A={n_a}, B={n_b}, C={n_c}. "
        f"Duracao media: {_fmt(glob.get('dur_media', np.nan), 's')}. "
        f"Voltas afetadas: {voltas_str}.",
        e_analise,
    ))
    historia.append(Spacer(1, 0.3 * cm))

    doc.build(historia)
    buf.seek(0)
    return buf.read()
