import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from codigos_tcc.configuracao import PILOTOS, validar_arquivos_base


def tradutor_de_tempos(valor):
    v = str(valor).strip().lower().replace(",", ".")
    if ":" in v:
        parts = v.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    if v.count(".") == 2:
        p = v.split(".")
        return int(p[0]) * 60 + float(f"{p[1]}.{p[2]}")
    return float(v)


def force_float(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip().replace(",", ".")
    if s.count(".") > 1:
        parts = s.rsplit(".", 1)
        s = parts[0].replace(".", "") + "." + parts[1]
    try:
        return float(s)
    except Exception:
        return np.nan


def limpa_diametro(x):
    s = str(x).strip().replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "")
        s = s[:2] + "." + s[2:]
    return pd.to_numeric(s, errors="coerce")


def atirar_com_sniper(frame_alvo, df, col_wi, col_t):
    match_exato = df[df[col_wi] == frame_alvo]
    if not match_exato.empty:
        return force_float(match_exato[col_t].iloc[0])

    idx_mais_perto = (df[col_wi] - frame_alvo).abs().idxmin()
    frame_encontrado = df.loc[idx_mais_perto, col_wi]
    diff = abs(frame_encontrado - frame_alvo)
    if diff > 30:
        print(
            f"   ATENCAO: Frame {frame_alvo} ausente. "
            f"Vizinho mais proximo: {frame_encontrado} (diferenca: {diff} frames)"
        )
    else:
        print(
            f"   Frame {frame_alvo} ausente, usando vizinho: "
            f"{frame_encontrado} (diferenca: {diff} frames)"
        )
    return force_float(df.loc[idx_mais_perto, col_t])


