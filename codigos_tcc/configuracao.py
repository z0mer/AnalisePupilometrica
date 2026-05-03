from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DADOS_DIR = BASE_DIR / "dados"
SAIDAS_DIR = BASE_DIR / "saidas"
VOLTA_IDEAL_DIR = SAIDAS_DIR / "volta_ideal"
GRAFICOS_VOLTAS_DIR = SAIDAS_DIR / "graficos_voltas"
GRAFICOS_TR_DIR = SAIDAS_DIR / "graficos_tr"

for pasta in (SAIDAS_DIR, VOLTA_IDEAL_DIR, GRAFICOS_VOLTAS_DIR, GRAFICOS_TR_DIR):
    pasta.mkdir(parents=True, exist_ok=True)


PILOTOS = {
    "Humberto": {
        "pupila":    DADOS_DIR / "Bertinho_InterTatus" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Bertinho_InterTatus" / "fixations.csv",
        "motec":     DADOS_DIR / "Bertinho_InterTatus" / "Humberto.csv",
    },
    "Rafa": {
        "pupila":    DADOS_DIR / "Rafa_InterTatus" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Rafa_InterTatus" / "fixations.csv",
        "motec":     DADOS_DIR / "Rafa_InterTatus" / "Rafa.csv",
    },
    "Varela": {
        "pupila":    DADOS_DIR / "VV_InterTatus" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "VV_InterTatus" / "fixations.csv",
        "motec":     DADOS_DIR / "VV_InterTatus" / "Varela.csv",
    },
}


ARQUIVO_IDEAL = VOLTA_IDEAL_DIR / "tracado_ideal.csv"
ARQUIVO_VOLTAS = VOLTA_IDEAL_DIR / "voltas_individuais.csv"
ARQUIVO_GRAFICO_IDEAL = VOLTA_IDEAL_DIR / "volta_ideal.png"
ARQUIVO_ANOMALIAS = SAIDAS_DIR / "anomalias_detectadas.csv"
ARQUIVO_RELATORIO_TR = SAIDAS_DIR / "relatorio_TR.csv"


def validar_arquivos_base():
    faltando = []
    for nome, caminhos in PILOTOS.items():
        for tipo in ("pupila", "motec"):
            if not caminhos[tipo].exists():
                faltando.append(f"{nome} - {tipo}: {caminhos[tipo]}")
    if faltando:
        raise FileNotFoundError("Arquivos de entrada nao encontrados:\n" + "\n".join(faltando))
