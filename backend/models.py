
"""
ORM models — Sistema de Análise Pupilométrica e Telemetria Veicular
====================================================================

Hierarquia de entidades:

    Sessao ──┬── ParametrosSync ──── Piloto
             ├── Volta ─────────────┬── Piloto
             │                      ├── SerieTemporalVolta
             │                      ├── Blink
             │                      └── Anomalia ──┬── MetricaAnomalia
             │                                     └── FixacaoAnomalia
             └── TracadoIdeal
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Piloto
# ---------------------------------------------------------------------------

class Piloto(Base):
    """
    Cadastro dos pilotos participantes do estudo.
    Ex.: Humberto (Bertinho), Rafa, Varela.
    """
    __tablename__ = "pilotos"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    parametros_sync: Mapped[list["ParametrosSync"]] = relationship(
        back_populates="piloto", cascade="all, delete-orphan"
    )
    voltas: Mapped[list["Volta"]] = relationship(
        back_populates="piloto", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Piloto id={self.id!r} nome={self.nome!r}>"


# ---------------------------------------------------------------------------
# Sessao
# ---------------------------------------------------------------------------

class Sessao(Base):
    """
    Agrupamento lógico de uma rodada de análises (ex.: 'InterTatus — Maio/2024').
    Uma sessão contém os dados de N pilotos numa mesma pista/evento.
    """
    __tablename__ = "sessoes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    parametros_sync: Mapped[list["ParametrosSync"]] = relationship(
        back_populates="sessao", cascade="all, delete-orphan"
    )
    voltas: Mapped[list["Volta"]] = relationship(
        back_populates="sessao", cascade="all, delete-orphan"
    )
    tracados_ideais: Mapped[list["TracadoIdeal"]] = relationship(
        back_populates="sessao", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Sessao id={self.id!r} nome={self.nome!r}>"


# ---------------------------------------------------------------------------
# ParametrosSync
# ---------------------------------------------------------------------------

class ParametrosSync(Base):
    """
    Parâmetros de calibração e sincronização por (sessão × piloto).

    Captura o 'Marco Zero' definido manualmente pelo operador:
    - frame_sync: frame exato no Pupil Player
    - t_sync_motec_s: tempo correspondente no MoTeC (segundos)
    - escala_timestamps: escala detectada automaticamente dos timestamps do eye tracker
    """
    __tablename__ = "parametros_sync"
    __table_args__ = (
        UniqueConstraint("sessao_id", "piloto_id", name="uq_sync_sessao_piloto"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    sessao_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sessoes.id", ondelete="CASCADE"), nullable=False
    )
    piloto_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pilotos.id", ondelete="CASCADE"), nullable=False
    )
    # Marco Zero: frame do vídeo Pupil Player
    frame_sync: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Tempo no MoTeC correspondente ao frame_sync (segundos desde início da sessão)
    t_sync_motec_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "microseconds" | "milliseconds" | "seconds" — auto-detectado pelo pipeline
    escala_timestamps: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Bytes dos CSVs originais (permite reprocessar sem re-upload)
    dados_pupil: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    dados_motec: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    dados_fixacoes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    sessao: Mapped["Sessao"] = relationship(back_populates="parametros_sync")
    piloto: Mapped["Piloto"] = relationship(back_populates="parametros_sync")

    def __repr__(self) -> str:
        return (
            f"<ParametrosSync piloto={self.piloto_id!r} "
            f"frame={self.frame_sync} t_motec={self.t_sync_motec_s}>"
        )


# ---------------------------------------------------------------------------
# Volta
# ---------------------------------------------------------------------------

class Volta(Base):
    """
    Uma volta (lap) de um piloto numa sessão.

    - numero_volta corresponde ao valor de 'Session Lap Count' do MoTeC
    - t_ini_sync_s / t_fim_sync_s são os timestamps já sincronizados (eixo comum)
    - eh_volta_ouro indica a volta selecionada para compor o Traçado Ideal
    """
    __tablename__ = "voltas"
    __table_args__ = (
        UniqueConstraint(
            "sessao_id", "piloto_id", "numero_volta",
            name="uq_volta_sessao_piloto_num"
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    sessao_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sessoes.id", ondelete="CASCADE"), nullable=False
    )
    piloto_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("pilotos.id", ondelete="CASCADE"), nullable=False
    )
    numero_volta: Mapped[int] = mapped_column(Integer, nullable=False)
    t_ini_sync_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_fim_sync_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    duracao_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    eh_volta_ouro: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # start_frame_index do Pupil Player no início da melhor volta (etapa 4 da sincronização)
    frame_ini_pupil: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # start_frame_index do Pupil Player no fim da melhor volta (etapa 4 da sincronização)
    frame_fim_pupil: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    sessao: Mapped["Sessao"] = relationship(back_populates="voltas")
    piloto: Mapped["Piloto"] = relationship(back_populates="voltas")
    series_temporais: Mapped[list["SerieTemporalVolta"]] = relationship(
        back_populates="volta", cascade="all, delete-orphan"
    )
    anomalias: Mapped[list["Anomalia"]] = relationship(
        back_populates="volta", cascade="all, delete-orphan"
    )
    blinks: Mapped[list["Blink"]] = relationship(
        back_populates="volta", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Volta piloto={self.piloto_id!r} num={self.numero_volta} "
            f"ouro={self.eh_volta_ouro}>"
        )


# ---------------------------------------------------------------------------
# TracadoIdeal
# ---------------------------------------------------------------------------

class TracadoIdeal(Base):
    """
    Resultado do Script 2 (media_pilotos.py): os N pontos normalizados (0-100%)
    que representam o 'Comportamento Ideal' de referência do grupo.

    Os dados são armazenados em JSONB como arrays paralelos para leitura eficiente
    no frontend (um único SELECT retorna tudo que o gráfico precisa):

        dados = {
            "progresso_pct":  [0.0, 0.1, ..., 100.0],   # N valores
            "steering_medio": [...],
            "steering_sigma": [...],
            "acel_medio":     [...],
            "acel_sigma":     [...],
            "freio_medio":    [...],
            "freio_sigma":    [...],
            "pupila_medio":   [...],
            "pupila_sigma":   [...]
        }

    pilotos_incluidos = ["<uuid-humberto>", "<uuid-rafa>", "<uuid-varela>"]
    """
    __tablename__ = "tracados_ideais"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    sessao_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sessoes.id", ondelete="CASCADE"), nullable=False
    )
    n_pontos: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    # Arrays paralelos com todos os canais normalizados
    dados: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # Lista de UUIDs dos pilotos que contribuíram para esta média
    pilotos_incluidos: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    sessao: Mapped["Sessao"] = relationship(back_populates="tracados_ideais")
    anomalias: Mapped[list["Anomalia"]] = relationship(
        back_populates="tracado_ideal"
    )

    def __repr__(self) -> str:
        return f"<TracadoIdeal sessao={self.sessao_id!r} n_pontos={self.n_pontos}>"


# ---------------------------------------------------------------------------
# SerieTemporalVolta
# ---------------------------------------------------------------------------

class SerieTemporalVolta(Base):
    """
    Série temporal sincronizada de uma volta, armazenada como JSONB.

    tipo = "motec"  → dados contém: t, acel, freio, volante
    tipo = "pupila" → dados contém: t, diam (diâmetro suavizado, mm)

    Exemplo (motec):
        dados = {
            "t":       [0.0, 0.01, 0.02, ...],   # segundos (eixo sincronizado)
            "acel":    [100.0, 99.8, ...],         # %
            "freio":   [0.0, 0.0, ...],            # %
            "volante": [-0.5, -0.3, ...]           # graus
        }

    Exemplo (pupila):
        dados = {
            "t":    [0.0, 0.033, 0.066, ...],
            "diam": [40.2, 40.5, ...]             # mm (rolling mean 5 amostras)
        }
    """
    __tablename__ = "series_temporais_volta"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    volta_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("voltas.id", ondelete="CASCADE"), nullable=False
    )
    # "motec" ou "pupila"
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    dados: Mapped[dict] = mapped_column(JSONB, nullable=False)
    n_amostras: Mapped[int | None] = mapped_column(Integer, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    volta: Mapped["Volta"] = relationship(back_populates="series_temporais")

    def __repr__(self) -> str:
        return (
            f"<SerieTemporalVolta volta={self.volta_id!r} "
            f"tipo={self.tipo!r} n={self.n_amostras}>"
        )


# ---------------------------------------------------------------------------
# Anomalia
# ---------------------------------------------------------------------------

class Anomalia(Base):
    """
    Anomalia detectada pelo Script 3 (anomalias.py).

    Tipos:
      A — Sinal invertido de volante em curva (piloto vira ao contrário)
      B — Desvio excessivo em reta (|volante| > 15° quando ideal < 10°)
      C — Correção abrupta (derivada do volante > 8°/%)

    ini_pct / fim_pct: posição da anomalia em % de progresso da volta (0-100).
    t_ini_s / t_fim_s: timestamps absolutos sincronizados (segundos).
    contexto_pista: "Reta" ou "Curva" (inferido pelo steering do traçado ideal).
    """
    __tablename__ = "anomalias"
    __table_args__ = (
        UniqueConstraint("volta_id", "numero_anomalia", name="uq_anom_volta_num"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    volta_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("voltas.id", ondelete="CASCADE"), nullable=False
    )
    # FK opcional: permite saber qual traçado ideal foi usado na detecção
    tracado_ideal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tracados_ideais.id", ondelete="SET NULL"),
        nullable=True,
    )
    numero_anomalia: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(1), nullable=False)       # "A" | "B" | "C"
    ini_pct: Mapped[float] = mapped_column(Float, nullable=False)
    fim_pct: Mapped[float] = mapped_column(Float, nullable=False)
    t_ini_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    t_fim_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    duracao_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    contexto_pista: Mapped[str | None] = mapped_column(String(10), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    volta: Mapped["Volta"] = relationship(back_populates="anomalias")
    tracado_ideal: Mapped["TracadoIdeal | None"] = relationship(
        back_populates="anomalias"
    )
    metrica: Mapped["MetricaAnomalia | None"] = relationship(
        back_populates="anomalia", cascade="all, delete-orphan", uselist=False
    )
    fixacao: Mapped["FixacaoAnomalia | None"] = relationship(
        back_populates="anomalia", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return (
            f"<Anomalia volta={self.volta_id!r} num={self.numero_anomalia} "
            f"tipo={self.tipo!r} [{self.ini_pct:.1f}–{self.fim_pct:.1f}%]>"
        )


# ---------------------------------------------------------------------------
# MetricaAnomalia
# ---------------------------------------------------------------------------

class MetricaAnomalia(Base):
    """
    Métricas detalhadas calculadas pelo Script 4 (anomalias_individuais.py)
    para cada anomalia detectada.

    Cobre:
    - Variação pupilar: diâmetro antes / durante / depois da anomalia
    - Tempos de reação (TR): latência de cada sinal para responder à anomalia
    - Carga cognitiva: picos de derivada pupilar
    - Comportamento em trechos escuros (piscadas prolongadas)

    ordem_reacao: lista ordenada pelo tempo de onset, ex.:
        ["Freio", "Steering", "Acelerador", "Pupila"]
    """
    __tablename__ = "metricas_anomalia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    anomalia_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("anomalias.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # --- Variação pupilar ---
    diam_antes_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    diam_durante_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    diam_depois_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta_diam_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # "dilatacao" | "contracao" | "estavel"
    tipo_resposta_pupilar: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- Tempos de Reação (s) — negativos = antecipação, positivos = lag ---
    tr_pupila_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    tr_steering_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    tr_acelerador_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    tr_freio_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Sinal que respondeu primeiro
    primeiro_sinal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Lista ordenada pelo onset: ["Freio", "Steering", ...]
    ordem_reacao: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # --- Carga cognitiva ---
    n_picos_cognitivos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intensidade_media_picos: Mapped[float | None] = mapped_column(Float, nullable=True)
    crescimento_pupilar_derivada: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Comportamento em trechos escuros (piscadas / perda de rastreamento) ---
    tempo_no_escuro_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    distancia_no_escuro_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    anomalia: Mapped["Anomalia"] = relationship(back_populates="metrica")

    def __repr__(self) -> str:
        return (
            f"<MetricaAnomalia anom={self.anomalia_id!r} "
            f"delta={self.delta_diam_mm} tr_pupila={self.tr_pupila_s}>"
        )


# ---------------------------------------------------------------------------
# FixacaoAnomalia
# ---------------------------------------------------------------------------

class FixacaoAnomalia(Base):
    """
    Estatísticas de fixação ocular na janela de ±3 s ao redor de cada anomalia.

    comportamento_visual: classificação qualitativa derivada das fixações, ex.:
        "Exploracao visual normal", "Visao em tunel", "Busca visual dispersa"

    n_curtas: fixações < 100 ms (exploração, incerteza)
    n_longas: fixações > 800 ms (foco intenso, possível tunnel vision)
    """
    __tablename__ = "fixacoes_anomalia"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    anomalia_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("anomalias.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    n_fixacoes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dur_media_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_curtas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_longas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comportamento_visual: Mapped[str | None] = mapped_column(String(100), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    anomalia: Mapped["Anomalia"] = relationship(back_populates="fixacao")

    def __repr__(self) -> str:
        return (
            f"<FixacaoAnomalia anom={self.anomalia_id!r} "
            f"n={self.n_fixacoes} dur_media={self.dur_media_ms} ms>"
        )


# ---------------------------------------------------------------------------
# Blink
# ---------------------------------------------------------------------------

class Blink(Base):
    """
    Evento de piscada registrado pelo Pupil Labs para uma volta.

    Timestamps já convertidos para o eixo sincronizado (segundos).
    confidence: valor de confiança reportado pelo Pupil Labs [0-1].
    """
    __tablename__ = "blinks"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default=_uuid
    )
    volta_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("voltas.id", ondelete="CASCADE"), nullable=False
    )
    t_ini_s: Mapped[float] = mapped_column(Float, nullable=False)
    t_fim_s: Mapped[float] = mapped_column(Float, nullable=False)
    duracao_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=_now, server_default=func.now()
    )

    # Relacionamentos
    volta: Mapped["Volta"] = relationship(back_populates="blinks")

    def __repr__(self) -> str:
        return (
            f"<Blink volta={self.volta_id!r} "
            f"[{self.t_ini_s:.3f}–{self.t_fim_s:.3f}s] dur={self.duracao_s}>"
        )
