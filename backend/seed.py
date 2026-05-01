"""
Carga inicial do banco de dados a partir dos CSVs já existentes em saidas/.

Execute UMA ÚNICA VEZ após criar as tabelas:

    python -m backend.seed

O script é idempotente: re-executá-lo atualiza os registros sem duplicar.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Garante que a raiz do projeto está no path quando executado como módulo
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, create_tables
from backend.db_ops import (
    get_or_create_piloto,
    get_or_create_sessao,
    inserir_blinks,
    upsert_anomalia,
    upsert_fixacao_anomalia,
    upsert_metrica_anomalia,
    upsert_parametros_sync,
    upsert_tracado_ideal,
    upsert_volta,
)
from backend.models import Anomalia as AnomaliaModel
from backend.models import TracadoIdeal as TracadoIdealModel
from backend.models import Volta as VoltaModel

# ---------------------------------------------------------------------------
# Caminhos dos CSVs de saída
# ---------------------------------------------------------------------------

SAIDAS = ROOT / "saidas"
ARQUIVO_VOLTAS_IND = SAIDAS / "volta_ideal" / "voltas_individuais.csv"
ARQUIVO_IDEAL = SAIDAS / "volta_ideal" / "tracado_ideal.csv"
ARQUIVO_ANOMALIAS = SAIDAS / "anomalias_detectadas.csv"
ARQUIVO_RELATORIO_TR = SAIDAS / "relatorio_TR.csv"

SESSAO_NOME = "InterTatus"


# ---------------------------------------------------------------------------
# Etapas de carga
# ---------------------------------------------------------------------------

def _etapa_pilotos(db, sessao):
    """Garante que os 3 pilotos existem no banco."""
    nomes = ["Humberto", "Rafa", "Varela"]
    pilotos = {n: get_or_create_piloto(db, n) for n in nomes}
    db.commit()
    print(f"  ✓ {len(pilotos)} pilotos verificados/inseridos")
    return pilotos


def _etapa_voltas_ouro(db, sessao, pilotos):
    """Insere voltas-ouro e parâmetros de sync (voltas_individuais.csv)."""
    if not ARQUIVO_VOLTAS_IND.exists():
        print(f"  ⚠  Arquivo não encontrado: {ARQUIVO_VOLTAS_IND}")
        return

    df = pd.read_csv(ARQUIVO_VOLTAS_IND)
    for _, row in df.iterrows():
        nome = row["piloto"]
        if nome not in pilotos:
            print(f"  ⚠  Piloto '{nome}' não cadastrado, pulando.")
            continue
        piloto = pilotos[nome]
        t_ini = float(row["t_ini"])
        t_fim = float(row["t_fim"])
        upsert_parametros_sync(
            db, sessao.id, piloto.id,
            t_sync_motec_s=float(row["t_sync_m"]),
        )
        upsert_volta(
            db, sessao.id, piloto.id,
            numero_volta=int(row["volta_num"]),
            t_ini=t_ini,
            t_fim=t_fim,
            duracao=t_fim - t_ini,
            eh_ouro=True,
        )
    db.commit()
    print(f"  ✓ {len(df)} volta(s)-ouro e parâmetros de sync inseridos")


def _etapa_tracado_ideal(db, sessao, pilotos):
    """Insere o traçado ideal normalizado (tracado_ideal.csv)."""
    if not ARQUIVO_IDEAL.exists():
        print(f"  ⚠  Arquivo não encontrado: {ARQUIVO_IDEAL}")
        return

    df = pd.read_csv(ARQUIVO_IDEAL)
    pilotos_ids = [p.id for p in pilotos.values()]
    upsert_tracado_ideal(db, sessao.id, df, pilotos_ids)
    db.commit()
    print(f"  ✓ Traçado ideal inserido ({len(df)} pontos)")


def _etapa_anomalias(db, sessao, pilotos):
    """
    Insere todas as anomalias detectadas (anomalias_detectadas.csv).
    Cria registros de Volta para voltas não-ouro se necessário.
    """
    if not ARQUIVO_ANOMALIAS.exists():
        print(f"  ⚠  Arquivo não encontrado: {ARQUIVO_ANOMALIAS}")
        return

    df = pd.read_csv(ARQUIVO_ANOMALIAS)

    # Garantir que todas as voltas referenciadas existem
    for (nome, volta_num), grp in df.groupby(["piloto", "volta_num"]):
        if nome not in pilotos:
            continue
        row0 = grp.iloc[0]
        t_ini = float(row0["t_ini_volta"])
        t_fim = float(row0["t_fim_volta"])
        upsert_volta(
            db, sessao.id, pilotos[nome].id,
            numero_volta=int(volta_num),
            t_ini=t_ini,
            t_fim=t_fim,
            duracao=t_fim - t_ini,
        )
    db.flush()

    # Buscar traçado ideal para FK
    ti = db.query(TracadoIdealModel).filter_by(sessao_id=sessao.id).first()
    ti_id = ti.id if ti else None

    count = 0
    for _, row in df.iterrows():
        nome = row["piloto"]
        if nome not in pilotos:
            continue
        volta = db.query(VoltaModel).filter_by(
            sessao_id=sessao.id,
            piloto_id=pilotos[nome].id,
            numero_volta=int(row["volta_num"]),
        ).first()
        if not volta:
            continue
        upsert_anomalia(
            db, volta.id,
            numero_anomalia=int(row["anom_num"]),
            tipo=str(row["tipo"]),
            ini_pct=float(row["ini_pct"]),
            fim_pct=float(row["fim_pct"]),
            t_ini_s=float(row["t_ini_volta"]),
            t_fim_s=float(row["t_fim_volta"]),
            tracado_ideal_id=ti_id,
        )
        count += 1

    db.commit()
    print(f"  ✓ {count} anomalia(s) inserida(s)")


def _etapa_metricas(db, sessao, pilotos):
    """
    Insere métricas detalhadas por anomalia (relatorio_TR.csv).
    Esse arquivo usa as mesmas chaves dos dicts internos dos scripts,
    então não é necessário renomear colunas.
    """
    if not ARQUIVO_RELATORIO_TR.exists():
        print(f"  ⚠  Arquivo não encontrado: {ARQUIVO_RELATORIO_TR}")
        return

    df = pd.read_csv(ARQUIVO_RELATORIO_TR)
    count = 0

    for _, row in df.iterrows():
        nome = row.get("piloto")
        if nome not in pilotos:
            continue

        volta = db.query(VoltaModel).filter_by(
            sessao_id=sessao.id,
            piloto_id=pilotos[nome].id,
            numero_volta=int(row["volta_num"]),
        ).first()
        if not volta:
            continue

        anom = db.query(AnomaliaModel).filter_by(
            volta_id=volta.id,
            numero_anomalia=int(row["anom_num"]),
        ).first()
        if not anom:
            continue

        # Enriquece a anomalia com dados do relatorio_TR que podem estar faltando
        if not anom.contexto_pista and row.get("contexto_pista"):
            anom.contexto_pista = str(row["contexto_pista"])
        if not anom.duracao_s and row.get("duracao_anom"):
            try:
                anom.duracao_s = float(row["duracao_anom"])
            except (TypeError, ValueError):
                pass

        row_dict = row.to_dict()
        upsert_metrica_anomalia(db, anom.id, row_dict)
        upsert_fixacao_anomalia(db, anom.id, row_dict)
        count += 1

    db.commit()
    print(f"  ✓ {count} métrica(s) detalhada(s) inserida(s)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def seed():
    print("=" * 55)
    print("  SEED — Carga inicial do banco de dados")
    print("=" * 55)

    print("\n[0] Criando tabelas (se não existirem)...")
    create_tables()
    print("  ✓ Tabelas verificadas")

    db = SessionLocal()
    try:
        sessao = get_or_create_sessao(
            db, SESSAO_NOME,
            descricao="Evento InterTatus — carga inicial via seed.py"
        )
        db.commit()
        print(f"\n[1] Sessão: '{SESSAO_NOME}' (id={sessao.id[:8]}...)")

        pilotos = _etapa_pilotos(db, sessao)

        print("\n[2] Voltas-ouro e parâmetros de sync...")
        _etapa_voltas_ouro(db, sessao, pilotos)

        print("\n[3] Traçado ideal...")
        _etapa_tracado_ideal(db, sessao, pilotos)

        print("\n[4] Anomalias detectadas...")
        _etapa_anomalias(db, sessao, pilotos)

        print("\n[5] Métricas detalhadas (relatorio_TR)...")
        _etapa_metricas(db, sessao, pilotos)

        print("\n" + "=" * 55)
        print("  SEED CONCLUÍDO COM SUCESSO")
        print("=" * 55)

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
