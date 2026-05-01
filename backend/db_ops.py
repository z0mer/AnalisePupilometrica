"""
Operações reutilizáveis de banco de dados.
Usadas pelo seed.py (carga inicial) e pelos scripts de análise (persistência live).
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from backend.models import (
    Anomalia,
    Blink,
    FixacaoAnomalia,
    MetricaAnomalia,
    ParametrosSync,
    Piloto,
    Sessao,
    SerieTemporalVolta,
    TracadoIdeal,
    Volta,
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _f(row: dict, *keys) -> float | None:
    """Retorna o primeiro valor float não-nulo encontrado nas chaves dadas."""
    for k in keys:
        v = row.get(k)
        if v is None or v == "":
            continue
        try:
            f = float(v)
            return None if math.isnan(f) or math.isinf(f) else f
        except (TypeError, ValueError):
            pass
    return None


def _i(row: dict, *keys) -> int | None:
    """Retorna o primeiro valor int não-nulo encontrado nas chaves dadas."""
    for k in keys:
        v = row.get(k)
        if v is None or v == "":
            continue
        try:
            return int(float(v))
        except (TypeError, ValueError):
            pass
    return None


def _s(row: dict, *keys) -> str | None:
    """Retorna o primeiro valor string não-vazio encontrado nas chaves dadas."""
    for k in keys:
        v = row.get(k)
        if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
            continue
        return str(v).strip() or None
    return None


# ---------------------------------------------------------------------------
# Pilotos e Sessões
# ---------------------------------------------------------------------------

def get_or_create_piloto(db: Session, nome: str) -> Piloto:
    p = db.query(Piloto).filter_by(nome=nome).first()
    if not p:
        p = Piloto(nome=nome)
        db.add(p)
        db.flush()
    return p


def get_or_create_sessao(db: Session, nome: str, descricao: str | None = None) -> Sessao:
    s = db.query(Sessao).filter_by(nome=nome).first()
    if not s:
        s = Sessao(nome=nome, descricao=descricao)
        db.add(s)
        db.flush()
    return s


# ---------------------------------------------------------------------------
# Parâmetros de sincronização
# ---------------------------------------------------------------------------

def upsert_parametros_sync(
    db: Session,
    sessao_id: str,
    piloto_id: str,
    frame_sync: int | None = None,
    t_sync_motec_s: float | None = None,
    escala_timestamps: str | None = None,
) -> ParametrosSync:
    ps = db.query(ParametrosSync).filter_by(
        sessao_id=sessao_id, piloto_id=piloto_id
    ).first()
    if not ps:
        ps = ParametrosSync(sessao_id=sessao_id, piloto_id=piloto_id)
        db.add(ps)
    if frame_sync is not None:
        ps.frame_sync = frame_sync
    if t_sync_motec_s is not None:
        ps.t_sync_motec_s = t_sync_motec_s
    if escala_timestamps is not None:
        ps.escala_timestamps = escala_timestamps
    db.flush()
    return ps


# ---------------------------------------------------------------------------
# Voltas
# ---------------------------------------------------------------------------

def upsert_volta(
    db: Session,
    sessao_id: str,
    piloto_id: str,
    numero_volta: int,
    t_ini: float | None = None,
    t_fim: float | None = None,
    duracao: float | None = None,
    eh_ouro: bool = False,
) -> Volta:
    v = db.query(Volta).filter_by(
        sessao_id=sessao_id, piloto_id=piloto_id, numero_volta=numero_volta
    ).first()
    if not v:
        v = Volta(sessao_id=sessao_id, piloto_id=piloto_id, numero_volta=numero_volta)
        db.add(v)
    if t_ini is not None:
        v.t_ini_sync_s = t_ini
    if t_fim is not None:
        v.t_fim_sync_s = t_fim
    if duracao is not None:
        v.duracao_s = duracao
    if eh_ouro:
        v.eh_volta_ouro = True
    db.flush()
    return v


# ---------------------------------------------------------------------------
# Traçado ideal
# ---------------------------------------------------------------------------

def upsert_tracado_ideal(
    db: Session,
    sessao_id: str,
    df: pd.DataFrame,
    pilotos_ids: list[str],
) -> TracadoIdeal:
    ti = db.query(TracadoIdeal).filter_by(sessao_id=sessao_id).first()
    dados = {col: df[col].tolist() for col in df.columns}
    if not ti:
        ti = TracadoIdeal(
            sessao_id=sessao_id,
            n_pontos=len(df),
            dados=dados,
            pilotos_incluidos=pilotos_ids,
        )
        db.add(ti)
    else:
        ti.dados = dados
        ti.n_pontos = len(df)
        ti.pilotos_incluidos = pilotos_ids
    db.flush()
    return ti


# ---------------------------------------------------------------------------
# Séries temporais
# ---------------------------------------------------------------------------

def upsert_serie_temporal(
    db: Session,
    volta_id: str,
    tipo: str,
    dados: dict,
) -> SerieTemporalVolta:
    st = db.query(SerieTemporalVolta).filter_by(
        volta_id=volta_id, tipo=tipo
    ).first()
    n = len(next(iter(dados.values()), []))
    if not st:
        st = SerieTemporalVolta(volta_id=volta_id, tipo=tipo, dados=dados, n_amostras=n)
        db.add(st)
    else:
        st.dados = dados
        st.n_amostras = n
    db.flush()
    return st


# ---------------------------------------------------------------------------
# Anomalias
# ---------------------------------------------------------------------------

def upsert_anomalia(
    db: Session,
    volta_id: str,
    numero_anomalia: int,
    tipo: str,
    ini_pct: float,
    fim_pct: float,
    t_ini_s: float | None = None,
    t_fim_s: float | None = None,
    duracao_s: float | None = None,
    contexto_pista: str | None = None,
    tracado_ideal_id: str | None = None,
) -> Anomalia:
    a = db.query(Anomalia).filter_by(
        volta_id=volta_id, numero_anomalia=numero_anomalia
    ).first()
    if not a:
        a = Anomalia(
            volta_id=volta_id,
            numero_anomalia=numero_anomalia,
            tipo=tipo,
            ini_pct=ini_pct,
            fim_pct=fim_pct,
        )
        db.add(a)
    a.t_ini_s = t_ini_s
    a.t_fim_s = t_fim_s
    if duracao_s is not None:
        a.duracao_s = duracao_s
    if contexto_pista is not None:
        a.contexto_pista = contexto_pista
    if tracado_ideal_id is not None:
        a.tracado_ideal_id = tracado_ideal_id
    db.flush()
    return a


# ---------------------------------------------------------------------------
# Métricas de anomalia
# ---------------------------------------------------------------------------

def upsert_metrica_anomalia(db: Session, anomalia_id: str, row: dict) -> MetricaAnomalia:
    """
    Aceita tanto as chaves internas dos scripts (diam_antes_mm, TR_steering_s ...)
    quanto as chaves do relatorio_TR.csv — que são idênticas.
    """
    m = db.query(MetricaAnomalia).filter_by(anomalia_id=anomalia_id).first()
    if not m:
        m = MetricaAnomalia(anomalia_id=anomalia_id)
        db.add(m)

    m.diam_antes_mm = _f(row, "diam_antes_mm")
    m.diam_durante_mm = _f(row, "diam_durante_mm")
    m.diam_depois_mm = _f(row, "diam_depois_mm")
    m.delta_diam_mm = _f(row, "delta_diam_mm")
    m.tipo_resposta_pupilar = _s(row, "tipo_resposta_pupilar")
    m.tr_pupila_s = _f(row, "TR_pupila_s")
    m.tr_steering_s = _f(row, "TR_steering_s")
    m.tr_acelerador_s = _f(row, "TR_acelerador_s")
    m.tr_freio_s = _f(row, "TR_freio_s")
    m.primeiro_sinal = _s(row, "primeiro_sinal")

    ordem_raw = row.get("ordem_reacao")
    if ordem_raw and str(ordem_raw).strip():
        m.ordem_reacao = [x.strip() for x in str(ordem_raw).split("->")]

    m.n_picos_cognitivos = _i(row, "n_picos_cognitivos_janela")
    m.intensidade_media_picos = _f(row, "intensidade_media_picos")
    m.crescimento_pupilar_derivada = _f(row, "crescimento_pupilar_derivada")
    m.tempo_no_escuro_s = _f(row, "tempo_no_escuro_s")
    m.distancia_no_escuro_m = _f(row, "distancia_no_escuro_m")

    db.flush()
    return m


def upsert_fixacao_anomalia(db: Session, anomalia_id: str, row: dict) -> FixacaoAnomalia:
    """
    Aceita tanto as chaves internas quanto as do relatorio_TR.csv (idênticas).
    """
    f = db.query(FixacaoAnomalia).filter_by(anomalia_id=anomalia_id).first()
    if not f:
        f = FixacaoAnomalia(anomalia_id=anomalia_id)
        db.add(f)

    f.n_fixacoes = _i(row, "n_fixacoes_janela")
    f.dur_media_ms = _f(row, "dur_media_fix_ms")
    f.n_curtas = _i(row, "fix_curtas")
    f.n_longas = _i(row, "fix_longas")
    f.comportamento_visual = _s(row, "comportamento_visual")

    db.flush()
    return f


# ---------------------------------------------------------------------------
# Blinks
# ---------------------------------------------------------------------------

def inserir_blinks(db: Session, volta_id: str, blinks: list[dict]) -> int:
    """
    Insere eventos de piscada para uma volta (não faz upsert — apaga e re-insere).
    Cada dict deve ter: t_ini_s, t_fim_s, duracao_s, confidence.
    """
    db.query(Blink).filter_by(volta_id=volta_id).delete()
    for b in blinks:
        db.add(Blink(
            volta_id=volta_id,
            t_ini_s=float(b.get("t_ini_s", 0)),
            t_fim_s=float(b.get("t_fim_s", 0)),
            duracao_s=_f(b, "duracao_s"),
            confidence=_f(b, "confidence"),
        ))
    db.flush()
    return len(blinks)
