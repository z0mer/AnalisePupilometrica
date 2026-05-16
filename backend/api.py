"""
backend/api.py
==============
Ponto de entrada da aplicação FastAPI.
Cada domínio tem seu próprio router em backend/routers/.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import SAIDAS_DIR
from backend.database import create_tables
from backend.routers import cadastro, misc, motec, pilotos, processamento, sessoes

create_tables()

app = FastAPI(
    title="Análise Pupilométrica API",
    description="API para processamento de dados de pupilometria e telemetria MoTeC.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Arquivos estáticos gerados
# ---------------------------------------------------------------------------
SAIDAS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(SAIDAS_DIR)), name="static")

# ---------------------------------------------------------------------------
# Routers (ordem = ordem no Swagger)
# ---------------------------------------------------------------------------
app.include_router(sessoes.router)
app.include_router(pilotos.router)
app.include_router(cadastro.router)
app.include_router(motec.router)
app.include_router(processamento.router)
app.include_router(misc.router)
