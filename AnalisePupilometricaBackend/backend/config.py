"""
backend/config.py
=================
Caminhos e constantes globais compartilhados por toda a aplicação.
"""
from pathlib import Path

# Raiz do projeto (AnalisePupilometrica/)
BASE_DIR = Path(__file__).resolve().parent.parent
SAIDAS_DIR = BASE_DIR / "saidas"
