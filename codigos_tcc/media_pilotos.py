import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

from codigos_tcc.configuracao import (
    ARQUIVO_GRAFICO_IDEAL,
    ARQUIVO_IDEAL,
    ARQUIVO_VOLTAS,
    PILOTOS,
    validar_arquivos_base,
)


N_PONTOS = 1000


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
    tag = "ATENCAO!" if diff > 30 else "INFO"
    print(f"   {tag} Frame {frame_alvo} ausente -> usando {frame_encontrado} (diff: {diff})")
    return force_float(df.loc[idx_mais_perto, col_t])


def clean_col(df, name_list):
    for name in name_list:
        target = [c for c in df.columns if c.lower() == name.lower()]
        if not target:
            target = [c for c in df.columns if name.lower() in c.lower()]
        if target:
            series = pd.to_numeric(
                df[target[0]].astype(str).str.replace(",", ".", regex=False),
                errors="coerce",
            )
            print(f"   '{name}' -> '{target[0]}' | nao nulos: {series.notna().sum()}")
            return series, target[0]
    print(f"   Nao encontrado: {name_list}")
    return None, None


def interpolar_volta(valores, n_pontos):
    mask_valido = ~np.isnan(valores)
    if mask_valido.sum() < 2:
        return np.full(n_pontos, np.nan)
    eixo_orig = np.linspace(0, 100, len(valores))
    eixo_novo = np.linspace(0, 100, n_pontos)
    return np.interp(eixo_novo, eixo_orig, valores)


