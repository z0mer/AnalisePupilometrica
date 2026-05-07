"""
backend/routers/processamento.py
=================================
Endpoint de processamento completo de sessão:
  1. Volta de ouro por piloto
  2. Traçado ideal (média das voltas de ouro)
  3. Detecção de anomalias por volta
  4. Análise de TR + geração de PDF/CSV
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.config import SAIDAS_DIR
from backend.database import get_db
from backend.db_ops import (
    get_or_create_sessao,
    upsert_anomalia,
    upsert_fixacao_anomalia,
    upsert_metrica_anomalia,
    upsert_serie_temporal,
    upsert_tracado_ideal,
    upsert_volta,
)
from backend.models import Anomalia, ParametrosSync, Piloto, TracadoIdeal, Volta
from backend.processamento.utils import force_float, limpa_diametro

router = APIRouter(prefix="/api", tags=["Processamento"])


@router.post(
    "/processar/sessao",
    status_code=200,
    summary="Processa uma sessão completa (volta de ouro → traçado ideal → anomalias → TR)",
    description="""
Recebe os CSVs de cada piloto e executa todo o pipeline de análise:

1. **Volta de ouro** — sincroniza Pupil + MoTeC para cada piloto
2. **Traçado ideal** — média das voltas de ouro normalizadas (0–100%)
3. **Anomalias** — detecta desvios tipo A/B/C em cada volta
4. **TR** — calcula tempo de reação e gera PDF/CSV (requer fixações)

