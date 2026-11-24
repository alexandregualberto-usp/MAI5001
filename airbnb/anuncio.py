"""Entidade do domínio: um anúncio de hospedagem do Airbnb em Lisboa."""

TIPOS_QUARTO = ("Entire home/apt", "Private room", "Hotel room", "Shared room")
CAMPOS_ALTERAVEIS = ("nome", "bairro", "municipio", "tipo_quarto", "preco",
                     "capacidade", "avaliacoes", "nota", "licenca")


class Anuncio:
    """Anúncio com id inteiro, não negativo e imutável.

    O id é guardado em _id e só tem property de leitura. Os outros campos
    também são lidos por property e só mudam por alterar(), que valida tudo
    antes de aplicar (se um campo for inválido, nada muda).
    """

    __slots__ = ("_id", "_nome", "_bairro", "_municipio", "_tipo_quarto",
                 "_preco", "_capacidade", "_avaliacoes", "_nota", "_licenca")

    def __init__(self, id: int, nome: str, bairro: str, municipio: str, tipo_quarto: str,
                 preco: float, capacidade: int, avaliacoes: int = 0,
                 nota: float | None = None, licenca: str | None = None):
        if type(id) is not int or id < 0:
            raise ValueError(f"id deve ser inteiro não negativo, recebido {id!r}")
        self._id = id
        campos = {"nome": nome, "bairro": bairro, "municipio": municipio,
                  "tipo_quarto": tipo_quarto, "preco": preco, "capacidade": capacidade,
                  "avaliacoes": avaliacoes, "nota": nota, "licenca": licenca}
        self._validar(campos)
        self._aplicar(campos)

    # leitura
    @property
    def id(self) -> int:
        return self._id

    @property
    def nome(self) -> str:
        return self._nome

    @property
    def bairro(self) -> str:
        return self._bairro

    @property
    def municipio(self) -> str:
        return self._municipio

    @property
    def tipo_quarto(self) -> str:
        return self._tipo_quarto

    @property
    def preco(self) -> float:
        """Preço por noite em euros."""
        return self._preco

    @property
    def capacidade(self) -> int:
        return self._capacidade

    @property
    def avaliacoes(self) -> int:
        return self._avaliacoes

    @property
    def nota(self) -> float | None:
        return self._nota

    @property
    def licenca(self) -> str | None:
        return self._licenca

    # alteração
    def alterar(self, **alteracoes) -> None:
        """Altera atributos que não são o id. Levanta ValueError se algum campo
        não existir, for o id ou tiver valor inválido."""
        for campo in alteracoes:
            if campo == "id":
                raise ValueError("o id de um anúncio não pode ser alterado")
            if campo not in CAMPOS_ALTERAVEIS:
                raise ValueError(f"campo desconhecido: {campo}")
        self._validar(alteracoes)
        self._aplicar(alteracoes)

    @staticmethod
    def _validar(c: dict) -> None:
        for campo in ("nome", "bairro", "municipio"):
            if campo in c and (not isinstance(c[campo], str) or c[campo].strip() == ""):
                raise ValueError(f"{campo} deve ser texto não vazio")
        if "tipo_quarto" in c and c["tipo_quarto"] not in TIPOS_QUARTO:
            raise ValueError(f"tipo_quarto inválido: {c['tipo_quarto']!r}")
        if "preco" in c:
            p = c["preco"]
            if isinstance(p, bool) or not isinstance(p, (int, float)) or not p > 0:
                raise ValueError(f"preço deve ser positivo, recebido {p!r}")
        if "capacidade" in c:
            if type(c["capacidade"]) is not int or c["capacidade"] < 1:
                raise ValueError("capacidade deve ser inteiro >= 1")
        if "avaliacoes" in c:
            if type(c["avaliacoes"]) is not int or c["avaliacoes"] < 0:
                raise ValueError("avaliacoes deve ser inteiro >= 0")
        if "nota" in c and c["nota"] is not None:
            if not isinstance(c["nota"], (int, float)) or not 0 <= c["nota"] <= 5:
                raise ValueError("nota deve estar entre 0 e 5 ou ser None")
        if "licenca" in c and c["licenca"] is not None and not isinstance(c["licenca"], str):
            raise ValueError("licenca deve ser texto ou None")

    def _aplicar(self, c: dict) -> None:
        for campo, valor in c.items():
            if campo == "preco":
                valor = float(valor)
            setattr(self, "_" + campo, valor)

    # utilitários
    def como_linha(self) -> list:
        """Valores na ordem das colunas do CSV limpo."""
        return [self._id, self._nome, self._bairro, self._municipio, self._tipo_quarto,
                self._preco, self._capacidade, self._avaliacoes,
                "" if self._nota is None else self._nota,
                "" if self._licenca is None else self._licenca]

    def copia(self) -> "Anuncio":
        return Anuncio(self._id, self._nome, self._bairro, self._municipio, self._tipo_quarto,
                       self._preco, self._capacidade, self._avaliacoes, self._nota, self._licenca)

    def __eq__(self, outro) -> bool:
        if not isinstance(outro, Anuncio):
            return NotImplemented
        return self.como_linha() == outro.como_linha()

    __hash__ = None  # mutável, não pode ser chave de dict/set

    def __repr__(self) -> str:
        return (f"Anuncio(id={self._id}, nome={self._nome[:30]!r}, bairro={self._bairro!r}, "
                f"tipo={self._tipo_quarto!r}, preco={self._preco:.2f})")


COLUNAS_CSV = ["id", "nome", "bairro", "municipio", "tipo_quarto", "preco",
               "capacidade", "avaliacoes", "nota", "licenca"]


def chave_id(r: Anuncio) -> int:
    return r.id


def chave_preco(r: Anuncio) -> tuple:
    # o id entra como desempate, assim a ordem é única mesmo com preços iguais
    return (r.preco, r.id)
