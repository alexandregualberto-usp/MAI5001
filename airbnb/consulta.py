"""Estratégias de consulta por id.

Contrato comum (EstrategiaConsulta):
- preparar(registros, metricas): monta a estrutura de acesso a partir da
  sequência de registros (que deve ser tratada como somente leitura);
- buscar(id, metricas): devolve o anúncio com aquele id ou None.
  Só pode ser chamado depois de preparar; senão levanta RuntimeError;
- ao_inserir / ao_remover: avisos do repositório. O padrão é invalidar a
  estrutura (ela será reconstruída antes do próximo uso). A hash sobrescreve
  para se atualizar sem reconstruir.

Alterar atributos que não são o id não afeta nenhuma dessas estruturas: todas
guardam referências aos mesmos objetos do repositório, e a ordem é pelo id.
"""
from abc import ABC, abstractmethod
from typing import Sequence

from airbnb.anuncio import Anuncio, chave_id
from airbnb.hash_tabela import TabelaHash
from airbnb.metricas import Metricas
from airbnb.ordenacao import EstrategiaOrdenacao, MergeSort


class EstrategiaConsulta(ABC):
    nome = "abstrata"

    def __init__(self):
        self._preparada = False

    @property
    def preparada(self) -> bool:
        return self._preparada

    @abstractmethod
    def preparar(self, registros: Sequence[Anuncio], metricas: Metricas | None = None) -> None:
        ...

    @abstractmethod
    def buscar(self, id: int, metricas: Metricas | None = None) -> Anuncio | None:
        ...

    def invalidar(self) -> None:
        self._preparada = False

    def ao_inserir(self, registro: Anuncio) -> None:
        self.invalidar()

    def ao_remover(self, registro: Anuncio) -> None:
        self.invalidar()

    @property
    def rotulo(self) -> str:
        """Nome usado nos resultados dos experimentos."""
        return self.nome

    def _checar(self):
        if not self._preparada:
            raise RuntimeError(f"consulta {self.nome} usada sem preparar")

    def __repr__(self):
        return self.nome


class BuscaSequencial(EstrategiaConsulta):
    """Percorre a lista na ordem em que está. Não precisa de ordem nem de índice.

    preparar só guarda a referência para a lista do repositório (O(1), sem cópia),
    então inserções e remoções feitas na lista já aparecem na próxima busca e
    não é preciso invalidar.
    """
    nome = "sequencial"

    def preparar(self, registros, metricas=None):
        self._registros = registros
        self._preparada = True

    def buscar(self, id, metricas=None):
        self._checar()
        for r in self._registros:
            if metricas is not None:
                metricas.passos += 1
            if r.id == id:
                return r
        return None

    def ao_inserir(self, registro):
        pass

    def ao_remover(self, registro):
        pass


class _BuscaEmVetorOrdenado(EstrategiaConsulta):
    """Base das buscas que precisam de uma cópia ordenada por id.

    A ordenação usada na preparação é recebida por composição (padrão: MergeSort),
    então dá para trocar por InsertionSort quando a lista já está quase ordenada.
    A cópia guarda referências aos mesmos objetos do repositório (não copia os
    anúncios).

    Duas políticas de manutenção:
    - incremental=False (padrão): inserção ou remoção invalida a cópia, que é
      reordenada inteira antes da próxima busca (O(n log n) com MergeSort);
    - incremental=True: acha a posição pelo id com busca binária própria e faz
      list.insert / del nessa posição. A busca é O(log n), mas insert e del
      deslocam o resto da lista: O(n) por operação (memmove em C, rápido,
      mas não gratuito).
    """

    def __init__(self, ordenacao: EstrategiaOrdenacao | None = None, incremental: bool = False):
        super().__init__()
        self.ordenacao = ordenacao if ordenacao is not None else MergeSort()
        self.incremental = incremental
        self._v: list[Anuncio] = []

    @property
    def rotulo(self) -> str:
        if self.incremental:
            return f"{self.nome}/incremental"
        return f"{self.nome}/reconstroi-{self.ordenacao.nome}"

    def preparar(self, registros, metricas=None):
        self._v = self.ordenacao.ordenar(registros, chave_id, metricas)
        self._preparada = True

    def _posicao(self, id: int) -> int:
        """Primeira posição p com v[p].id >= id (limite inferior)."""
        ini, fim = 0, len(self._v)
        while ini < fim:
            meio = (ini + fim) // 2
            if self._v[meio].id < id:
                ini = meio + 1
            else:
                fim = meio
        return ini

    def ao_inserir(self, registro):
        if not self.incremental or not self._preparada:
            self.invalidar()
            return
        self._v.insert(self._posicao(registro.id), registro)

    def ao_remover(self, registro):
        if not self.incremental or not self._preparada:
            self.invalidar()
            return
        p = self._posicao(registro.id)
        if p < len(self._v) and self._v[p] is registro:
            del self._v[p]


