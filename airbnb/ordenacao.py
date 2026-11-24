"""Estratégias de ordenação: Insertion Sort, Merge Sort (recursivo) e Heapsort.

Contrato comum (EstrategiaOrdenacao.ordenar):
- recebe uma sequência de anúncios, uma função chave e, opcionalmente, Metricas;
- devolve uma lista NOVA em ordem crescente de chave; a entrada não é alterada;
- a chave deve ser única (por isso chave_preco usa o id como desempate), assim
  as três estratégias devolvem exatamente a mesma lista.

Como todas fazem a mesma coisa antes e depois, isso fica em ordenar() (método
template) e cada algoritmo só implementa _ordenar_itens(). Antes de ordenar a
chave de cada registro é calculada uma vez e guardada em pares (chave, registro):
isso custa O(n) de memória extra, mas evita chamar a função chave a cada
comparação. As três estratégias pagam esse mesmo custo.

Merge Sort adaptado do nosso Exercício 05 (merge com fatias esq/dir); passou a
comparar só a chave do par e a contar comparações e movimentações.
"""
from abc import ABC, abstractmethod
from typing import Any, Callable, Sequence

from airbnb.anuncio import Anuncio
from airbnb.metricas import Metricas


class EstrategiaOrdenacao(ABC):
    nome = "abstrata"

    def ordenar(self, registros: Sequence[Anuncio], chave: Callable[[Anuncio], Any],
                metricas: Metricas | None = None) -> list[Anuncio]:
        itens = [(chave(r), r) for r in registros]   # cópia O(n): a entrada fica intacta
        self._ordenar_itens(itens, metricas)
        return [r for _, r in itens]

    @abstractmethod
    def _ordenar_itens(self, v: list, m: Metricas | None) -> None:
        """Ordena v (lista de pares (chave, registro)) no lugar, pela chave."""

    def __repr__(self):
        return self.nome


class InsertionSort(EstrategiaOrdenacao):
    """Elementar, estável, in-place. O(n^2) no pior caso, O(n) se já ordenado."""
    nome = "insertion"

    def _ordenar_itens(self, v, m):
        for j in range(1, len(v)):
            # invariante: v[0..j-1] está ordenado e tem os mesmos itens de antes
            atual = v[j]
            k = atual[0]
            i = j - 1
            while i >= 0:
                if m is not None:
                    m.comparacoes += 1
                if v[i][0] > k:
                    v[i + 1] = v[i]
                    if m is not None:
                        m.movimentacoes += 1
                    i -= 1
                else:
                    break
            v[i + 1] = atual
            if m is not None:
                m.movimentacoes += 1


class MergeSort(EstrategiaOrdenacao):
    """Recursivo, estável. T(n) = 2T(n/2) + Θ(n) = Θ(n log n) em qualquer entrada.
    Usa O(n) de memória auxiliar nas fatias e O(log n) de pilha."""
    nome = "merge"

    def _ordenar_itens(self, v, m):
        self._merge_sort(v, 0, len(v) - 1, m)

    def _merge_sort(self, v, inicio, fim, m):
        if inicio < fim:
            meio = (inicio + fim) // 2
            self._merge_sort(v, inicio, meio, m)
            self._merge_sort(v, meio + 1, fim, m)
            self._merge(v, inicio, meio, fim, m)

    def _merge(self, v, inicio, meio, fim, m):
        esq = v[inicio:meio + 1]      # fatias copiam referências: O(fim - inicio)
        dir = v[meio + 1:fim + 1]
        i = j = 0
        k = inicio
        while i < len(esq) and j < len(dir):
            if m is not None:
                m.comparacoes += 1
            if esq[i][0] <= dir[j][0]:   # <= mantém a estabilidade
                v[k] = esq[i]
                i += 1
            else:
                v[k] = dir[j]
                j += 1
            k += 1
        while i < len(esq):
            v[k] = esq[i]
            i += 1
            k += 1
        while j < len(dir):
            v[k] = dir[j]
            j += 1
            k += 1
        if m is not None:
            m.movimentacoes += fim - inicio + 1


class HeapSort(EstrategiaOrdenacao):
    """Heap de máximo em vetor, construção bottom-up e sift-down iterativo.

    Índices (base 0): pai(i) = (i-1)//2, esq(i) = 2i+1, dir(i) = 2i+2.
    Região ativa v[0..tam-1] é heap; sufixo v[tam..n-1] já está ordenado e
    contém os maiores elementos. Não é estável (aqui não importa, a chave é única).

    Com registrar_passos=True guarda em self.passos o estado do vetor depois da
    construção e de cada extração, para ilustrar em entradas pequenas.
    """
    nome = "heap"

    def __init__(self, registrar_passos: bool = False):
        self.registrar_passos = registrar_passos
        self.passos = []

    def _ordenar_itens(self, v, m):
        n = len(v)
        self.passos = []
        # construção bottom-up: do último pai até a raiz
        for i in range(n // 2 - 1, -1, -1):
            self._sift_down(v, i, n, m)
        if self.registrar_passos:
            self.passos.append(("heap construída", [k for k, _ in v], n))
        # extrações: a raiz (máximo) vai para o início do sufixo ordenado
        for tam in range(n - 1, 0, -1):
            v[0], v[tam] = v[tam], v[0]
            if m is not None:
                m.movimentacoes += 2
            self._sift_down(v, 0, tam, m)
            if self.registrar_passos:
                self.passos.append((f"extração {n - tam}", [k for k, _ in v], tam))

    @staticmethod
    def _sift_down(v, i, tam, m):
        while True:
            maior = i
            e = 2 * i + 1
            d = 2 * i + 2
            if e < tam:
                if m is not None:
                    m.comparacoes += 1
                if v[e][0] > v[maior][0]:
                    maior = e
            if d < tam:
                if m is not None:
                    m.comparacoes += 1
                if v[d][0] > v[maior][0]:
                    maior = d
            if maior == i:
                return
            v[i], v[maior] = v[maior], v[i]
            if m is not None:
                m.movimentacoes += 2
            i = maior
