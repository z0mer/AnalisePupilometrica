"""
backend/routers/motec.py
========================
Endpoint para análise prévia do CSV do MoTeC:
lista as voltas disponíveis com seus limites de tempo.
"""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api", tags=["MoTeC"])


@router.post(
    "/listar-voltas-motec",
    summary="Analisa o CSV do MoTeC e devolve as voltas com limites de tempo",
    description=(
        "Ignora a volta 0 (saída do grid) e a última volta (geralmente incompleta). "
        "Use a resposta para popular o dropdown de voltas e auto-preencher "
        "MoTeC Inicial/Final no formulário."
    ),
)
async def listar_voltas_motec(motec_csv: UploadFile = File(...)):
    from backend.processamento.pipeline import carregar_motec
    from backend.processamento.utils import clean_col

    data = await motec_csv.read()
    df = carregar_motec(data)

    lap_s = clean_col(df, ["Session Lap Count", "Lap", "lap", "volta"])
    time_s = clean_col(df, ["Time", "tempo"])

    if lap_s is None or time_s is None:
        raise HTTPException(
            status_code=422,
            detail="Colunas 'Session Lap Count' ou 'Time' não encontradas no CSV do MoTeC.",
        )

    df = df.copy()
    df["_lap"] = lap_s
    df["_time"] = time_s
    df = df.dropna(subset=["_lap", "_time"])

    # Filtra volta 0 (aquecimento/saída do grid)
    df_v = df[df["_lap"] > 0]
    lap_counts = sorted(df_v["_lap"].unique())

    # Remove a última volta (incompleta ou de entrada dos boxes)
    if len(lap_counts) > 1:
        lap_counts = lap_counts[:-1]

    voltas = []
    for lc in lap_counts:
        mask = df_v["_lap"] == lc
        t_ini = float(df_v.loc[mask, "_time"].min())
        t_fim = float(df_v.loc[mask, "_time"].max())
        voltas.append(
            {
                "numero_volta": int(lc),
                "t_ini": round(t_ini, 4),
                "t_fim": round(t_fim, 4),
                "duracao": round(t_fim - t_ini, 4),
            }
        )

    # Detecta o Marco Zero (primeira queda de Car Pos Norm, ou None se ausente)
    t_sync_motec_s = None
    car_pos_col = clean_col(df, ["Car Pos Norm", "car_pos_norm", "CarPosNorm"])
    if car_pos_col is not None:
        df["_car_pos"] = car_pos_col
        df_sync = df.dropna(subset=["_car_pos", "_time"])
        queda = df_sync["_car_pos"].diff() < -0.5
        if queda.any():
            idx = queda.idxmax()
            t_sync_motec_s = round(float(df_sync.loc[idx, "_time"]), 4)

    return {"voltas": voltas, "t_sync_motec_s": t_sync_motec_s}