Os arquivos gerados são salvos em `saidas/` e servidos via `/static/`.
""",
)
async def processar_sessao(
    sessao_nome: str = Form(...),
    piloto_nomes: List[str] = Form(...),
    pupil_csvs: List[UploadFile] = File(...),
    motec_csvs: List[UploadFile] = File(...),
    fixacoes_csvs: Optional[List[UploadFile]] = File(default=None),
    blinks_csvs: Optional[List[UploadFile]] = File(default=None),
    db: Session = Depends(get_db),
):
    from backend.processamento.pipeline import (
        calcular_tracado_ideal,
        carregar_blinks,
        carregar_fixacoes,
        carregar_motec,
        carregar_pupil,
        processar_anomalias_piloto,
        processar_tr_piloto,
        processar_volta_ouro,
    )

    n = len(piloto_nomes)
    if len(pupil_csvs) != n or len(motec_csvs) != n:
        raise HTTPException(
            status_code=422,
            detail="Número de arquivos deve ser igual ao número de pilotos.",
        )

    sessao_nome = sessao_nome.strip()
    sessao = get_or_create_sessao(db, nome=sessao_nome)

    # -------------------------------------------------------------------
    # Etapa 1 — Volta de ouro por piloto
    # -------------------------------------------------------------------
    resultados: list[dict] = []

    for i, nome_piloto in enumerate(piloto_nomes):
        nome_piloto = nome_piloto.strip()
        print(f"\n{'='*55}\n  PROCESSANDO: {nome_piloto.upper()}\n{'='*55}")

        piloto_obj = db.query(Piloto).filter_by(nome=nome_piloto).first()
        if not piloto_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Piloto '{nome_piloto}' não cadastrado. Use /api/cadastro primeiro.",
            )

        ps = db.query(ParametrosSync).filter_by(
            sessao_id=sessao.id, piloto_id=piloto_obj.id
        ).first()
        if not ps or ps.frame_sync is None:
            ps = db.query(ParametrosSync).filter_by(piloto_id=piloto_obj.id).first()
        if not ps or ps.frame_sync is None:
            raise HTTPException(
                status_code=422,
                detail=f"frame_sync ausente para '{nome_piloto}'. Cadastre via /api/cadastro.",
            )

        volta_ouro = (
            db.query(Volta)
            .filter_by(piloto_id=piloto_obj.id, eh_volta_ouro=True)
            .order_by(Volta.criado_em.desc())
            .first()
        )
        if not volta_ouro or volta_ouro.frame_ini_pupil is None:
            raise HTTPException(
                status_code=422,
                detail=f"Frames da volta de ouro ausentes para '{nome_piloto}'. Cadastre via /api/cadastro.",
            )

        frame_sync = ps.frame_sync
        t_sync_motec_s = ps.t_sync_motec_s or volta_ouro.t_ini_sync_s
        if t_sync_motec_s is None:
            raise HTTPException(
                status_code=422,
                detail=f"t_sync_motec_s ausente para '{nome_piloto}'.",
            )

        pupil_bytes = await pupil_csvs[i].read()
        motec_bytes = await motec_csvs[i].read()

        pupil_df = carregar_pupil(pupil_bytes)
        motec_df = carregar_motec(motec_bytes)

        df_ouro, motec_sinc, t_sync_p, escala = processar_volta_ouro(
            pupil_df=pupil_df,
            motec_df=motec_df,
            frame_sync=frame_sync,
            t_sync_motec_s=t_sync_motec_s,
            frame_ini_pupil=volta_ouro.frame_ini_pupil,
            frame_fim_pupil=volta_ouro.frame_fim_pupil,
            nome=nome_piloto,
        )

        # Fixações e blinks (opcionais)
        df_fix = None
        df_blink = None
        if fixacoes_csvs and i < len(fixacoes_csvs) and fixacoes_csvs[i]:
            fix_bytes = await fixacoes_csvs[i].read()
            df_fix = carregar_fixacoes(fix_bytes, t_sync_p, escala)
        if blinks_csvs and i < len(blinks_csvs) and blinks_csvs[i]:
            blink_bytes = await blinks_csvs[i].read()
            df_blink = carregar_blinks(blink_bytes, t_sync_p, escala)

        # Arrays de pupila sincronizados
        c_p_t_list = [c for c in pupil_df.columns if "timestamp" in c.lower()]
        c_p_d_list = [c for c in pupil_df.columns if "diameter_3d" in c.lower()]
        if not c_p_d_list or pupil_df[c_p_d_list[0]].isna().all():
            c_p_d_list = [c for c in pupil_df.columns if "diameter" in c.lower()]

        c_p_t = c_p_t_list[0] if c_p_t_list else None
        c_p_d = c_p_d_list[0] if c_p_d_list else None

        if c_p_t and c_p_d:
            pupil_clean = pupil_df.copy()
            pupil_clean[c_p_t] = pupil_clean[c_p_t].apply(force_float)
            pupil_clean[c_p_d] = pupil_clean[c_p_d].apply(limpa_diametro)
            pupil_clean = pupil_clean.dropna(subset=[c_p_t, c_p_d])
            t_pupila = (pupil_clean[c_p_t].values - t_sync_p) / escala
            diam_pupila = (
                pd.Series(pupil_clean[c_p_d].values)
                .rolling(window=5, center=True)
                .mean()
                .values
            )
        else:
            t_pupila = np.array([])
            diam_pupila = np.array([])

        # Persistir série temporal
        volta_db_ouro = (
            db.query(Volta)
            .filter_by(piloto_id=piloto_obj.id, eh_volta_ouro=True)
            .order_by(Volta.criado_em.desc())
            .first()
        )
        upsert_serie_temporal(db, volta_db_ouro.id, "motec", {
            "t":       df_ouro["tempo_sync"].tolist(),
            "acel":    df_ouro["acel"].tolist() if "acel" in df_ouro.columns else [],
            "freio":   df_ouro["freio"].tolist() if "freio" in df_ouro.columns else [],
            "volante": df_ouro["volante"].tolist() if "volante" in df_ouro.columns else [],
        })
        upsert_serie_temporal(db, volta_db_ouro.id, "pupila", {
            "t":    df_ouro["tempo_sync"].tolist(),
            "diam": df_ouro["diam_suav"].tolist(),
        })

        resultados.append({
            "nome":        nome_piloto,
            "piloto_id":   piloto_obj.id,
            "df_ouro":     df_ouro,
            "motec_sinc":  motec_sinc,
            "t_pupila":    t_pupila,
            "diam_pupila": diam_pupila,
            "df_fix":      df_fix,
            "df_blink":    df_blink,
        })

    # -------------------------------------------------------------------
    # Etapa 2 — Traçado Ideal
    # -------------------------------------------------------------------
    print("\n\nCALCULANDO TRACADO IDEAL...")
    voltas_para_ideal = [{"nome": r["nome"], "df_ouro": r["df_ouro"]} for r in resultados]
    df_ideal, png_ideal_bytes = calcular_tracado_ideal(voltas_para_ideal)

    volta_ideal_dir = SAIDAS_DIR / "volta_ideal"
    volta_ideal_dir.mkdir(parents=True, exist_ok=True)
    (volta_ideal_dir / "volta_ideal.png").write_bytes(png_ideal_bytes)
    print(f"Tracado ideal salvo em: {volta_ideal_dir / 'volta_ideal.png'}")

    pilotos_ids = [r["piloto_id"] for r in resultados]
    upsert_tracado_ideal(db, sessao.id, df_ideal, pilotos_ids)

    # -------------------------------------------------------------------
    # Etapa 3 — Anomalias por volta
    # -------------------------------------------------------------------
    graficos_voltas_dir = SAIDAS_DIR / "graficos_voltas"
    graficos_voltas_dir.mkdir(parents=True, exist_ok=True)
    graficos_tr_dir = SAIDAS_DIR / "graficos_tr"
    graficos_tr_dir.mkdir(parents=True, exist_ok=True)

    graficos_gerados: list[str] = []
    total_anomalias = 0
    todos_registros_csv: list[dict] = []  # acumula TR de todos os pilotos para CSV Geral

    ti_db = (
        db.query(TracadoIdeal)
        .filter_by(sessao_id=sessao.id)
        .order_by(TracadoIdeal.criado_em.desc())
        .first()
    )
    ti_id = ti_db.id if ti_db else None

    for r in resultados:
        nome_piloto = r["nome"]
        piloto_obj = db.query(Piloto).filter_by(nome=nome_piloto).first()

        df_fix_sync = r["df_fix"] if r["df_fix"] is not None else pd.DataFrame()
        df_blinks = r["df_blink"] if r["df_blink"] is not None else pd.DataFrame()

        anomalias, imagens = processar_anomalias_piloto(
            nome=nome_piloto,
            motec_sinc=r["motec_sinc"],
            t_pupila=r["t_pupila"],
            diam_pupila=r["diam_pupila"],
            df_ideal=df_ideal,
        )
        total_anomalias += len(anomalias)

        for nome_arq, img_bytes in imagens.items():
            caminho = graficos_voltas_dir / nome_arq
            caminho.write_bytes(img_bytes)
            graficos_gerados.append(f"/static/graficos_voltas/{nome_arq}")

        # Persistir anomalias
        for anom in anomalias:
            volta_num = anom["volta_num"]
            volta_db = db.query(Volta).filter_by(
                sessao_id=sessao.id,
                piloto_id=piloto_obj.id,
                numero_volta=volta_num,
            ).first()
            if not volta_db:
                volta_db = upsert_volta(
                    db, sessao.id, piloto_obj.id,
                    numero_volta=volta_num,
                    t_ini=anom["t_ini_volta"],
                    t_fim=anom["t_fim_volta"],
                    duracao=anom["t_fim_volta"] - anom["t_ini_volta"],
                )
            upsert_anomalia(
                db, volta_db.id,
                numero_anomalia=anom["anom_num"],
                tipo=anom["tipo"],
                ini_pct=anom["ini_pct"],
                fim_pct=anom["fim_pct"],
                t_ini_s=anom["t_ini_volta"],
                t_fim_s=anom["t_fim_volta"],
                tracado_ideal_id=ti_id,
            )

        # -------------------------------------------------------------------
        # Etapa 4 — Análise TR (opcional)
        # -------------------------------------------------------------------
        if not df_fix_sync.empty or len(anomalias) > 0:
            try:
                registros_csv, pdf_bytes, csv_bytes = processar_tr_piloto(
                    nome=nome_piloto,
                    anomalias_bruta=anomalias,
                    df_ideal=df_ideal,
                    motec_sinc=r["motec_sinc"],
                    t_pupila=r["t_pupila"],
                    diam_pupila=r["diam_pupila"],
                    df_fix_sync=df_fix_sync,
                    df_blinks=df_blinks,
                )

                if pdf_bytes:
                    pdf_path = graficos_tr_dir / f"Relatorio_TR_{nome_piloto}.pdf"
                    pdf_path.write_bytes(pdf_bytes)
                    print(f"PDF salvo: {pdf_path}")

                if csv_bytes:
                    csv_path = graficos_tr_dir / f"CSV_{nome_piloto}.csv"
                    csv_path.write_bytes(csv_bytes)
                    print(f"CSV salvo: {csv_path}")

                # Acumula para CSV Geral
                for rec in registros_csv:
                    todos_registros_csv.append({"piloto": nome_piloto, **rec})

                # Persistir métricas TR
                for rec in registros_csv:
                    volta_num = int(rec["volta_num"])
                    anom_num = int(rec["anom_num"])
                    volta_db2 = db.query(Volta).filter_by(
                        sessao_id=sessao.id,
                        piloto_id=piloto_obj.id,
                        numero_volta=volta_num,
                    ).first()
                    if volta_db2:
                        anom_db = db.query(Anomalia).filter_by(
                            volta_id=volta_db2.id,
                            numero_anomalia=anom_num,
                        ).first()
                        if anom_db:
                            upsert_metrica_anomalia(db, anom_db.id, rec)
                            upsert_fixacao_anomalia(db, anom_db.id, rec)

            except Exception as exc:
                print(f"  [AVISO] TR para {nome_piloto} falhou: {exc}")

    db.commit()

    # -------------------------------------------------------------------
    # CSV Geral consolidado (todos os pilotos)
    # -------------------------------------------------------------------
    csv_geral_url: str | None = None
    if todos_registros_csv:
        df_geral = pd.DataFrame(todos_registros_csv)
        csv_geral_bytes = df_geral.to_csv(index=False).encode("utf-8")
        (graficos_tr_dir / "relatorio_TR.csv").write_bytes(csv_geral_bytes)
        csv_geral_url = "/static/graficos_tr/relatorio_TR.csv"
        print(f"CSV Geral salvo: {graficos_tr_dir / 'relatorio_TR.csv'}")

    return {
        "sessao": sessao_nome,
        "pilotos_processados": len(resultados),
        "tracado_ideal_url": "/static/volta_ideal/volta_ideal.png",
        "graficos_voltas": graficos_gerados,
        "total_anomalias": total_anomalias,
        "csv_geral_url": csv_geral_url,
    }
