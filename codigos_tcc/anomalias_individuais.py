import io
import os
from datetime import datetime

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
    GRAFICOS_TR_DIR,
    PILOTOS,
    validar_arquivos_base,
)


PASTA_SAIDA_PDF = GRAFICOS_TR_DIR
JANELA_REACAO_SEG = 3.0
JANELA_POS_ANOMALIA_SEG = 2.0
LIMIAR_ONSET_PUPILA_MM = 2.0
LIMIAR_ONSET_PEDAL_PCT = 5.0
LIMIAR_ONSET_STEERING_GRAUS = 5.0

LABELS_TIPO = {
    "A": "Sinal Invertido (curva lado errado)",
    "B": "Desvio Excessivo na Reta",
    "C": "Correcao Brusca de Volante",
}
CORES_TIPO = {"A": "#e74c3c", "B": "#e67e22", "C": "#8e44ad"}


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


def gerar_pdf_piloto(nome, lista_anomalias_dados, pasta_saida):
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    caminho_pdf = os.path.join(pasta_saida, f"Relatorio_TR_{nome}.pdf")
    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    largura_pagina, _ = A4
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        "TituloDoc",
        parent=estilos["Title"],
        fontSize=18,
        textColor=colors.HexColor("#2c3e50"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo",
        parent=estilos["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#7f8c8d"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    estilo_secao = ParagraphStyle(
        "Secao",
        parent=estilos["Heading1"],
        fontSize=13,
        textColor=colors.HexColor("#2980b9"),
        spaceBefore=14,
        spaceAfter=6,
    )
    estilo_rodape = ParagraphStyle(
        "Rodape",
        parent=estilos["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#95a5a6"),
        alignment=TA_RIGHT,
    )

    cor_tipo = {
        "A": colors.HexColor("#e74c3c"),
        "B": colors.HexColor("#e67e22"),
        "C": colors.HexColor("#8e44ad"),
    }

    historia = []
    historia.append(Spacer(1, 1.0 * cm))
    historia.append(Paragraph("Relatorio de Tempo de Reacao", estilo_titulo))
    historia.append(Paragraph(f"Piloto: {nome}", estilo_subtitulo))
    historia.append(
        Paragraph(
            f"Gerado em: {data_hora} | Total de anomalias: {len(lista_anomalias_dados)}",
            estilo_subtitulo,
        )
    )
    historia.append(
        HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor("#2980b9"),
            spaceAfter=12,
        )
    )

    resumo_data = [[
        "Volta",
        "Anomalia",
        "Tipo",
        "Posicao na Pista",
        "Duracao",
        "1o Sinal",
        "Ordem de Reacao",
    ]]
    for d in lista_anomalias_dados:
        resumo_data.append(
            [
                str(d["volta_num"]),
                f"{d['tipo']}{d['anom_num']}",
                LABELS_TIPO.get(d["tipo"], d["tipo"]),
                f"{d['ini_pct']:.1f}% -> {d['fim_pct']:.1f}%",
                f"{d['duracao_anom']:.2f}s",
                d.get("primeiro_sinal", "N/D"),
                d.get("ordem_reacao", "N/D"),
            ]
        )

    tabela_resumo = Table(
        resumo_data,
        colWidths=[1.2 * cm, 1.5 * cm, 4.5 * cm, 3.2 * cm, 1.8 * cm, 2.2 * cm, 4.5 * cm],
    )
    tabela_resumo.setStyle(
        TableStyle(
            [
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
            ]
        )
    )
    historia.append(tabela_resumo)
    historia.append(Spacer(1, 0.5 * cm))

    for d in lista_anomalias_dados:
        historia.append(PageBreak())

        tipo = d["tipo"]
        volta_num = d["volta_num"]
        anom_num = d["anom_num"]
        cor_sec = cor_tipo.get(tipo, colors.HexColor("#2980b9"))

        historia.append(Paragraph(f"Anomalia {tipo}{anom_num} - Volta {volta_num}", estilo_secao))
        historia.append(HRFlowable(width="100%", thickness=1.5, color=cor_sec, spaceAfter=8))

        delta_d = d.get("delta_diam", np.nan)
        d_antes = d.get("diam_antes", np.nan)
        d_durante = d.get("diam_durante", np.nan)
        d_depois = d.get("diam_depois", np.nan)

        sinal_delta = "+" if (not np.isnan(delta_d) and delta_d > 0) else ""
        reacao_pupila = "dilatou" if (not np.isnan(delta_d) and delta_d > 0) else "contraiu"

        def fmt(v, sufixo=""):
            return f"{v:.3f}{sufixo}" if not np.isnan(v) else "N/D"

        meta_data = [
            ["Campo", "Valor"],
            ["Tipo de Anomalia", LABELS_TIPO.get(tipo, tipo)],
            ["Posicao na Pista", f"{d['ini_pct']:.1f}% -> {d['fim_pct']:.1f}%"],
            ["Duracao da Anomalia", f"{d['duracao_anom']:.3f}s"],
            ["1o Sinal Detectado", d.get("primeiro_sinal", "N/D")],
            ["Ordem de Reacao", d.get("ordem_reacao", "N/D")],
            ["Pupila - Antes", fmt(d_antes, " mm")],
            ["Pupila - Durante", fmt(d_durante, " mm")],
            ["Pupila - Depois", fmt(d_depois, " mm")],
            ["Delta Pupila", f"{sinal_delta}{fmt(delta_d, ' mm')} ({reacao_pupila})"],
        ]

        for sinal in ["Steering", "Acelerador", "Freio", "Pupila"]:
            chave_tr = f"TR_{sinal.lower()}_s"
            if chave_tr in d and not np.isnan(d.get(chave_tr, np.nan)):
                meta_data.append([f"TR {sinal}", f"{d[chave_tr]:+.3f}s"])

        tabela_meta = Table(meta_data, colWidths=[6 * cm, 10 * cm])
        tabela_meta.setStyle(
            TableStyle(
                [
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
                ]
            )
        )
        historia.append(tabela_meta)
        historia.append(Spacer(1, 0.4 * cm))

        if d.get("fig_bytes") is not None:
            d["fig_bytes"].seek(0)
            img = Image(d["fig_bytes"], width=largura_pagina - 3 * cm, height=10 * cm)
            historia.append(img)

        historia.append(Spacer(1, 0.3 * cm))
        historia.append(
            Paragraph(
                f"Relatorio TCC - {nome} | Anomalia {tipo}{anom_num} | Volta {volta_num} | {data_hora}",
                estilo_rodape,
            )
        )

    doc.build(historia)
    print(f"PDF gerado: {caminho_pdf}")
    return caminho_pdf


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
        raise Exception("Rode o Codigo 2 primeiro.")

    df_ideal = pd.read_csv(ARQUIVO_IDEAL)
    df_anom = pd.read_csv(ARQUIVO_ANOMALIAS)
    eixo_pct = df_ideal["progresso_pct"].values
    steer_med = df_ideal["steering_medio"].values

    print(f"Baseline: {len(eixo_pct)} pontos")
    print(f"Anomalias para analisar: {len(df_anom)}")

    pdfs_gerados = []

    for nome in df_anom["piloto"].unique():
        df_anom_piloto = df_anom[df_anom["piloto"] == nome].reset_index(drop=True)
        print(f"\n{'=' * 60}")
        print(f"   CARREGANDO: {nome.upper()} ({len(df_anom_piloto)} anomalia(s))")
        print(f"{'=' * 60}")

        caminhos = PILOTOS[nome]

        df_pupil = pd.read_csv(str(caminhos["pupila"]), sep=None, engine="python", on_bad_lines="skip")
        df_pupil.columns = [str(c).strip() for c in df_pupil.columns]

        c_p_m = [c for c in df_pupil.columns if "method" in c.lower()]
        if c_p_m:
            count_2d = df_pupil[c_p_m[0]].astype(str).str.contains(r"2d c\+\+", regex=True, case=False).sum()
            count_3d = df_pupil[c_p_m[0]].astype(str).str.contains("pye3d", regex=True, case=False).sum()
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

        t_sync_m = float(df_anom_piloto["t_sync_m"].iloc[0])
        frame_sync = int(input(f"\nFRAME do Marco Zero no Pupil Player [{nome}]: ").strip())
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
        t_series = clean_col(df_m, ["Time"])
        df_m["t_sync"] = t_series - t_sync_m
        df_m["steer"] = clean_col(df_m, ["Steering Angle"])
        df_m["acel"] = clean_col(df_m, ["Throttle Pos"])
        df_m["freio"] = clean_col(df_m, ["Brake Pos"])
        df_m = df_m.dropna(subset=["t_sync"])

        t_motec = df_m["t_sync"].values
        steer_raw = df_m["steer"].values
        acel_raw = df_m["acel"].values
        freio_raw = df_m["freio"].values

        lista_anomalias_piloto = []

        for _, row in df_anom_piloto.iterrows():
            volta_num = int(row["volta_num"])
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
                print(f"Dados insuficientes para {tipo}{anom_num} - pulando")
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

            m_antes = (t_pupila >= t_anom_ini - 1.0) & (t_pupila < t_anom_ini)
            m_durante = (t_pupila >= t_anom_ini) & (t_pupila < t_anom_fim)
            m_depois = (t_pupila >= t_anom_fim) & (t_pupila < t_anom_fim + 1.0)
            d_antes = np.nanmean(diam_pupila[m_antes]) if m_antes.sum() > 0 else np.nan
            d_durante = np.nanmean(diam_pupila[m_durante]) if m_durante.sum() > 0 else np.nan
            d_depois = np.nanmean(diam_pupila[m_depois]) if m_depois.sum() > 0 else np.nan
            delta_d = d_durante - d_antes if not (np.isnan(d_antes) or np.isnan(d_durante)) else np.nan

            trs = {}
            if t_primeiro is not None:
                for sinal, t_on in onsets_validos.items():
                    trs[f"TR_{sinal.lower()}_s"] = round(t_on - t_primeiro, 4)

            cor = CORES_TIPO[tipo]
            cores_onset = {
                "Steering": "#2980b9",
                "Acelerador": "#e67e22",
                "Freio": "#27ae60",
                "Pupila": "#8e44ad",
            }

            fig_an = plt.figure(figsize=(14, 9))
            fig_an.suptitle(
                f"Anomalia {tipo}{anom_num} - Volta {volta_num} - {nome}\n"
                f"{LABELS_TIPO[tipo]} | {ini_pct:.1f}% - {fim_pct:.1f}%",
                fontsize=10,
                fontweight="bold",
            )
            gs = gridspec.GridSpec(3, 1, height_ratios=[1.4, 1.2, 2.0], hspace=0.45)
            ax_pup = fig_an.add_subplot(gs[0])
            ax_pedal = fig_an.add_subplot(gs[1], sharex=ax_pup)
            ax_steer = fig_an.add_subplot(gs[2], sharex=ax_pup)

            if len(t_p_jan) > 1:
                ax_pup.plot(t_p_jan, d_jan, color="purple", linewidth=1.6, label="Pupila")
                if not np.isnan(d_antes):
                    ax_pup.axhline(
                        d_antes, color="gray", linewidth=1, linestyle=":", label=f"Baseline: {d_antes:.1f}mm"
                    )
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

            ax_pedal.plot(t_m_jan, a_jan, color="orange", linewidth=1.4, label="Acelerador")
            ax_pedal.plot(t_m_jan, f_jan, color="green", linewidth=1.4, label="Freio")
            ax_pedal.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.15)
            ax_pedal.axvline(t_anom_ini, color=cor, linewidth=1.8, linestyle="--")
            ax_pedal.set_ylabel("%", fontsize=8)
            ax_pedal.set_title("Pedais", fontsize=8)
            ax_pedal.legend(loc="upper right", fontsize=6)
            ax_pedal.grid(True, alpha=0.3)

            if len(eixo_pct) > 0:
                mask_ideal = (eixo_pct >= max(0, ini_pct - 5)) & (eixo_pct <= min(100, fim_pct + 5))
                if mask_ideal.any():
                    t_ideal_jan = np.linspace(t_jan_ini, t_jan_fim, mask_ideal.sum())
                    ax_steer.plot(
                        t_ideal_jan,
                        steer_med[mask_ideal],
                        color="gray",
                        linewidth=2,
                        linestyle="--",
                        label="Ideal",
                        zorder=3,
                    )

            ax_steer.plot(t_m_jan, s_jan, color="#2980b9", linewidth=1.6, label="Steering piloto", zorder=5)
            ax_steer.axvspan(t_anom_ini, t_anom_fim, color=cor, alpha=0.20, label="Anomalia")
            ax_steer.axvline(t_anom_ini, color=cor, linewidth=2.2, linestyle="--", label=f"Inicio ({t_anom_ini:.2f}s)")

            for sinal in ordem_reacao:
                t_on = onsets_validos[sinal]
                tr = t_on - t_primeiro if t_primeiro is not None else 0
                ax_steer.axvline(
                    t_on,
                    color=cores_onset[sinal],
                    linewidth=1.6,
                    linestyle=":",
                    alpha=0.9,
                    label=f"{sinal} (TR={tr:+.3f}s)",
                )
                if t_primeiro is not None and sinal != primeiro_sinal:
                    y_seta = np.nanmin(s_jan) * 0.85 if np.nanmin(s_jan) < 0 else 5
                    ax_steer.annotate(
                        "",
                        xy=(t_on, y_seta),
                        xytext=(t_primeiro, y_seta),
                        arrowprops=dict(arrowstyle="<->", color=cores_onset[sinal], lw=1.2),
                    )
                    ax_steer.text(
                        (t_on + t_primeiro) / 2,
                        y_seta * 1.2,
                        f"TR={tr:+.3f}s",
                        fontsize=6,
                        color=cores_onset[sinal],
                        ha="center",
                        fontweight="bold",
                    )

            ordem_str = " -> ".join(ordem_reacao) if ordem_reacao else "N/D"
            ax_steer.set_title(f"Steering | Ordem: {ordem_str}", fontsize=8)
            ax_steer.set_ylabel("Steering (graus)", fontsize=8)
            ax_steer.set_xlabel("Tempo Sincronizado (s)", fontsize=8)
            ax_steer.legend(loc="upper right", fontsize=6)
            ax_steer.grid(True, alpha=0.3)

            plt.tight_layout()
            fig_bytes = fig_para_bytes(fig_an)
            plt.close(fig_an)

            dado_anomalia = {
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
            }
            dado_anomalia.update(trs)
            lista_anomalias_piloto.append(dado_anomalia)

            print(
                f"Anomalia {tipo}{anom_num} (Volta {volta_num}): "
                f"1o sinal={primeiro_sinal} | ordem={' -> '.join(ordem_reacao)}"
            )

        if lista_anomalias_piloto:
            caminho_pdf = gerar_pdf_piloto(nome, lista_anomalias_piloto, str(PASTA_SAIDA_PDF))
            pdfs_gerados.append(caminho_pdf)
        else:
            print(f"Nenhuma anomalia com dados suficientes para {nome} - PDF nao gerado")

    print(f"\n{'=' * 60}")
    print(f"PDFs gerados: {len(pdfs_gerados)}")
    for caminho in pdfs_gerados:
        print(f"- {caminho}")
    print(f"{'=' * 60}")


def main():
    try:
        executar()
    except Exception as e:
        import traceback

        print(f"\nDEU RUIM: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
