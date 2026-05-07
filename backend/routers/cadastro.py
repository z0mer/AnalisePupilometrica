"""
backend/routers/cadastro.py
============================
Endpoint de cadastro de piloto + parâmetros de sincronização + volta de ouro.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.db_ops import (
    get_or_create_piloto,
    get_or_create_sessao,
    upsert_parametros_sync,
    upsert_volta,
)
from backend.models import Piloto

router = APIRouter(prefix="/api", tags=["Cadastro"])


class CadastroPayload(BaseModel):
    sessao_nome: str
    piloto_nome: str
    frame_sync: Optional[int] = None
    frame_ini_pupil: Optional[int] = None
    frame_fim_pupil: Optional[int] = None
    t_ini_motec_s: Optional[float] = None
    t_fim_motec_s: Optional[float] = None
    numero_volta: int = 1


@router.post("/cadastro", status_code=201, summary="Salva parâmetros de piloto e volta de ouro")
def cadastrar(payload: CadastroPayload, db: Session = Depends(get_db)):
    ja_existia_piloto = (
        db.query(Piloto).filter_by(nome=payload.piloto_nome.strip()).first() is not None
    )

    sessao = get_or_create_sessao(db, nome=payload.sessao_nome.strip())
    piloto = get_or_create_piloto(db, nome=payload.piloto_nome.strip())

    upsert_parametros_sync(
        db,
        sessao_id=sessao.id,
        piloto_id=piloto.id,
        frame_sync=payload.frame_sync,
    )

    volta = upsert_volta(
        db,
        sessao_id=sessao.id,
        piloto_id=piloto.id,
        numero_volta=payload.numero_volta,
        eh_ouro=True,
        frame_ini_pupil=payload.frame_ini_pupil,
        frame_fim_pupil=payload.frame_fim_pupil,
        t_ini=payload.t_ini_motec_s,
        t_fim=payload.t_fim_motec_s,
    )

    db.commit()

    return {
        "sessao_id": sessao.id,
        "piloto_id": piloto.id,
        "volta_id": volta.id,
        "ja_existia": ja_existia_piloto,
    }