class BuscaBinaria(_BuscaEmVetorOrdenado):
    """Binária iterativa. Invariante: se o id está em v, está em v[ini..fim]."""
    nome = "binaria"

    def buscar(self, id, metricas=None):
        self._checar()
        v = self._v
        ini, fim = 0, len(v) - 1
        while ini <= fim:
            meio = (ini + fim) // 2
            if metricas is not None:
                metricas.passos += 1
            atual = v[meio].id
            if atual == id:
                return v[meio]
            if atual < id:
                ini = meio + 1
            else:
                fim = meio - 1
        return None


class BuscaInterpolacao(_BuscaEmVetorOrdenado):
    """Estima a posição supondo ids espalhados de forma uniforme entre v[ini] e v[fim].

    Proteções: só sonda se v[ini].id <= id <= v[fim].id (então a posição estimada
    fica dentro de [ini, fim]); se v[ini].id == v[fim].id não divide. Como os ids
    são inteiros do Python, a conta (id - lo) * (fim - ini) não estoura.
    Cada sonda descarta pelo menos uma posição, então termina em no máximo n passos.
    """
    nome = "interpolacao"

    def buscar(self, id, metricas=None):
        self._checar()
        v = self._v
        ini, fim = 0, len(v) - 1
        while ini <= fim:
            lo = v[ini].id
            hi = v[fim].id
            if id < lo or id > hi:
                return None
            if metricas is not None:
                metricas.passos += 1
            if hi == lo:
                pos = ini
            else:
                pos = ini + (id - lo) * (fim - ini) // (hi - lo)
            atual = v[pos].id
            if atual == id:
                return v[pos]
            if atual < id:
                ini = pos + 1
            else:
                fim = pos - 1
        return None


class ConsultaHash(EstrategiaConsulta):
    """Adaptador da TabelaHash para o contrato de consulta.

    preparar cria uma tabela com capacidade N/alfa e insere todos (O(N)).
    Depois disso inserções e remoções do repositório são repassadas para a
    tabela (O(1 + α) cada), sem reconstruir. Se a base crescer, o rehash da
    tabela mantém α <= fator_max.
    """
    nome = "hash"

    def __init__(self, alfa: float = 0.5, fator_max: float | None = 0.75):
        super().__init__()
        self.alfa = alfa
        self.fator_max = fator_max
        self.tabela: TabelaHash | None = None

    def preparar(self, registros, metricas=None):
        capacidade = max(11, int(len(registros) / self.alfa))
        self.tabela = TabelaHash(capacidade, self.fator_max)
        for r in registros:
            self.tabela.inserir(r, metricas)
        self._preparada = True

    def buscar(self, id, metricas=None):
        self._checar()
        return self.tabela.buscar(id, metricas)

    def ao_inserir(self, registro):
        if self._preparada:
            self.tabela.inserir(registro)

    def ao_remover(self, registro):
        if self._preparada:
            self.tabela.remover(registro.id)
