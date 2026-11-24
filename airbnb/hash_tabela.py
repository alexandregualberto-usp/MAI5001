"""Tabela hash própria com encadeamento.

- função hash: método da divisão, h(id) = id mod M, com M primo
  (adaptada do hash_divisao do nosso Exercício 06);
- M baldes, cada balde é uma lista Python de anúncios;
- colisão: o anúncio entra no fim da lista do balde (encadeamento);
- busca e remoção percorrem só o balde h(id), comparando ids; terminam ao
  achar o id ou no fim do balde, então sempre terminam.

Custo: com hashing uniforme simples e α = N/M, busca com sucesso examina em
média 1 + α/2 elementos e busca sem sucesso α elementos, O(1 + α). No pior caso
(todos no mesmo balde) é O(N). Inserção é O(1 + α) porque antes de inserir
percorre o balde para rejeitar id repetido. Remover do meio da lista do balde
custa O(tamanho do balde) por causa do deslocamento do del.

Rehash é opcional: com fator_max definido, quando α passaria desse valor a
tabela cresce para o primo >= 2M e reinsere tudo (O(N)). O número de rehashes
fica em self.rehashes. Nos experimentos de fator de carga fica desligado.
"""
from airbnb.anuncio import Anuncio
from airbnb.metricas import Metricas


def eh_primo(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def proximo_primo(n: int) -> int:
    n = max(2, n)
    while not eh_primo(n):
        n += 1
    return n


class TabelaHash:
    def __init__(self, capacidade: int = 11, fator_max: float | None = None):
        self._m = proximo_primo(capacidade)
        self._baldes: list[list[Anuncio]] = [[] for _ in range(self._m)]
        self._n = 0
        self.fator_max = fator_max
        self.colisoes = 0      # acumulado de inserções em balde não vazio
        self.rehashes = 0

    def _h(self, id: int) -> int:
        return id % self._m

    def inserir(self, registro: Anuncio, metricas: Metricas | None = None) -> None:
        """Insere o anúncio. Levanta ValueError se o id já estiver na tabela."""
        if self.fator_max is not None and (self._n + 1) / self._m > self.fator_max:
            self._rehash(2 * self._m)
        balde = self._baldes[self._h(registro.id)]
        for r in balde:
            if metricas is not None:
                metricas.comparacoes += 1
            if r.id == registro.id:
                raise ValueError(f"id {registro.id} já existe na tabela")
        if balde:
            self.colisoes += 1
            if metricas is not None:
                metricas.colisoes += 1
        balde.append(registro)
        self._n += 1

    def buscar(self, id: int, metricas: Metricas | None = None) -> Anuncio | None:
        balde = self._baldes[self._h(id)]
        for r in balde:
            if metricas is not None:
                metricas.passos += 1
            if r.id == id:
                return r
        return None

    def remover(self, id: int, metricas: Metricas | None = None) -> bool:
        balde = self._baldes[self._h(id)]
        for i in range(len(balde)):
            if metricas is not None:
                metricas.passos += 1
            if balde[i].id == id:
                del balde[i]
                self._n -= 1
                return True
        return False

    def _rehash(self, nova_capacidade: int) -> None:
        antigos = self._baldes
        self._m = proximo_primo(nova_capacidade)
        self._baldes = [[] for _ in range(self._m)]
        for balde in antigos:
            for r in balde:
                self._baldes[self._h(r.id)].append(r)
        self.rehashes += 1

    # informações para os experimentos
    @property
    def capacidade(self) -> int:
        return self._m

    @property
    def fator_carga(self) -> float:
        return self._n / self._m

    def __len__(self) -> int:
        return self._n

    def tamanhos_baldes(self) -> list[int]:
        return [len(b) for b in self._baldes]

    def __repr__(self):
        return f"TabelaHash(N={self._n}, M={self._m}, alfa={self.fator_carga:.3f})"
