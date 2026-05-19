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
    "Alexandre": {
        "pupila":  DADOS_DIR / "Ale_InterTatus" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Ale_InterTatus" / "fixations.csv",
        "motec":     DADOS_DIR / "Ale_InterTatus" / "Ale.csv",
        "blinks":     DADOS_DIR / "Ale_InterTatus" / "blinks.csv",
    },
    "Anna Carolina": {
        "pupila": DADOS_DIR / "Anna_InterTatus" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Anna_InterTatus" / "fixations.csv",
        "motec": DADOS_DIR / "Anna_InterTatus" / "Anna.csv",
        "blinks": DADOS_DIR / "Anna_InterTatus" / "blinks.csv",
    },
    "Bruno - Instrutor": {
        "pupila": DADOS_DIR / "BrunoInstr_InterPorsche" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "BrunoInstr_InterPorsche" / "fixations.csv",
        "motec": DADOS_DIR / "BrunoInstr_InterPorsche" / "BrunoInstr.csv",
        "blinks": DADOS_DIR / "BrunoInstr_InterPorsche" / "blinks.csv",
    },
    "Bruno T": {
        "pupila":  DADOS_DIR / "BrunoT_InterOnix" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "BrunoT_InterOnix" / "fixations.csv",
        "motec":     DADOS_DIR / "BrunoT_InterOnix" / "Bruno Tauan.csv",
        "blinks":     DADOS_DIR / "BrunoT_InterOnix" / "blinks.csv",
    },
    "Carloni": {
        "pupila":  DADOS_DIR / "Carloni_InterRSS" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Carloni_InterRSS" / "fixations.csv",
        "motec":     DADOS_DIR / "Carloni_InterRSS" / "Carloni.csv",
        "blinks":     DADOS_DIR / "Carloni_InterRSS" / "blinks.csv",
    },
    "César": {
        "pupila":  DADOS_DIR / "Cesar_InterRSS" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Cesar_InterRSS" / "fixations.csv",
        "motec":     DADOS_DIR / "Cesar_InterRSS" / "Cesar.csv",
        "blinks":     DADOS_DIR / "Cesar_InterRSS" / "blinks.csv",
    },
    "Chris": {
        "pupila": DADOS_DIR / "Chris_InterPorsche" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Chris_InterPorsche" / "fixations.csv",
        "motec": DADOS_DIR / "Chris_InterPorsche" / "Chris.csv",
        "blinks": DADOS_DIR / "Chris_InterPorsche" / "blinks.csv",
    },
    "Felipe Z.": {
        "pupila": DADOS_DIR / "Fe_InterRSS" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Fe_InterRSS" / "fixations.csv",
        "motec": DADOS_DIR / "Fe_InterRSS" / "Fe.csv",
        "blinks": DADOS_DIR / "Fe_InterRSS" / "blinks.csv",
    },
    "Gabriel": {
        "pupila": DADOS_DIR / "Gabriel_InterMustang" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Gabriel_InterMustang" / "fixations.csv",
        "motec": DADOS_DIR / "Gabriel_InterMustang" / "Gabriel.csv",
        "blinks": DADOS_DIR / "Gabriel_InterMustang" / "blinks.csv",
    },
    "Grota": {
        "pupila":  DADOS_DIR / "Grota_InterLambo" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Grota_InterLambo" / "fixations.csv",
        "motec":     DADOS_DIR / "Grota_InterLambo" / "Grota.csv",
        "blinks":     DADOS_DIR / "Grota_InterLambo" / "blinks.csv",
    },
    "Guilherme": {
        "pupila":  DADOS_DIR / "Guilherme_InterRSS" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Guilherme_InterRSS" / "fixations.csv",
        "motec":     DADOS_DIR / "Guilherme_InterRSS" / "Guilherme.csv",
        "blinks":     DADOS_DIR / "Guilherme_InterRSS" / "blinks.csv",
    },
    "Humberto": {
        "pupila": DADOS_DIR / "Humberto_InterPorsche" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Humberto_InterPorsche" / "fixations.csv",
        "motec": DADOS_DIR / "Humberto_InterPorsche" / "Humberto2.csv",
        "blinks": DADOS_DIR / "Humberto_InterPorsche" / "blinks.csv",
    },
    "Larissa": {
        "pupila": DADOS_DIR / "Lala_InterTatus" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Lala_InterTatus" / "fixations.csv",
        "motec": DADOS_DIR / "Lala_InterTatus" / "Lala.csv",
        "blinks": DADOS_DIR / "Lala_InterTatus" / "blinks.csv",
    },
    "Leonardo": {
        "pupila": DADOS_DIR / "Leo_InterPorsche" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Leo_InterPorsche" / "fixations.csv",
        "motec": DADOS_DIR / "Leo_InterPorsche" / "Leo.csv",
        "blinks": DADOS_DIR / "Leo_InterPorsche" / "blinks.csv",
    },
    "Lucca Z.": {
        "pupila": DADOS_DIR / "Lucca_InterPorsche" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Lucca_InterPorsche" / "fixations.csv",
        "motec": DADOS_DIR / "Lucca_InterPorsche" / "Lucca.csv",
        "blinks": DADOS_DIR / "Lucca_InterPorsche" / "blinks.csv",
    },
    "Matheus": {
        "pupila":  DADOS_DIR / "Matheus_InterMustang" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Matheus_InterMustang" / "fixations.csv",
        "motec":     DADOS_DIR / "Matheus_InterMustang" / "Matheus.csv",
        "blinks":     DADOS_DIR / "Matheus_InterMustang" / "blinks.csv",
    },
    "Niko": {
        "pupila": DADOS_DIR / "Niko_InterGTR" / "pupil_positions.csv",
        "fixations":  DADOS_DIR / "Niko_InterGTR" / "fixations.csv",
        "motec": DADOS_DIR / "Niko_InterGTR" / "Niko.csv",
        "blinks": DADOS_DIR / "Niko_InterGTR" / "blinks.csv",
    },
    "Rafa Velho": {
        "pupila":  DADOS_DIR / "Rafa_InterMustang" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Rafa_InterMustang" / "fixations.csv",
        "motec":     DADOS_DIR / "Rafa_InterMustang" / "Rafa.csv",
        "blinks":     DADOS_DIR / "Rafa_InterMustang" / "blinks.csv",
    }, 
    # "Rodi": {
    #     "pupila":  DADOS_DIR / "Rodi_InterMustang" / "pupil_positions.csv",
    #     "fixations": DADOS_DIR / "Rodi_InterMustang" / "fixations.csv",
    #     "motec":     DADOS_DIR / "Rodi_InterMustang" / "Rodi.csv",
    #     "blinks":     DADOS_DIR / "Rodi_InterMustang" / "blinks.csv",
    # },
    "Rodrigo": {
        "pupila":  DADOS_DIR / "Rodrigo_InterMustang" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Rodrigo_InterMustang" / "fixations.csv",
        "motec":     DADOS_DIR / "Rodrigo_InterMustang" / "Rodrigo.csv",
        "blinks":     DADOS_DIR / "Rodrigo_InterMustang" / "blinks.csv",
    }, 
    "Stefano": {
        "pupila":  DADOS_DIR / "Stefano_InterRSS" / "pupil_positions.csv",
        "fixations": DADOS_DIR / "Stefano_InterRSS" / "fixations.csv",
        "motec":     DADOS_DIR / "Stefano_InterRSS" / "Stefano.csv",
        "blinks":     DADOS_DIR / "Stefano_InterRSS" / "blinks.csv",
    },   
}


NIVEL_PILOTOS = {
    "Grota": "Pro",
    "Rafa Velho": "Pro",
    "Carloni": "Pro",
    "Niko": "Pro",
    "Felipe": "Pro",
    "Lucca": "Pro",
    "César": "Pro",
    "Guilherme": "Pro",
    "Gabriel": "Pro",
    "Stefano": "Pro"
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
