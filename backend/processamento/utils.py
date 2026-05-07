"""
backend/processamento/utils.py
==============================
Funções auxiliares puras compartilhadas por todo o pipeline.
Sem leitura de disco, sem plt.show(), sem input().
"""
from __future__ import annotations

import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Conversão / limpeza de tipos
# ---------------------------------------------------------------------------

def force_float(val) -> float:
    """Converte um valor para float, tratando separadores de milhar e vírgula."""
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


def limpa_diametro(x) -> float:
    """Limpa e converte valores de diâmetro pupilar."""
    s = str(x).strip().replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "")
        s = s[:2] + "." + s[2:]
    return pd.to_numeric(s, errors="coerce")


def tradutor_de_tempos(valor) -> float:
    """Converte tempo no formato 'mm:ss.fff' ou 'mm.ss.fff' para segundos."""
    v = str(valor).strip().lower().replace(",", ".")
    if ":" in v:
        parts = v.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    if v.count(".") == 2:
        p = v.split(".")
        return int(p[0]) * 60 + float(f"{p[1]}.{p[2]}")
    return float(v)


# ---------------------------------------------------------------------------
# Busca de frame no DataFrame da pupila
# ---------------------------------------------------------------------------

def atirar_com_sniper(frame_alvo: int, df: pd.DataFrame, col_wi: str, col_t: str) -> float:
    """
    Retorna o timestamp do frame mais próximo a `frame_alvo` no DataFrame da pupila.
    Se a diferença for > 30 frames, emite um aviso (mas não falha).
    """
    match_exato = df[df[col_wi] == frame_alvo]
    if not match_exato.empty:
        return force_float(match_exato[col_t].iloc[0])

    idx_mais_perto = (df[col_wi] - frame_alvo).abs().idxmin()
    frame_encontrado = df.loc[idx_mais_perto, col_wi]
    diff = abs(frame_encontrado - frame_alvo)
    if diff > 30:
        print(
            f"   ATENCAO: Frame {frame_alvo} ausente. "
            f"Vizinho mais proximo: {frame_encontrado} (diferenca: {diff} frames)"
        )
    else:
        print(
            f"   Frame {frame_alvo} ausente, usando vizinho: "
            f"{frame_encontrado} (diferenca: {diff} frames)"
        )
    return force_float(df.loc[idx_mais_perto, col_t])


# ---------------------------------------------------------------------------
# Busca de coluna por nome (exato ou parcial)
# ---------------------------------------------------------------------------

def clean_col(df: pd.DataFrame, name_list: list[str]) -> pd.Series | None:
    """
    Procura no DataFrame uma coluna cujo nome corresponda a qualquer item de
    `name_list` (exato primeiro, parcial depois) e retorna a Series numérica.
    Retorna None se nenhuma coluna for encontrada.
    """
    for name in name_list:
        target_exato = [c for c in df.columns if c.lower() == name.lower()]
        target_parcial = [c for c in df.columns if name.lower() in c.lower()]
        target = target_exato if target_exato else target_parcial
        if target:
            series = pd.to_numeric(
                df[target[0]].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            print(f"   '{name}' -> coluna '{target[0]}' | nao nulos: {series.notna().sum()}")
            return series
    print(f"   Nenhuma coluna encontrada para: {name_list}")
    return None


# ---------------------------------------------------------------------------
# Conversão de figura matplotlib para bytes (sem salvar em disco)
# ---------------------------------------------------------------------------

def fig_para_bytes(fig: plt.Figure, dpi: int = 130) -> bytes:
    """Serializa uma figura matplotlib para PNG em memória (BytesIO → bytes)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    buf.seek(0)
    return buf.read()


# ---------------------------------------------------------------------------
# Constantes de detecção de anomalias (compartilhadas entre pipeline e api)
# ---------------------------------------------------------------------------

LIMIAR_RETA_GRAUS = 10.0
LIMIAR_SINAL_INVERTIDO_GRAUS = 20.0
LIMIAR_DESVIO_RETA_GRAUS = 15.0
LIMIAR_DERIVADA = 8.0
JANELA_SUAVIZACAO_DERIV = 5
DURACAO_MINIMA_PCT = 0.8
TOLERANCIA_GAP_PCT = 0.8

# Constantes TR (anomalias_individuais)
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
