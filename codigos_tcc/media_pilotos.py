import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

from codigos_tcc.configuracao import (
    ARQUIVO_GRAFICO_IDEAL,
    ARQUIVO_IDEAL,
    ARQUIVO_VOLTAS,
    PILOTOS,
    validar_arquivos_base,
)

N_PONTOS = 1000

def tradutor_de_tempos(valor):
    v = str(valor).strip().lower().replace(',', '.')
    if ':' in v:
        parts = v.split(':')
        if len(parts) == 2: return int(parts[0]) * 60 + float(parts[1])
    if v.count('.') == 2:
        p = v.split('.')
        return int(p[0]) * 60 + float(f"{p[1]}.{p[2]}")
    return float(v)

def force_float(val):
    if pd.isna(val): return np.nan
    s = str(val).strip().replace(',', '.')
    if s.count('.') > 1:
        parts = s.rsplit('.', 1)
        s = parts[0].replace('.', '') + '.' + parts[1]
    try: return float(s)
    except: return np.nan

def limpa_diametro(x):
    s = str(x).strip().replace(',', '.')
    if s.count('.') > 1: s = s.replace('.', ''); s = s[:2] + '.' + s[2:]
    return pd.to_numeric(s, errors='coerce')

def atirar_com_sniper(frame_alvo, df, col_wi, col_t):
    match_exato = df[df[col_wi] == frame_alvo]
    if not match_exato.empty:
        return force_float(match_exato[col_t].iloc[0])
    idx_mais_perto = (df[col_wi] - frame_alvo).abs().idxmin()
    frame_encontrado = df.loc[idx_mais_perto, col_wi]
    diff = abs(frame_encontrado - frame_alvo)
    tag = "⚠️  ATENÇÃO: diferença grande!" if diff > 30 else "🎯"
    print(f"   {tag} Frame {frame_alvo} ausente → usando {frame_encontrado} (diff: {diff})")
    return force_float(df.loc[idx_mais_perto, col_t])

def clean_col(df, name_list):
    for name in name_list:
        target = [c for c in df.columns if c.lower() == name.lower()]
        if not target:
            target = [c for c in df.columns if name.lower() in c.lower()]
        if target:
            series = pd.to_numeric(df[target[0]].astype(str).str.replace(',', '.', regex=False), errors='coerce')
            print(f"   ✅ '{name}' → '{target[0]}' | não-nulos: {series.notna().sum()}")
            return series, target[0]
    print(f"   ❌ Não encontrado: {name_list}")
    return None, None

