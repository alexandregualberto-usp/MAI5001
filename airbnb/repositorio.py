"""Repositório: dono da coleção principal de anúncios e da consistência dos índices.

Estruturas e como se referem aos registros:
- self._registros: lista principal, em ordem de cadastro. É a única coleção
  "dona" dos objetos. Não é exposta para alteração (registros() devolve tupla).
- self._indice: TabelaHash própria usada pelo repositório para rejeitar id
  duplicado e achar o registro em atualizar/remover sem varrer a lista.
- estratégias de consulta registradas: cada uma guarda referências aos mesmos
  objetos (cópia ordenada por id ou tabela hash), nunca cópias dos anúncios.

Fluxo de atualização:
- inserir: valida id único -> append na lista -> índice -> avisa as estratégias
  (ordenadas ficam inválidas, hash insere, sequencial não precisa de nada);
- atualizar: altera o próprio objeto (id não pode mudar); como nenhuma
  estrutura é ordenada por outro campo que não o id, nada precisa ser refeito;
- remover: tira da lista e do índice -> avisa as estratégias (ordenadas ficam
  inválidas, hash remove). Assim um objeto removido não volta em consulta.
- buscar: se a estratégia escolhida está inválida, é reconstruída antes
  (reconstrução preguiçosa) e isso é contado em self.reconstrucoes.

Relatórios ordenados (por preço etc.) são gerados na hora e devolvidos como
lista nova: são um retrato do momento e o repositório não os mantém.
"""
from typing import Iterator, Sequence

from airbnb.anuncio import Anuncio, chave_preco
from airbnb.consulta import EstrategiaConsulta
from airbnb.hash_tabela import TabelaHash
from airbnb.metricas import Metricas
from airbnb.ordenacao import EstrategiaOrdenacao


class Repositorio:
    def __init__(self, consultas: Sequence[EstrategiaConsulta] = ()):
        self._registros: list[Anuncio] = []
        self._indice = TabelaHash(1009, fator_max=0.75)
        self._consultas: list[EstrategiaConsulta] = []
        self.reconstrucoes = {}
        for c in consultas:
            self.registrar_consulta(c)

    # estratégias
    def registrar_consulta(self, consulta: EstrategiaConsulta) -> None:
        if self._achar_consulta(consulta.nome) is not None:
            raise ValueError(f"já existe consulta chamada {consulta.nome}")
        self._consultas.append(consulta)
        self.reconstrucoes[consulta.nome] = 0

    def _achar_consulta(self, nome: str) -> EstrategiaConsulta | None:
        for c in self._consultas:
            if c.nome == nome:
                return c
        return None

    @property
    def nomes_consultas(self) -> list[str]:
        return [c.nome for c in self._consultas]

    # cadastro
    def inserir(self, registro: Anuncio) -> None:
        """Cadastra o anúncio. ValueError se o id já existe."""
        if self._indice.buscar(registro.id) is not None:
            raise ValueError(f"id {registro.id} já cadastrado")
        self._registros.append(registro)
        self._indice.inserir(registro)
        for c in self._consultas:
            c.ao_inserir(registro)

    def carregar(self, registros: Sequence[Anuncio]) -> None:
        for r in registros:
            self.inserir(r)

    def atualizar(self, id: int, alteracoes: dict) -> None:
        """Altera atributos não identificadores. KeyError se o id não existe,
        ValueError se tentar mudar o id ou um valor for inválido."""
        if "id" in alteracoes:
            raise ValueError("o id é imutável")
        r = self._indice.buscar(id)
        if r is None:
            raise KeyError(id)
        r.alterar(**alteracoes)

    def remover(self, id: int) -> bool:
        """Remove o anúncio. Devolve False se o id não existia."""
        r = self._indice.buscar(id)
        if r is None:
            return False
        # acha a posição na lista: O(n), mas mantém a ordem de cadastro
        for i in range(len(self._registros)):
            if self._registros[i] is r:
                del self._registros[i]
                break
        self._indice.remover(id)
        for c in self._consultas:
            c.ao_remover(r)
        return True

    # consulta
    def preparar(self, estrategia: str, metricas: Metricas | None = None) -> None:
        c = self._achar_consulta(estrategia)
        if c is None:
            raise KeyError(f"estratégia {estrategia} não registrada")
        c.preparar(self._registros, metricas)
        self.reconstrucoes[estrategia] += 1

    def buscar(self, id: int, estrategia: str, metricas: Metricas | None = None) -> Anuncio | None:
        c = self._achar_consulta(estrategia)
        if c is None:
            raise KeyError(f"estratégia {estrategia} não registrada")
        if not c.preparada:
            c.preparar(self._registros, metricas)
            self.reconstrucoes[estrategia] += 1
        return c.buscar(id, metricas)

    # relatórios
    def relatorio(self, ordenacao: EstrategiaOrdenacao, chave=chave_preco,
                  metricas: Metricas | None = None) -> list[Anuncio]:
        return ordenacao.ordenar(self._registros, chave, metricas)

    # leitura
    def registros(self) -> tuple[Anuncio, ...]:
        return tuple(self._registros)

    def __len__(self) -> int:
        return len(self._registros)

    def __iter__(self) -> Iterator[Anuncio]:
        return iter(self._registros)

    def __contains__(self, id: int) -> bool:
        return self._indice.buscar(id) is not None