def clean_col(df, name_list):
    for name in name_list:
        target_exato = [c for c in df.columns if c.lower() == name.lower()]
        target_parcial = [c for c in df.columns if name.lower() in c.lower()]
        target = target_exato if target_exato else target_parcial
        if target:
            series = pd.to_numeric(
                df[target[0]].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            print(
                f"   '{name}' -> coluna '{target[0]}' | "
                f"nao nulos: {series.notna().sum()}"
            )
            return series
    print(f"   Nenhuma coluna encontrada para: {name_list}")
    return None


def escolher_piloto():
    opcoes = list(PILOTOS.keys())
    print("Pilotos disponiveis:")
    for indice, nome in enumerate(opcoes, start=1):
        print(f"{indice}. {nome}")

    escolha = input("Selecione o piloto: ").strip()
    if escolha.isdigit() and 1 <= int(escolha) <= len(opcoes):
        return opcoes[int(escolha) - 1]
    if escolha in PILOTOS:
        return escolha
    raise ValueError("Piloto invalido.")


def executar():
    validar_arquivos_base()
    piloto = escolher_piloto()
    arquivo_pupila = str(PILOTOS[piloto]["pupila"])
    arquivo_motec = str(PILOTOS[piloto]["motec"])

    if not os.path.exists(arquivo_pupila):
        raise FileNotFoundError(f"Pupila nao encontrada: {arquivo_pupila}")
    if not os.path.exists(arquivo_motec):
        raise FileNotFoundError(f"MoTeC nao encontrado: {arquivo_motec}")

    print("=" * 55)
    print(f"   CALIBRACAO INDIVIDUAL - {piloto}")
    print("=" * 55)

    print("\nCarregando Pupila...")
    df_pupil = pd.read_csv(arquivo_pupila, sep=None, engine="python", on_bad_lines="skip")
    df_pupil.columns = [str(c).strip() for c in df_pupil.columns]
    print(f"   Colunas encontradas: {list(df_pupil.columns)}")

    c_p_m = [c for c in df_pupil.columns if "method" in c.lower()]
    if c_p_m:
        count_2d = df_pupil[c_p_m[0]].astype(str).str.contains(
            r"2d c\+\+", regex=True, case=False
        ).sum()
        count_3d = df_pupil[c_p_m[0]].astype(str).str.contains(
            "pye3d", regex=True, case=False
        ).sum()
        if count_3d > count_2d:
            df_pupil = df_pupil[
                df_pupil[c_p_m[0]].astype(str).str.contains(
                    "pye3d", regex=True, case=False, na=False
                )
            ]
            print("   Metodo Pye3D detectado e filtrado.")
        else:
            df_pupil = df_pupil[
                df_pupil[c_p_m[0]].astype(str).str.contains(
                    r"2d c\+\+", regex=True, case=False, na=False
                )
            ]
            print("   Metodo 2D C++ detectado e filtrado.")

    c_p_t_list = [c for c in df_pupil.columns if "timestamp" in c.lower()]
    if not c_p_t_list:
        raise Exception("Coluna 'timestamp' nao encontrada na pupila.")
    c_p_t = c_p_t_list[0]

    c_p_wi_list = [c for c in df_pupil.columns if "world_index" in c.lower()]
    if not c_p_wi_list:
        raise Exception("Coluna 'world_index' nao encontrada.")
    c_p_wi = c_p_wi_list[0]

    c_p_d_list = [c for c in df_pupil.columns if "diameter_3d" in c.lower()]
    if not c_p_d_list or df_pupil[c_p_d_list[0]].isna().all():
        c_p_d_list = [c for c in df_pupil.columns if "diameter" in c.lower()]
    c_p_d = c_p_d_list[0]
    print(f"   Usando diametro: '{c_p_d}'")

    print("\nMARCO ZERO")
    frame_sync = int(input("FRAME exato no Pupil Player: "))
    t_sync_m = tradutor_de_tempos(input("Tempo no MOTEC (ex: 112.60): "))
    t_sync_p = atirar_com_sniper(frame_sync, df_pupil, c_p_wi, c_p_t)
    print(f"   Timestamp bruto do Marco Zero: {t_sync_p}")

    df_pupil[c_p_t] = df_pupil[c_p_t].apply(force_float)
    df_pupil[c_p_d] = df_pupil[c_p_d].apply(limpa_diametro)
    df_pupil = df_pupil.dropna(subset=[c_p_t, c_p_d])

    t_mestre_raw = df_pupil[c_p_t].values - t_sync_p
    mediana_abs = np.nanmedian(np.abs(t_mestre_raw))
    print(f"\nDiagnostico de escala: mediana(|t_mestre|) = {mediana_abs:.2f}")

    if mediana_abs > 100_000:
        escala = 1_000_000.0
        print("Timestamp em microssegundos. Convertendo para segundos.")
    elif mediana_abs > 500:
        escala = 1_000.0
        print("Timestamp em milissegundos. Convertendo para segundos.")
    else:
        escala = 1.0
        print("Timestamp ja em segundos.")

    t_mestre = t_mestre_raw / escala
    df_master = pd.DataFrame({"tempo_sync": t_mestre})
    df_master["diam_suav"] = (
        df_pupil[c_p_d].rolling(window=5, center=True).mean().values
    )

    print("\nLendo MoTeC...")
    df_motec = pd.read_csv(
        arquivo_motec,
        skiprows=14,
        sep=None,
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    df_motec.columns = [str(c).strip() for c in df_motec.columns]
    print(f"   Colunas MoTeC: {list(df_motec.columns)}")

    df_motec["t_clean"] = clean_col(df_motec, ["Time", "tempo"])
    df_motec["f_clean"] = clean_col(df_motec, ["Brake Pos", "freio", "brk"])
    df_motec["a_clean"] = clean_col(df_motec, ["Throttle Pos", "acel", "thr"])
    df_motec["s_clean"] = clean_col(df_motec, ["Steering Angle", "volante", "whl"])
    df_motec = df_motec.dropna(subset=["t_clean"])

    t_m_orig = df_motec["t_clean"].values - t_sync_m
    print(f"\nRange MoTeC (sync): {t_m_orig.min():.2f} -> {t_m_orig.max():.2f} s")
    print(f"Range Pupila (sync): {t_mestre.min():.2f} -> {t_mestre.max():.2f} s")

    for col, source in [("freio", "f_clean"), ("acel", "a_clean"), ("volante", "s_clean")]:
        if source in df_motec.columns and df_motec[source].notna().any():
            vals = df_motec[source].values.astype(float)
            df_master[col] = np.interp(t_mestre, t_m_orig, vals)
            print(
                f"   '{col}' interpolado | "
                f"range: {df_master[col].min():.3f} -> {df_master[col].max():.3f}"
            )
        else:
            print(f"   '{col}' nao disponivel, pulando.")

    print("\nVOLTA DE OURO")
    frame_ouro_ini = int(input("FRAME INICIAL da Volta de Ouro: "))
    frame_ouro_fim = int(input("FRAME FINAL da Volta de Ouro: "))

    t_ouro_p_ini = atirar_com_sniper(frame_ouro_ini, df_pupil, c_p_wi, c_p_t)
    t_ouro_p_fim = atirar_com_sniper(frame_ouro_fim, df_pupil, c_p_wi, c_p_t)

    t_ouro_ini_sync = (t_ouro_p_ini - t_sync_p) / escala
    t_ouro_fim_sync = (t_ouro_p_fim - t_sync_p) / escala
    print(f"   Janela da volta (sync): {t_ouro_ini_sync:.2f}s -> {t_ouro_fim_sync:.2f}s")

    input("Tempo INICIAL no MOTEC: ")
    input("Tempo FINAL no MOTEC: ")

    df_ouro = df_master[
        (df_master["tempo_sync"] >= t_ouro_ini_sync)
        & (df_master["tempo_sync"] <= t_ouro_fim_sync)
    ].copy()

    print(f"\nLinhas no recorte da volta: {len(df_ouro)}")

    if df_ouro.empty:
        print("\nVAZIO. Verifique os frames e os tempos MoTeC.")
        print(
            f"   df_master vai de {df_master['tempo_sync'].min():.2f} "
            f"a {df_master['tempo_sync'].max():.2f} s"
        )
        return

    print("Gerando grafico...")
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    ax1.plot(
        df_ouro["tempo_sync"], df_ouro["diam_suav"], color="purple", linewidth=2, label="Pupila"
    )
    ax1.set_title("Dilatacao da Pupila - Volta de Ouro")
    ax1.set_ylabel("Diametro (mm)")
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc="upper right")

    if "acel" in df_ouro.columns:
        ax2.plot(
            df_ouro["tempo_sync"], df_ouro["acel"], color="orange", label="Acelerador", alpha=0.8
        )
    if "freio" in df_ouro.columns:
        ax2.plot(
            df_ouro["tempo_sync"], df_ouro["freio"], color="green", label="Freio", alpha=0.8
        )
    ax2.set_title("Pedais (MoTeC)")
    ax2.set_ylabel("%")
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc="upper right")

    if "volante" in df_ouro.columns:
        ax3.plot(
            df_ouro["tempo_sync"], df_ouro["volante"], color="black", linewidth=1.5, label="Volante"
        )
    ax3.set_title("Estercamento do Volante (MoTeC)")
    ax3.set_ylabel("Graus")
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper right")

    plt.xlabel("Tempo (s) - Relativo a Linha de Chegada")
    plt.tight_layout()
    plt.show()


def main():
    try:
        executar()
    except Exception as e:
        import traceback

        print(f"\nDEU RUIM: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