def processar_piloto(nome, caminhos):
    print(f"\n{'='*60}")
    print(f"   👤 PILOTO: {nome.upper()}")
    print(f"{'='*60}")

    print("\n👑 Carregando Pupila...")
    df_pupil = pd.read_csv(str(caminhos['pupila']), sep=None, engine='python', on_bad_lines='skip')
    df_pupil.columns = [str(c).strip() for c in df_pupil.columns]

    c_p_m = [c for c in df_pupil.columns if 'method' in c.lower()]
    if c_p_m:
        count_2d = df_pupil[c_p_m[0]].astype(str).str.contains(r'2d c\+\+', regex=True, case=False).sum()
        count_3d = df_pupil[c_p_m[0]].astype(str).str.contains('pye3d', regex=True, case=False).sum()
        if count_3d > count_2d:
            df_pupil = df_pupil[df_pupil[c_p_m[0]].astype(str).str.contains('pye3d', regex=True, case=False, na=False)]
            print("   👁️ Pye3D detectado e filtrado!")
        else:
            df_pupil = df_pupil[df_pupil[c_p_m[0]].astype(str).str.contains(r'2d c\+\+', regex=True, case=False, na=False)]
            print("   👁️ 2D C++ detectado e filtrado!")

    c_p_t = [c for c in df_pupil.columns if 'timestamp' in c.lower()]
    if not c_p_t: raise Exception("Coluna 'timestamp' não encontrada!")
    c_p_t = c_p_t[0]

    c_p_wi = [c for c in df_pupil.columns if 'world_index' in c.lower()]
    if not c_p_wi: raise Exception("Coluna 'world_index' não encontrada!")
    c_p_wi = c_p_wi[0]

    c_p_d_list = [c for c in df_pupil.columns if 'diameter_3d' in c.lower()]
    if not c_p_d_list or df_pupil[c_p_d_list[0]].isna().all():
        c_p_d_list = [c for c in df_pupil.columns if 'diameter' in c.lower()]
    c_p_d = c_p_d_list[0]
    print(f"   Usando diâmetro: '{c_p_d}'")

    print(f"\n🏁 MARCO ZERO — {nome}")
    frame_sync = int(input(f"   🎬 [{nome}] FRAME do Marco Zero: "))
    t_sync_m   = tradutor_de_tempos(input(f"   🏎️  [{nome}] Tempo MoTeC do Marco Zero: "))
    t_sync_p   = atirar_com_sniper(frame_sync, df_pupil, c_p_wi, c_p_t)
    print(f"   Timestamp bruto Marco Zero: {t_sync_p}")

    df_pupil[c_p_t] = df_pupil[c_p_t].apply(force_float)
    df_pupil[c_p_d] = df_pupil[c_p_d].apply(limpa_diametro)
    df_pupil = df_pupil.dropna(subset=[c_p_t, c_p_d])

    t_mestre_raw = df_pupil[c_p_t].values - t_sync_p
    mediana_abs  = np.nanmedian(np.abs(t_mestre_raw))
    if   mediana_abs > 100_000: escala = 1_000_000.0; print("⚠️  Microssegundos → segundos")
    elif mediana_abs > 500:     escala = 1_000.0;     print("⚠️  Milissegundos → segundos")
    else:                       escala = 1.0;         print("✅ Já em segundos")
    t_mestre = t_mestre_raw / escala

    df_master = pd.DataFrame({'tempo_sync': t_mestre})
    df_master['diam_suav'] = df_pupil[c_p_d].rolling(window=5, center=True).mean().values

    print("\n📈 Lendo MoTeC...")
    df_motec = pd.read_csv(str(caminhos['motec']), skiprows=14, sep=None, engine='python', encoding='latin1', on_bad_lines='skip')
    df_motec.columns = [str(c).strip() for c in df_motec.columns]

    t_clean_series, _ = clean_col(df_motec, ['Time', 'tempo'])
    f_clean_series, _ = clean_col(df_motec, ['Brake Pos', 'freio', 'brk'])
    a_clean_series, _ = clean_col(df_motec, ['Throttle Pos', 'acel', 'thr'])
    s_clean_series, _ = clean_col(df_motec, ['Steering Angle', 'volante', 'whl'])

    df_motec['t_clean'] = t_clean_series
    df_motec['f_clean'] = f_clean_series
    df_motec['a_clean'] = a_clean_series
    df_motec['s_clean'] = s_clean_series
    df_motec = df_motec.dropna(subset=['t_clean'])

    t_m_orig = df_motec['t_clean'].values - t_sync_m
    for col, source in [('freio', 'f_clean'), ('acel', 'a_clean'), ('volante', 's_clean')]:
        if source in df_motec.columns and df_motec[source].notna().any():
            vals = df_motec[source].values.astype(float)
            df_master[col] = np.interp(t_mestre, t_m_orig, vals)
        else:
            print(f"   ⚠️ '{col}' não disponível.")

    print(f"\n🏆 VOLTA DE OURO — {nome}")
    frame_ini = int(input(f"   🎬 [{nome}] FRAME INICIAL da Volta: "))
    frame_fim = int(input(f"   🎬 [{nome}] FRAME FINAL da Volta: "))

    t_ini_sync = (atirar_com_sniper(frame_ini, df_pupil, c_p_wi, c_p_t) - t_sync_p) / escala
    t_fim_sync = (atirar_com_sniper(frame_fim, df_pupil, c_p_wi, c_p_t) - t_sync_p) / escala
    print(f"   Janela: {t_ini_sync:.2f}s → {t_fim_sync:.2f}s")

    t_ini_m_raw = input(f"   🏎️  [{nome}] Tempo INICIAL MoTeC (registro): ")
    t_fim_m_raw = input(f"   🏎️  [{nome}] Tempo FINAL MoTeC (registro): ")
    _ = tradutor_de_tempos(t_ini_m_raw) if t_ini_m_raw.strip() else 0
    _ = tradutor_de_tempos(t_fim_m_raw) if t_fim_m_raw.strip() else 0

    df_ouro = df_master[
        (df_master['tempo_sync'] >= t_ini_sync) &
        (df_master['tempo_sync'] <= t_fim_sync)
    ].copy()

    print(f"   📦 Linhas na volta: {len(df_ouro)}")
    if df_ouro.empty:
        raise Exception(f"Volta de ouro vazia para {nome}!")

    meta = {
        'piloto': nome,
        'volta_num': 1,
        't_ini': t_ini_sync,
        't_fim': t_fim_sync,
        't_sync_m': t_sync_m
    }

    return df_ouro, meta

