"""
backend/routers/pilotos.py
==========================
Endpoints de consulta a pilotos, voltas e arquivos gerados.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import SAIDAS_DIR
from backend.database import get_db
from backend.models import Anomalia, ParametrosSync, Piloto, Volta

router = APIRouter(prefix="/api", tags=["Pilotos"])


@router.get("/pilotos/lista", summary="Lista todos os pilotos cadastrados")
def listar_pilotos(db: Session = Depends(get_db)):
    pilotos = db.query(Piloto).order_by(Piloto.nome).all()
    return [{"id": p.id, "nome": p.nome} for p in pilotos]


@router.get("/pilotos", summary="Busca um piloto pelo nome e retorna seus parâmetros de sync")
def buscar_piloto(nome: str, db: Session = Depends(get_db)):
    piloto = db.query(Piloto).filter_by(nome=nome.strip()).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto não encontrado")

    ps = db.query(ParametrosSync).filter_by(piloto_id=piloto.id).first()
    volta_ouro = (
        db.query(Volta)
        .filter_by(piloto_id=piloto.id, eh_volta_ouro=True)
        .order_by(Volta.criado_em.desc())
        .first()
    )

    tem_csvs_salvos = bool(ps and ps.dados_pupil and ps.dados_motec)

    return {
        "id": piloto.id,
        "nome": piloto.nome,
        "frame_sync": ps.frame_sync if ps else None,
        "frame_ini_pupil": volta_ouro.frame_ini_pupil if volta_ouro else None,
        "frame_fim_pupil": volta_ouro.frame_fim_pupil if volta_ouro else None,
        "t_ini_motec_s": volta_ouro.t_ini_sync_s if volta_ouro else None,
        "t_fim_motec_s": volta_ouro.t_fim_sync_s if volta_ouro else None,
        "numero_volta": volta_ouro.numero_volta if volta_ouro else 1,
        "tem_csvs_salvos": tem_csvs_salvos,
    }


@router.get(
    "/pilotos/{nome}/status",
    summary="Retorna se o piloto existe e se já foi processado (voltas/anomalias)",
)
def status_piloto(nome: str, db: Session = Depends(get_db)):
    piloto = db.query(Piloto).filter_by(nome=nome.strip()).first()
    if not piloto:
        return {"existe": False, "processado": False}

    n_voltas = db.query(Volta).filter_by(piloto_id=piloto.id).count()
    n_anomalias = (
        db.query(Anomalia)
        .join(Volta, Anomalia.volta_id == Volta.id)
        .filter(Volta.piloto_id == piloto.id)
        .count()
    )

    return {
        "existe": True,
        "processado": n_voltas > 0,
        "voltas": n_voltas,
        "anomalias": n_anomalias,
    }


@router.get(
    "/pilotos/{nome}/voltas",
    summary="Lista as voltas do piloto (exclui volta 0 e última volta)",
)
def listar_voltas_piloto(nome: str, db: Session = Depends(get_db)):
    piloto = db.query(Piloto).filter_by(nome=nome.strip()).first()
    if not piloto:
        raise HTTPException(status_code=404, detail="Piloto não encontrado")

    voltas = (
        db.query(Volta)
        .filter(Volta.piloto_id == piloto.id, Volta.numero_volta > 0)
        .order_by(Volta.numero_volta)
        .all()
    )
    # Exclui a última volta (geralmente incompleta)
    if len(voltas) > 1:
        voltas = voltas[:-1]

    return [
        {"numero_volta": v.numero_volta, "eh_volta_ouro": v.eh_volta_ouro}
        for v in voltas
    ]


@router.get(
    "/pilotos/{nome}/arquivos",
    summary="Retorna URLs dos gráficos, PDF de TR e CSV gerados para o piloto",
)
def arquivos_piloto(nome: str):
    graficos_dir = SAIDAS_DIR / "graficos_voltas"
    graficos_tr_dir = SAIDAS_DIR / "graficos_tr"

    graficos: list[str] = []
    if graficos_dir.exists():
        for f in sorted(graficos_dir.iterdir()):
            if f.suffix == ".png" and f.stem.endswith(f"_{nome}"):
                graficos.append(f"/static/graficos_voltas/{f.name}")

    relatorio_pdf: str | None = None
    pdf_path = graficos_tr_dir / f"Relatorio_TR_{nome}.pdf"
    if pdf_path.exists():
        relatorio_pdf = f"/static/graficos_tr/Relatorio_TR_{nome}.pdf"

    csv: str | None = None
    csv_path = graficos_tr_dir / f"CSV_{nome}.csv"
    if csv_path.exists():
        csv = f"/static/graficos_tr/CSV_{nome}.csv"

    return {"graficos": graficos, "relatorio_pdf": relatorio_pdf, "csv": csv}
