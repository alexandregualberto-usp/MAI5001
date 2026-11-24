"""Demonstração pelo terminal: consulta, cadastro, alteração, remoção e relatório.

Uso:  python demo.py
"""
from pathlib import Path

from airbnb import (Anuncio, Repositorio, BuscaSequencial, BuscaBinaria, BuscaInterpolacao,
                    ConsultaHash, InsertionSort, MergeSort, HeapSort, chave_preco)
from airbnb import dados
from airbnb.arquivos import ler_anuncios_csv, escrever_anuncios_csv

RAIZ = Path(__file__).resolve().parent


def mostrar_busca(repo, id):
    for nome in repo.nomes_consultas:
        print(f"  {nome:13s} -> {repo.buscar(id, nome)}")


def main():
    if not (dados.PASTA_LIMPO / "anuncios_mar21.csv").exists():
        dados.preparar_todas()
    repo = Repositorio([BuscaSequencial(), BuscaBinaria(), BuscaInterpolacao(), ConsultaHash()])
    repo.carregar(ler_anuncios_csv(dados.PASTA_LIMPO / "anuncios_mar21.csv"))
    print(f"{len(repo)} anúncios carregados (coleta mar/21)\n")

    print("consulta do id 6499 (existe) pelas quatro estratégias:")
    mostrar_busca(repo, 6499)
    print("consulta do id 6500 (não existe):")
    mostrar_busca(repo, 6500)

    novo = Anuncio(60_000_001, "Estúdio novo no Intendente", "Arroios", "Lisboa",
                   "Entire home/apt", 72.0, 2, 0)
    repo.inserir(novo)
    print("\ninserido:", novo)
    try:
        repo.inserir(Anuncio(6499, "Cópia", "Belm", "Lisboa", "Private room", 30.0, 1))
    except ValueError as e:
        print("id duplicado rejeitado:", e)
    print("consulta do novo id (as ordenadas são reconstruídas antes):")
    mostrar_busca(repo, 60_000_001)

    repo.atualizar(60_000_001, {"preco": 85.0, "nota": 4.9})
    print("\ndepois de alterar preço e nota:", repo.buscar(60_000_001, "hash"),
          "nota", repo.buscar(60_000_001, "hash").nota)
    try:
        repo.atualizar(60_000_001, {"id": 1})
    except ValueError as e:
        print("alterar id rejeitado:", e)

    print("\nremovendo 6499:", repo.remover(6499))
    mostrar_busca(repo, 6499)
    print("reconstruções até aqui:", repo.reconstrucoes)

    print("\nrelatório: 10 anúncios mais baratos (preço, desempate id)")
    relatorios = [repo.relatorio(o) for o in (InsertionSort(), MergeSort(), HeapSort())]
    print("insertion == merge == heap ?", relatorios[0] == relatorios[1] == relatorios[2])
    for a in relatorios[1][:10]:
        print(f"  {a.preco:7.2f} €  id={a.id:<9d} {a.municipio:10s} {a.nome[:45]}")

    destino = RAIZ / "resultados" / "relatorio_por_preco.csv"
    escrever_anuncios_csv(relatorios[1], destino)
    print("\nrelatório exportado em", destino)


if __name__ == "__main__":
    main()