def processar_piloto(nome, caminhos):
    print(f"\n{'=' * 60}")
    print(f"   PILOTO: {nome.upper()}")
    print(f"{'=' * 60}")

    print("\nCarregando Pupila...")
    df_pupil = pd.read_csv(str(caminhos["pupila"]), sep=None, engine="python", on_bad_lines="skip")
    df_pupil.columns = [str(c).strip() for c in df_pupil.columns]

    c_p_m = [c for c in df_pupil.columns if "method" in c.lower()]
    if c_p_m:
        count_2d = df_pupil[c_p_m[0]].astype(str).str.contains(
            r"2d c\+\+", regex=True, case=False
        ).sum()
        count_3d = df_pupil[c_p_m[0]].astype(str).str.contains(
            "pye3d", regex=True, case=False
        ).sum()
        metodo = "pye3d" if count_3d > count_2d else r"2d c\+\+"
        df_pupil = df_pupil[
            df_pupil[c_p_m[0]].astype(str).str.contains(metodo, regex=True, case=False, na=False)
        ]
        print(f"   Metodo: {'Pye3D' if count_3d > count_2d else '2D C++'}")

    c_p_t = [c for c in df_pupil.columns if "timestamp" in c.lower()][0]
    c_p_wi = [c for c in df_pupil.columns if "world_index" in c.lower()][0]
    c_p_d_list = [c for c in df_pupil.columns if "diameter_3d" in c.lower()]
    if not c_p_d_list or df_pupil[c_p_d_list[0]].isna().all():
        c_p_d_list = [c for c in df_pupil.columns if "diameter" in c.lower()]
    c_p_d = c_p_d_list[0]
    print(f"   Diametro: '{c_p_d}'")

    print(f"\nMARCO ZERO - {nome}")
    frame_sync = int(input(f"   [{nome}] FRAME do Marco Zero no Pupil Player: "))
    t_sync_m = tradutor_de_tempos(input(f"   [{nome}] Tempo MoTeC do Marco Zero: "))
    t_sync_p = atirar_com_sniper(frame_sync, df_pupil, c_p_wi, c_p_t)
    print(f"   Timestamp bruto Marco Zero: {t_sync_p}")

    df_pupil[c_p_t] = df_pupil[c_p_t].apply(force_float)
    df_pupil[c_p_d] = df_pupil[c_p_d].apply(limpa_diametro)
    df_pupil = df_pupil.dropna(subset=[c_p_t, c_p_d])

    t_raw = df_pupil[c_p_t].values - t_sync_p
    mediana_ab = np.nanmedian(np.abs(t_raw))
    if mediana_ab > 100_000:
        escala = 1_000_000.0
        print("   us -> s")
    elif mediana_ab > 500:
        escala = 1_000.0
        print("   ms -> s")
    else:
        escala = 1.0
        print("   ja em s")

    t_pupila = (df_pupil[c_p_t].values - t_sync_p) / escala
    diam_pupila = pd.Series(df_pupil[c_p_d].values).rolling(window=5, center=True).mean().values

    print(f"\nCarregando MoTeC - {nome}...")
    df_m = pd.read_csv(
        str(caminhos["motec"]),
        skiprows=14,
        sep=None,
        engine="python",
        encoding="latin1",
        on_bad_lines="skip",
    )
    df_m.columns = [str(c).strip() for c in df_m.columns]

    t_series, _ = clean_col(df_m, ["Time"])
    st_series, _ = clean_col(df_m, ["Steering Angle"])
    ac_series, _ = clean_col(df_m, ["Throttle Pos"])
    fr_series, _ = clean_col(df_m, ["Brake Pos"])
    lap_series, _ = clean_col(df_m, ["Session Lap Count"])

    if t_series is None:
        raise Exception(f"[{nome}] Coluna 'Time' nao encontrada.")

    df_m["t_sync"] = t_series - t_sync_m
    df_m["steering"] = st_series
    df_m["acel"] = ac_series
    df_m["freio"] = fr_series
    df_m["lap_raw"] = lap_series
    df_m = df_m.dropna(subset=["t_sync"])

    if lap_series is not None and lap_series.notna().any():
        df_m["lap_corrigido"] = df_m["lap_raw"].apply(
            lambda x: int(round(x)) + 1 if not pd.isna(x) else np.nan
        )
        voltas_brutas = sorted(df_m["lap_corrigido"].dropna().unique().astype(int))
        print(f"\n   Voltas apos offset (+1): {voltas_brutas}")
        ultima_volta = max(voltas_brutas)
        voltas_validas = [v for v in voltas_brutas if v != ultima_volta]
        print(f"   Ultima volta excluida: Volta {ultima_volta} (incompleta)")
        print(f"   Voltas validas: {voltas_validas}")
    else:
        print("   Session Lap Count nao encontrado. Informe manualmente.")
        n_voltas = int(input(f"   Quantas voltas COMPLETAS o piloto {nome} deu? "))
        voltas_validas = list(range(1, n_voltas + 1))
        df_m["lap_corrigido"] = np.nan

    voltas = []
    for lap_num in voltas_validas:
        if df_m["lap_corrigido"].notna().any():
            mask_v = df_m["lap_corrigido"] == lap_num
        else:
            print(f"\n   Volta {lap_num} de {nome}:")
            t_ini_m = tradutor_de_tempos(input(f"     Tempo INICIAL MoTeC da volta {lap_num}: "))
            t_fim_m = tradutor_de_tempos(input(f"     Tempo FINAL MoTeC da volta {lap_num}: "))
            t_ini_s = t_ini_m - t_sync_m
            t_fim_s = t_fim_m - t_sync_m
            mask_v = (df_m["t_sync"] >= t_ini_s) & (df_m["t_sync"] <= t_fim_s)

        df_v = df_m[mask_v].copy()
        if len(df_v) < 10:
            print(f"   Volta {lap_num} com poucos dados ({len(df_v)} pts) - pulando")
            continue

        t_ini_s = df_v["t_sync"].iloc[0]
        t_fim_s = df_v["t_sync"].iloc[-1]

        steer_norm = (
            interpolar_volta(df_v["steering"].values, N_PONTOS)
            if df_v["steering"].notna().any()
            else np.full(N_PONTOS, np.nan)
        )
        acel_norm = (
            interpolar_volta(df_v["acel"].values, N_PONTOS)
            if df_v["acel"].notna().any()
            else np.full(N_PONTOS, np.nan)
        )
        freio_norm = (
            interpolar_volta(df_v["freio"].values, N_PONTOS)
            if df_v["freio"].notna().any()
            else np.full(N_PONTOS, np.nan)
        )

        mask_p = (t_pupila >= t_ini_s) & (t_pupila <= t_fim_s)
        pupila_norm = (
            interpolar_volta(diam_pupila[mask_p], N_PONTOS)
            if mask_p.sum() > 5
            else np.full(N_PONTOS, np.nan)
        )

        voltas.append(
            {
                "piloto": nome,
                "volta_num": int(lap_num),
                "steering": steer_norm,
                "acel": acel_norm,
                "freio": freio_norm,
                "pupila": pupila_norm,
                "t_ini": t_ini_s,
                "t_fim": t_fim_s,
                "t_sync_m": t_sync_m,
            }
        )
        print(f"   Volta {lap_num}: {t_ini_s:.1f}s -> {t_fim_s:.1f}s ({len(df_v)} amostras)")

    print(f"\n   Total de voltas validas coletadas de {nome}: {len(voltas)}")
    return voltas


