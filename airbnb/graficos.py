"""Tabelas e gráficos feitos só a partir dos CSV de resultados (resultados/*.csv).

Separado dos algoritmos: dá para refazer todos os gráficos sem rodar nada de novo.
Tempos: mediana das 5 repetições e intervalo interquartil (IQR = Q3 - Q1).
"""
from pathlib import Path

import matplotlib
import matplotlib.ticker
import matplotlib.pyplot as plt
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PASTA_RES = RAIZ / "resultados"
PASTA_GRAF = RAIZ / "graficos"

CORES = {"insertion": "#d62728", "merge": "#1f77b4", "heap": "#2ca02c", "ref_sorted": "#7f7f7f",
         "sequencial": "#d62728", "binaria/reconstroi-merge": "#1f77b4", "interpolacao/reconstroi-merge": "#ff7f0e",
         "hash": "#2ca02c", "ref_dict": "#7f7f7f", "ref_bisect": "#bcbd22",
         "binaria/reconstroi-insertion": "#9467bd", "binaria/incremental": "#17becf",
         "interpolacao/incremental": "#e377c2"}


def ler(nome: str) -> pd.DataFrame:
    return pd.read_csv(PASTA_RES / f"{nome}.csv")


def resumo(df: pd.DataFrame, medida: str, por: list[str]) -> pd.DataFrame:
    """Mediana, Q1, Q3 e IQR da medida agrupada por 'por'."""
    d = df[df["medida"] == medida]
    g = d.groupby(por)["valor"]
    r = pd.DataFrame({"mediana": g.median(), "q1": g.quantile(0.25), "q3": g.quantile(0.75),
                      "reps": g.size()})
    r["iqr"] = r["q3"] - r["q1"]
    return r.reset_index()


def _eixo_n(ax, valores):
    # marca só os tamanhos usados, sem os rótulos automáticos do eixo log
    ax.set_xticks(sorted(set(valores)), labels=[str(int(v)) for v in sorted(set(valores))])
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())


def _salvar(fig, nome):
    PASTA_GRAF.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(PASTA_GRAF / nome, dpi=120)
    return fig


def grafico_ordenacao(df=None):
    df = ler("ordenacao") if df is None else df
    r = resumo(df, "tempo", ["estrategia", "perfil", "n"])
    perfis = ["aleatorio", "ordenado", "inverso", "repeticoes"]
    fig, eixos = plt.subplots(1, 4, figsize=(16, 4), sharey=True)
    for ax, perfil in zip(eixos, perfis):
        for est, g in r[r.perfil == perfil].groupby("estrategia"):
            g = g.sort_values("n")
            ax.errorbar(g.n, g.mediana / 1e6, yerr=[(g.mediana - g.q1) / 1e6, (g.q3 - g.mediana) / 1e6],
                        marker="o", capsize=3, label=est, color=CORES.get(est))
        ax.set_xscale("log")
        ax.set_yscale("log")
        _eixo_n(ax, r.n)
        ax.set_title(f"perfil: {perfil}")
        ax.set_xlabel("n (registros)")
        ax.grid(alpha=0.3)
    eixos[0].set_ylabel("tempo mediano (ms, log)")
    eixos[0].legend()
    fig.suptitle("Crescimento das ordenações (chave preço, desempate id)")
    return _salvar(fig, "1_ordenacao_crescimento.png")


def grafico_buscas(df=None):
    df = ler("busca") if df is None else df
    r = resumo(df, "tempo_por_consulta", ["estrategia", "perfil", "n"])
    p = df[df.medida.isin(["passos_medio_acerto", "passos_medio_erro"])]
    dists = ["regular", "real", "concentrada"]
    fig, eixos = plt.subplots(2, 3, figsize=(15, 8))
    for j, dist in enumerate(dists):
        ax = eixos[0][j]
        for est, g in r[r.perfil == dist].groupby("estrategia"):
            g = g.sort_values("n")
            ax.errorbar(g.n, g.mediana / 1e3, yerr=[(g.mediana - g.q1) / 1e3, (g.q3 - g.mediana) / 1e3],
                        marker="o", capsize=3, label=est, color=CORES.get(est))
        ax.set_xscale("log")
        ax.set_yscale("log")
        _eixo_n(ax, r.n)
        ax.set_title(f"ids {dist}: tempo por consulta")
        ax.set_xlabel("n")
        ax.set_ylabel("µs por consulta (log)")
        ax.grid(alpha=0.3)
        ax = eixos[1][j]
        nmax = p.n.max()
        q = p[(p.perfil == dist) & (p.n == nmax)].pivot_table(index="estrategia", columns="medida", values="valor")
        q.plot.bar(ax=ax, logy=True, rot=20)
        ax.set_title(f"ids {dist}: passos por consulta (n={nmax})")
        ax.set_ylabel("passos médios (log)")
        ax.set_xlabel("")
    eixos[0][0].legend(fontsize=8)
    fig.suptitle("Custo das buscas (lote de consultas, 50% presentes e 50% ausentes)")
    return _salvar(fig, "2_buscas_custo.png")