def executar():
    validar_arquivos_base()
    resultados = {}
    todas_metas = []

    for nome, caminhos in PILOTOS.items():
        df_ouro, meta = processar_piloto(nome, caminhos)
        resultados[nome] = df_ouro
        todas_metas.append(meta)

    print(f"\n\n{'='*60}")
    print("   📐 NORMALIZANDO E CALCULANDO MÉDIA DAS VOLTAS DE OURO...")
    print(f"{'='*60}")

    eixo_norm = np.linspace(0, 100, N_PONTOS)
    canais = ['diam_suav', 'acel', 'freio', 'volante']
    dados_norm = {canal: [] for canal in canais}

    for nome, df in resultados.items():
        t = df['tempo_sync'].values
        t_pct = np.linspace(0, 100, len(t))
        for canal in canais:
            if canal in df.columns:
                vals_interp = np.interp(eixo_norm, t_pct, df[canal].values)
                dados_norm[canal].append(vals_interp)
                print(f"   ✅ {nome} / {canal}: {len(df[canal])} pts → {N_PONTOS}")
            else:
                dados_norm[canal].append(np.full(N_PONTOS, np.nan))
                print(f"   ⚠️ {nome} / {canal}: ausente")

    medias = {}
    sigmas = {}
    for canal in canais:
        stack = np.array(dados_norm[canal])
        medias[canal] = np.nanmean(stack, axis=0)
        sigmas[canal] = np.nanstd(stack,  axis=0)

    # ---------------------------------------------------------------
    # 📊 GRÁFICO: Limpo para TCC
    # ---------------------------------------------------------------
    fig2, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    fig2.suptitle('Traçado Ideal — Média das Voltas de Ouro (Limpo)', fontsize=14, fontweight='bold')

    ax1.plot(eixo_norm, medias['diam_suav'], color='purple', linewidth=2)
    ax1.fill_between(eixo_norm, medias['diam_suav'] - sigmas['diam_suav'], medias['diam_suav'] + sigmas['diam_suav'], alpha=0.15, color='purple')
    ax1.set_title('Dilatação da Pupila'); ax1.set_ylabel('Diâmetro (mm)'); ax1.grid(True, alpha=0.3)

    ax2.plot(eixo_norm, medias['acel'],  color='orange', linewidth=2, label='Acelerador')
    ax2.plot(eixo_norm, medias['freio'], color='green',  linewidth=2, label='Freio')
    ax2.fill_between(eixo_norm, medias['acel'] - sigmas['acel'], medias['acel'] + sigmas['acel'],  alpha=0.12, color='orange')
    ax2.fill_between(eixo_norm, medias['freio'] - sigmas['freio'], medias['freio'] + sigmas['freio'], alpha=0.12, color='green')
    ax2.set_title('Pedais'); ax2.set_ylabel('%'); ax2.legend(loc='upper right'); ax2.grid(True, alpha=0.3)

    ax3.plot(eixo_norm, medias['volante'], color='black', linewidth=2)
    ax3.fill_between(eixo_norm,
                     medias['volante'] - sigmas['volante'],
                     medias['volante'] + sigmas['volante'],
                     alpha=0.15, color='black', label='±1σ')
    ax3.set_title('Esterçamento do Volante'); ax3.set_ylabel('Graus')
    ax3.legend(loc='upper right'); ax3.grid(True, alpha=0.3)
    ax3.set_xlabel('Progresso da Volta (%)')
    plt.tight_layout()
    plt.savefig(ARQUIVO_GRAFICO_IDEAL, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"\n📸 Gráfico salvo em: {ARQUIVO_GRAFICO_IDEAL}")

    # ---------------------------------------------------------------
    # 💾 EXPORTA CSV PARA O CÓDIGO 2
    # ---------------------------------------------------------------
    df_ideal = pd.DataFrame({
        'progresso_pct':   eixo_norm,
        'steering_medio':  medias['volante'],
        'steering_sigma':  sigmas['volante'],
        'acel_medio':      medias['acel'],
        'acel_sigma':      sigmas['acel'],
        'freio_medio':     medias['freio'],
        'freio_sigma':     sigmas['freio'],
        'pupila_medio':    medias['diam_suav'],
        'pupila_sigma':    sigmas['diam_suav'],
    })
    df_ideal.to_csv(ARQUIVO_IDEAL, index=False)
    print(f"💾 Traçado ideal salvo em: {ARQUIVO_IDEAL}")
    
    pd.DataFrame(todas_metas).to_csv(ARQUIVO_VOLTAS, index=False)
    print(f"💾 Metadados das voltas salvos em: {ARQUIVO_VOLTAS}")

    _persistir_banco_media(df_ideal, todas_metas, resultados)

