"""
backend/routers/sessoes.py
==========================
Endpoints relacionados a sessões de corrida.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.db_ops import get_or_create_sessao
from backend.models import Sessao

router = APIRouter(prefix="/api", tags=["Sessões"])


class SessaoCreate(BaseModel):
    nome: str


@router.get("/sessoes", summary="Lista todas as sessões cadastradas")
def listar_sessoes(db: Session = Depends(get_db)):
    sessoes = db.query(Sessao).order_by(Sessao.criado_em.desc()).all()
    return [{"id": s.id, "nome": s.nome} for s in sessoes]


@router.post("/sessoes", status_code=201, summary="Cria ou recupera uma sessão")
def criar_sessao(payload: SessaoCreate, db: Session = Depends(get_db)):
    sessao = get_or_create_sessao(db, nome=payload.nome.strip())
    db.commit()
    return {"id": sessao.id, "nome": sessao.nome}