def grafico_hash(df=None):
    df = ler("hash") if df is None else df
    d = df[df.repeticao == 0].pivot_table(index="parametro", columns="medida", values="valor")
    d["alfa"] = d["alfa_real"]
    d = d.sort_values("alfa")
    t = resumo(df, "tempo_por_consulta", ["parametro"]).set_index("parametro").loc[d.index]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4))
    a1.plot(d.alfa, d.passos_medio_acerto, "o-", label="acerto medido")
    a1.plot(d.alfa, d.teoria_acerto, "--", label="acerto teoria 1+α/2")
    a1.plot(d.alfa, d.passos_medio_erro, "s-", label="erro medido")
    a1.plot(d.alfa, d.teoria_erro, ":", label="erro teoria α")
    a1.set_xlabel("fator de carga α = N/M")
    a1.set_ylabel("comparações por consulta")
    a1.set_title("Passos por consulta")
    a1.legend()
    a1.grid(alpha=0.3)
    a2.bar([f"{x:.2f}" for x in d.alfa], d.colisoes, color="#ff7f0e")
    a2.set_xlabel("α")
    a2.set_ylabel("colisões na construção")
    a2.set_title("Colisões e maior balde")
    for i, (c, mb) in enumerate(zip(d.colisoes, d.maior_balde)):
        a2.text(i, c, f"maior={int(mb)}", ha="center", va="bottom", fontsize=8)
    a3.errorbar(d.alfa, t.mediana, yerr=[t.mediana - t.q1, t.q3 - t.mediana], marker="o", capsize=3)
    a3.set_xlabel("α")
    a3.set_ylabel("ns por consulta (mediana)")
    a3.set_title("Tempo por consulta")
    a3.grid(alpha=0.3)
    fig.suptitle(f"Efeito do fator de carga na tabela hash (N={int(df.n.iloc[0])}, ids reais)")
    return _salvar(fig, "3_hash_fator_carga.png")


def grafico_custo_total(lote=None, misto=None):
    lote = ler("lote") if lote is None else lote
    misto = ler("misto") if misto is None else misto
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 4.5))
    r = resumo(lote, "tempo_total", ["estrategia", "parametro"])
    r["Q"] = r.parametro.str.replace("Q=", "").astype(int)
    for est, g in r.groupby("estrategia"):
        g = g.sort_values("Q")
        a1.errorbar(g.Q, g.mediana / 1e6, yerr=[(g.mediana - g.q1) / 1e6, (g.q3 - g.mediana) / 1e6],
                    marker="o", capsize=3, label=est, color=CORES.get(est))
    a1.set_xscale("log")
    a1.set_yscale("log")
    _eixo_n(a1, r.Q)
    a1.set_xlabel("Q consultas no lote")
    a1.set_ylabel("tempo total mediano (ms, log)")
    a1.set_title("Lote estático: preparação + Q consultas")
    a1.legend(fontsize=7)
    a1.grid(alpha=0.3)
    for ax, cenario in ((a2, "trimestral"), (a3, "intercalado")):
        m = misto[misto.perfil == cenario]
        partes = ["tempo_consulta", "tempo_inserir", "tempo_alterar", "tempo_remover"]
        tab = (m[m.medida.isin(partes)].groupby(["estrategia", "medida"])["valor"].median()
               .unstack()[partes] / 1e6)
        tab = tab.loc[tab.sum(axis=1).sort_values().index]
        tab.columns = [c.replace("tempo_", "") for c in partes]
        tab.plot.barh(stacked=True, ax=ax)
        rec = m[m.medida == "reconstrucoes"].groupby("estrategia")["valor"].median()
        for i, est in enumerate(tab.index):
            ax.text(tab.loc[est].sum(), i, f" {tab.loc[est].sum():.0f} ms, {int(rec[est])} reconstr.",
                    va="center", fontsize=8)
        ax.set_xlim(0, tab.sum(axis=1).max() * 1.35)
        ax.set_xlabel("tempo mediano (ms)")
        ax.set_ylabel("")
        ax.set_title(f"Com atualizações: cenário {cenario}")
    fig.suptitle("Custo total com preparação e atualizações")
    return _salvar(fig, "4_custo_total.png")


def gerar_todos():
    matplotlib.use("Agg")
    for f in (grafico_ordenacao, grafico_buscas, grafico_hash, grafico_custo_total):
        plt.close(f())