def _persistir_banco_media(df_ideal, todas_metas, resultados):
    try:
        from backend.database import SessionLocal
        from backend.db_ops import (
            get_or_create_piloto, get_or_create_sessao,
            upsert_parametros_sync, upsert_volta,
            upsert_tracado_ideal, upsert_serie_temporal,
        )
        db = SessionLocal()
        try:
            sessao = get_or_create_sessao(db, "InterTatus")
            pilotos_ids = []
            for meta in todas_metas:
                nome = meta['piloto']
                piloto = get_or_create_piloto(db, nome)
                pilotos_ids.append(piloto.id)
                upsert_parametros_sync(db, sessao.id, piloto.id, t_sync_motec_s=meta['t_sync_m'])
                volta = upsert_volta(
                    db, sessao.id, piloto.id,
                    numero_volta=int(meta['volta_num']),
                    t_ini=meta['t_ini'],
                    t_fim=meta['t_fim'],
                    duracao=meta['t_fim'] - meta['t_ini'],
                    eh_ouro=True,
                )
                df_o = resultados[nome]
                upsert_serie_temporal(db, volta.id, "motec", {
                    "t":       df_o["tempo_sync"].tolist(),
                    "acel":    df_o["acel"].tolist() if "acel" in df_o.columns else [],
                    "freio":   df_o["freio"].tolist() if "freio" in df_o.columns else [],
                    "volante": df_o["volante"].tolist() if "volante" in df_o.columns else [],
                })
                upsert_serie_temporal(db, volta.id, "pupila", {
                    "t":    df_o["tempo_sync"].tolist(),
                    "diam": df_o["diam_suav"].tolist(),
                })
            upsert_tracado_ideal(db, sessao.id, df_ideal, pilotos_ids)
            db.commit()
            print(f"✅ [DB] Traçado ideal e {len(todas_metas)} volta(s)-ouro persistidas.")
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️  [DB] Falha ao persistir — análise não afetada. Erro: {e}")

def main():
    try:
        executar()
    except Exception as e:
        import traceback
        print(f"\n🚨 DEU RUIM: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()