def executar():
    validar_arquivos_base()
    todas_voltas = []

    for nome, caminhos in PILOTOS.items():
        voltas_piloto = processar_piloto(nome, caminhos)
        todas_voltas.extend(voltas_piloto)

    total_voltas = len(todas_voltas)
    print(f"\n\n{'=' * 60}")
    print(f"   TOTAL DE VOLTAS VALIDAS: {total_voltas}")
    for nome in PILOTOS:
        n = sum(1 for v in todas_voltas if v["piloto"] == nome)
        print(f"      {nome}: {n} volta(s)")
    print(f"{'=' * 60}")

    if total_voltas == 0:
        raise Exception("Nenhuma volta valida coletada. Verifique os dados.")

    print("\nCalculando Volta Ideal...")
    eixo_norm = np.linspace(0, 100, N_PONTOS)

    stack_steer = np.array([v["steering"] for v in todas_voltas])
    stack_acel = np.array([v["acel"] for v in todas_voltas])
    stack_freio = np.array([v["freio"] for v in todas_voltas])
    stack_pupila = np.array([v["pupila"] for v in todas_voltas])

    media_steer = np.nanmean(stack_steer, axis=0)
    media_acel = np.nanmean(stack_acel, axis=0)
    media_freio = np.nanmean(stack_freio, axis=0)
    media_pupila = np.nanmean(stack_pupila, axis=0)
    sigma_steer = np.nanstd(stack_steer, axis=0)
    sigma_acel = np.nanstd(stack_acel, axis=0)
    sigma_freio = np.nanstd(stack_freio, axis=0)
    sigma_pupila = np.nanstd(stack_pupila, axis=0)

    df_ideal = pd.DataFrame(
        {
            "progresso_pct": eixo_norm,
            "steering_medio": media_steer,
            "steering_sigma": sigma_steer,
            "acel_medio": media_acel,
            "acel_sigma": sigma_acel,
            "freio_medio": media_freio,
            "freio_sigma": sigma_freio,
            "pupila_medio": media_pupila,
            "pupila_sigma": sigma_pupila,
        }
    )
    df_ideal.to_csv(ARQUIVO_IDEAL, index=False)
    print(f"\nVolta Ideal salva em: {ARQUIVO_IDEAL}")

    rows = []
    for v in todas_voltas:
        rows.append(
            {
                "piloto": v["piloto"],
                "volta_num": v["volta_num"],
                "t_ini": v["t_ini"],
                "t_fim": v["t_fim"],
                "t_sync_m": v["t_sync_m"],
            }
        )
    pd.DataFrame(rows).to_csv(ARQUIVO_VOLTAS, index=False)
    print(f"Metadados salvos em: {ARQUIVO_VOLTAS}")

    cores = {nome: c for nome, c in zip(PILOTOS.keys(), ["#1f77b4", "#ff7f0e", "#2ca02c"])}

    fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=True)
    fig.suptitle(
        f"Volta Ideal - Media de {total_voltas} volta(s) valida(s) de {len(PILOTOS)} piloto(s)\n"
        "(offset aplicado | ultima volta de cada piloto excluida)",
        fontsize=13,
        fontweight="bold",
    )

    for v in todas_voltas:
        cor = cores[v["piloto"]]
        axes[0].plot(eixo_norm, v["steering"], color=cor, alpha=0.12, linewidth=0.8)
        axes[1].plot(eixo_norm, v["acel"], color="orange", alpha=0.10, linewidth=0.8)
        axes[2].plot(eixo_norm, v["freio"], color="green", alpha=0.10, linewidth=0.8)
        axes[3].plot(eixo_norm, v["pupila"], color=cor, alpha=0.12, linewidth=0.8)

    axes[0].plot(eixo_norm, media_steer, color="black", linewidth=2.5, label="Ideal (media)", zorder=5)
    axes[0].fill_between(
        eixo_norm,
        media_steer - sigma_steer,
        media_steer + sigma_steer,
        alpha=0.15,
        color="black",
        label="+/-1sigma",
    )
    axes[1].plot(eixo_norm, media_acel, color="orange", linewidth=2.5, label="Acelerador ideal", zorder=5)
    axes[2].plot(eixo_norm, media_freio, color="green", linewidth=2.5, label="Freio ideal", zorder=5)
    axes[3].plot(eixo_norm, media_pupila, color="purple", linewidth=2.5, label="Pupila ideal", zorder=5)

    rotulos_eixo = ["Estercamento (graus)", "Acelerador (%)", "Freio (%)", "Diametro Pupila (mm)"]
    for ax, rotulo in zip(axes, rotulos_eixo):
        ax.set_ylabel(rotulo, fontsize=9)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, alpha=0.3)

    handles_pilotos = [Line2D([0], [0], color=cores[n], linewidth=2, label=n) for n in PILOTOS]
    handles_pilotos.append(Line2D([0], [0], color="black", linewidth=2.5, label="Media Ideal"))
    axes[0].legend(handles=handles_pilotos, loc="upper right", fontsize=7)

    axes[-1].set_xlabel("Progresso da Volta (%)", fontsize=10)
    plt.tight_layout()
    plt.savefig(ARQUIVO_GRAFICO_IDEAL, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Grafico salvo em: {ARQUIVO_GRAFICO_IDEAL}")


def main():
    try:
        executar()
    except Exception as e:
        import traceback

        print(f"\nDEU RUIM: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
