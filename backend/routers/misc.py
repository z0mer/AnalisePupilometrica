"""
backend/routers/misc.py
========================
Endpoints utilitários: health check e traçado ideal.
"""
from __future__ import annotations

from fastapi import APIRouter

from backend.config import SAIDAS_DIR

router = APIRouter(prefix="/api", tags=["Utilitários"])


@router.get("/health", summary="Verifica se a API está online")
def health():
    return {"status": "ok"}


@router.get("/tracado-ideal", summary="Retorna a URL do PNG do traçado ideal mais recente")
def tracado_ideal():
    png_path = SAIDAS_DIR / "volta_ideal" / "volta_ideal.png"
    url = "/static/volta_ideal/volta_ideal.png" if png_path.exists() else None
    return {"url": url}


@router.get("/csv-geral", summary="Retorna a URL do CSV consolidado de todos os pilotos")
def csv_geral():
    csv_path = SAIDAS_DIR / "graficos_tr" / "relatorio_TR.csv"
    url = "/static/graficos_tr/relatorio_TR.csv" if csv_path.exists() else None
    return {"url": url}
