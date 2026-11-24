"""Roda todos os experimentos e grava resultados/*.csv e graficos/*.png.

Uso:
    python rodar_experimentos.py            # protocolo completo (~5 min)
    python rodar_experimentos.py --rapido   # 1 repetição e tamanhos pequenos, só para conferir

Configuração (sementes, tamanhos, proporções) fica em CONFIG abaixo e também
vai para resultados/ambiente.txt junto com versões e máquina.
"""
import os
import platform
import sys
import time
from pathlib import Path

import matplotlib
import numpy
import pandas

from airbnb import (InsertionSort, MergeSort, HeapSort, BuscaSequencial, BuscaBinaria,
                    BuscaInterpolacao, ConsultaHash)
from airbnb import dados, graficos
from airbnb.arquivos import ler_anuncios_csv
from airbnb.cargas import (GeradorCargas, anuncios_novos, sequencia_trimestral,
                           sequencia_intercalada, resumo_sequencia)
from airbnb.experimentos import ExecutorExperimentos, ConfiguracaoExperimento, salvar_resultados

RAIZ = Path(__file__).resolve().parent
SEMENTE = 2024

CONFIG = {
    "ordenacao": dict(tamanhos=(500, 2000, 8000), perfis=("aleatorio", "ordenado", "inverso", "repeticoes")),
    "busca": dict(tamanhos=(2000, 6000, 18000), perfis=("regular", "real", "concentrada"), q=2000),
    "hash": dict(alfas=(0.25, 0.5, 0.75, 1.0, 2.0), q=20000),
    "lote": dict(qs=(1, 10, 100, 1000, 10000)),
    "misto": dict(q_trimestral=1000, n_ops_intercalado=4000, proporcoes=(0.80, 0.10, 0.05, 0.05)),
}
RAPIDO = {
    "ordenacao": dict(tamanhos=(200, 400, 800), perfis=CONFIG["ordenacao"]["perfis"]),
    "busca": dict(tamanhos=(500, 1000, 2000), perfis=CONFIG["busca"]["perfis"], q=1000),
    "hash": CONFIG["hash"],
    "lote": dict(qs=(1, 10, 100)),
    "misto": dict(q_trimestral=200, n_ops_intercalado=500, proporcoes=(0.80, 0.10, 0.05, 0.05)),
}

ORDENACOES = [InsertionSort(), MergeSort(), HeapSort()]
CONSULTAS = [BuscaSequencial, BuscaBinaria, BuscaInterpolacao, ConsultaHash]
CONSULTAS_MISTO = [BuscaSequencial,
                   BuscaBinaria,                                   # reconstrói com MergeSort
                   lambda: BuscaBinaria(InsertionSort()),          # reconstrói com InsertionSort
                   lambda: BuscaBinaria(incremental=True),
                   lambda: BuscaInterpolacao(incremental=True),
                   ConsultaHash]


def ambiente() -> str:
    linhas = [f"python: {sys.version.split()[0]}", f"implementacao: {platform.python_implementation()}",
              f"sistema: {platform.platform()}", f"processador: {platform.processor() or platform.machine()}",
              f"cpus: {os.cpu_count()}", f"pandas: {pandas.__version__}", f"numpy: {numpy.__version__}",
              f"matplotlib: {matplotlib.__version__}", f"semente: {SEMENTE}"]
    return "\n".join(linhas)


def carregar_coletas() -> dict:
    pasta = dados.PASTA_LIMPO
    if not (pasta / "anuncios_mar21.csv").exists():
        dados.preparar_todas()
    return {c: ler_anuncios_csv(pasta / f"anuncios_{c}.csv") for c in dados.COLETAS}


def executar_tudo(rapido: bool = False, repeticoes: int = 5, saida: Path = RAIZ / "resultados") -> dict:
    cfg = RAPIDO if rapido else CONFIG
    reps = 1 if rapido else repeticoes
    coletas = carregar_coletas()
    base = coletas["mar21"]
    gerador = GeradorCargas(base)
    saida.mkdir(parents=True, exist_ok=True)
    texto_cfg = ambiente() + f"\nrepeticoes: {reps}\nconfig: {cfg}\n"

    ex = ExecutorExperimentos(gerador, ORDENACOES, CONSULTAS)
    ex_misto = ExecutorExperimentos(gerador, consultas=CONSULTAS_MISTO, referencias=False)

    m = cfg["misto"]
    lista = [coletas[c] for c in dados.COLETAS]
    tri = sequencia_trimestral(lista, m["q_trimestral"], SEMENTE)
    inter = sequencia_intercalada(base, anuncios_novos(base, lista[1:]), m["n_ops_intercalado"],
                                  SEMENTE, m["proporcoes"])
    texto_cfg += f"sequencia trimestral: {resumo_sequencia(tri)}\nsequencia intercalada: {resumo_sequencia(inter)}\n"

    experimentos = {
        "ordenacao": (ex, ConfiguracaoExperimento("ordenacao", repeticoes=reps, semente=SEMENTE, **cfg["ordenacao"])),
        "busca": (ex, ConfiguracaoExperimento("busca", repeticoes=reps, semente=SEMENTE, **cfg["busca"])),
        "hash": (ex, ConfiguracaoExperimento("hash", repeticoes=reps, semente=SEMENTE, **cfg["hash"])),
        "lote": (ex, ConfiguracaoExperimento("lote", repeticoes=reps, semente=SEMENTE, **cfg["lote"])),
        "misto": (ex_misto, ConfiguracaoExperimento("misto", repeticoes=reps, semente=SEMENTE,
                                                    cenarios={"trimestral": (base, tri), "intercalado": (base, inter)})),
    }
    resultados = {}
    for nome, (executor, c) in experimentos.items():
        t = time.time()
        res = executor.executar(c)
        salvar_resultados(res, saida / f"{nome}.csv")
        resultados[nome] = res
        print(f"{nome}: {len(res)} medidas em {time.time() - t:.0f} s")
    avisos = ex.avisos + ex_misto.avisos
    texto_cfg += f"divergencias: {avisos if avisos else 'nenhuma'}\n"
    (saida / "ambiente.txt").write_text(texto_cfg, encoding="utf-8")
    print("divergências:", avisos if avisos else "nenhuma")
    return resultados


if __name__ == "__main__":
    rapido = "--rapido" in sys.argv
    executar_tudo(rapido)
    if not rapido:
        graficos.gerar_todos()
        print("gráficos em", graficos.PASTA_GRAF)
