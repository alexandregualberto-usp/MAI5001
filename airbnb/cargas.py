"""Gerador das entradas dos experimentos, sempre a partir da base real limpa.

As variações sintéticas mexem em uma coisa só por vez:
- perfis de ordenação (aleatório, ordenado, inverso, repetições no preço);
- distribuição dos ids (real, regular, concentrada);
- lotes de consulta com 50% de ids presentes e 50% ausentes.

Usa random.Random(semente) local, então a mesma semente gera a mesma entrada.
sorted e set aparecem aqui só para GERAR dados (permitido pelo enunciado), nunca
dentro dos algoritmos avaliados.
"""
import random
from typing import Sequence

from airbnb.anuncio import Anuncio, chave_preco

PRECOS_REPETIDOS = (40.0, 60.0, 80.0, 100.0, 150.0)
BASE_ID_GRANDE = 10 ** 18   # o Airbnb passou a usar ids de 18 dígitos em 2022


def com_id(a: Anuncio, novo_id: int) -> Anuncio:
    return Anuncio(novo_id, a.nome, a.bairro, a.municipio, a.tipo_quarto, a.preco,
                   a.capacidade, a.avaliacoes, a.nota, a.licenca)


class GeradorCargas:
    def __init__(self, base: Sequence[Anuncio]):
        self.base = list(base)

    def amostra(self, n: int, semente: int) -> list[Anuncio]:
        if n > len(self.base):
            raise ValueError(f"amostra de {n} maior que a base ({len(self.base)})")
        return random.Random(semente).sample(self.base, n)

    def perfil(self, registros: list[Anuncio], perfil: str, semente: int) -> list[Anuncio]:
        """Mesma amostra, organizada conforme o perfil pedido (chave = preço, id)."""
        rnd = random.Random(semente)
        if perfil == "aleatorio":
            v = list(registros)
            rnd.shuffle(v)
            return v
        if perfil == "ordenado":
            return sorted(registros, key=chave_preco)
        if perfil == "inverso":
            return sorted(registros, key=chave_preco, reverse=True)
        if perfil == "repeticoes":
            # só 5 preços distintos: muitos empates, desfeitos pelo id
            v = [a.copia() for a in registros]
            for a in v:
                a.alterar(preco=rnd.choice(PRECOS_REPETIDOS))
            rnd.shuffle(v)
            return v
        raise ValueError(f"perfil desconhecido: {perfil}")

    def com_distribuicao(self, registros: list[Anuncio], dist: str, semente: int) -> list[Anuncio]:
        """real: ids originais do Airbnb (6499 a ~48 milhões, quase uniformes);
        regular: ids 1000, 2000, 3000... (progressão aritmética);
        concentrada: 90% com o id real e 10% com ids de 18 dígitos, como os
        anúncios criados depois da mudança de formato do Airbnb."""
        if dist == "real":
            return list(registros)
        if dist == "regular":
            ordem = sorted(registros, key=lambda a: a.id)
            return [com_id(a, 1000 * (i + 1)) for i, a in enumerate(ordem)]
        if dist == "concentrada":
            rnd = random.Random(semente)
            v = list(registros)
            k = len(v) // 10
            grandes = rnd.sample(range(len(v)), k)
            ids_grandes = rnd.sample(range(10 ** 15), k)
            for pos, extra in zip(grandes, ids_grandes):
                v[pos] = com_id(v[pos], BASE_ID_GRANDE + extra)
            return v
        raise ValueError(f"distribuição desconhecida: {dist}")

    @staticmethod
    def lote_consultas(registros: list[Anuncio], q: int, semente: int) -> list[int]:
        """q ids embaralhados: metade presentes (sorteados com reposição) e metade
        ausentes. O ausente é um id existente deslocado de até 500 (como um id
        digitado errado ou de anúncio que saiu), assim ele cai na mesma região
        dos ids reais em qualquer distribuição."""
        rnd = random.Random(semente)
        ids = [a.id for a in registros]
        existentes = set(ids)
        presentes = [rnd.choice(ids) for _ in range(q // 2)]
        ausentes = []
        while len(ausentes) < q - q // 2:
            x = rnd.choice(ids) + rnd.randint(-500, 500)
            if x >= 0 and x not in existentes:
                ausentes.append(x)
        lote = presentes + ausentes
        rnd.shuffle(lote)
        return lote


# ---------- sequências de operações para o cenário com atualizações ----------
# Operações: ("consulta", id) | ("inserir", Anuncio) | ("alterar", id, preco) | ("remover", id)

def _ausente(rnd, presentes: list[int], removidos: list[int], existentes: set) -> int:
    """Id ausente: metade das vezes um id já removido (quando há), senão um vizinho inexistente."""
    if removidos and rnd.random() < 0.5:
        return rnd.choice(removidos)
    while True:
        x = rnd.choice(presentes) + rnd.randint(-500, 500)
        if x >= 0 and x not in existentes:
            return x


def _consultas(rnd, presentes: list[int], removidos: list[int], existentes: set, q: int) -> list:
    """q consultas: 50% ids presentes e 50% ausentes, embaralhadas."""
    ops = [("consulta", rnd.choice(presentes)) for _ in range(q // 2)]
    ops += [("consulta", _ausente(rnd, presentes, removidos, existentes)) for _ in range(q - q // 2)]
    rnd.shuffle(ops)
    return ops


def sequencia_trimestral(coletas: list[list[Anuncio]], q: int, semente: int) -> list:
    """Atualizações reais: entre uma coleta e a seguinte, remove os anúncios que
    sumiram, insere os novos e altera o preço dos que mudaram de preço.
    Antes de cada lote de atualizações (e no final) roda q consultas."""
    rnd = random.Random(semente)
    atual = {a.id: a for a in coletas[0]}   # dict só para montar a sequência
    removidos = []
    ops = []
    for proxima in coletas[1:]:
        ops += _consultas(rnd, list(atual), removidos, set(atual), q)
        nova = {a.id: a for a in proxima}
        sairam = sorted(set(atual) - set(nova))
        entraram = sorted(set(nova) - set(atual))
        mudaram = sorted(i for i in set(atual) & set(nova) if atual[i].preco != nova[i].preco)
        ops += [("remover", i) for i in sairam]
        ops += [("inserir", nova[i]) for i in entraram]
        ops += [("alterar", i, nova[i].preco) for i in mudaram]
        removidos += sairam
        # quem foi reinserido deixa de ser "removido"
        removidos = [i for i in removidos if i not in nova]
        atual = nova
    ops += _consultas(rnd, list(atual), removidos, set(atual), q)
    return ops


def sequencia_intercalada(base: list[Anuncio], extras: list[Anuncio], n_ops: int, semente: int,
                          proporcoes=(0.80, 0.10, 0.05, 0.05)) -> list:
    """Operações sorteadas uma a uma: consulta, alteração de preço, inserção e
    remoção nas proporções dadas. extras são anúncios de coletas posteriores que
    não estão na base, usados nas inserções."""
    rnd = random.Random(semente)
    presentes = [a.id for a in base]
    existentes = set(presentes)
    removidos = []
    fila_extras = list(extras)
    rnd.shuffle(fila_extras)
    ops = []
    p_cons, p_alt, p_ins, _ = proporcoes
    while len(ops) < n_ops:
        x = rnd.random()
        if x < p_cons:
            if rnd.random() < 0.5:
                ops.append(("consulta", rnd.choice(presentes)))
            else:
                ops.append(("consulta", _ausente(rnd, presentes, removidos, existentes)))
        elif x < p_cons + p_alt:
            ops.append(("alterar", rnd.choice(presentes), round(rnd.uniform(15, 300), 2)))
        elif x < p_cons + p_alt + p_ins:
            if fila_extras:
                a = fila_extras.pop()
                ops.append(("inserir", a))
                presentes.append(a.id)
                existentes.add(a.id)
        else:
            i = rnd.randrange(len(presentes))
            id_rem = presentes[i]
            presentes[i] = presentes[-1]
            presentes.pop()
            existentes.discard(id_rem)
            removidos.append(id_rem)
            ops.append(("remover", id_rem))
    return ops


def resumo_sequencia(ops: list) -> dict:
    contagem = {"consulta": 0, "inserir": 0, "alterar": 0, "remover": 0}
    for op in ops:
        contagem[op[0]] += 1
    return contagem


def anuncios_novos(base: list[Anuncio], posteriores: list[list[Anuncio]]) -> list[Anuncio]:
    """Anúncios das coletas posteriores que não estão na base, sem repetir id
    (um anúncio novo de jun aparece de novo em set e dez: fica o de jun)."""
    vistos = {a.id for a in base}
    novos = []
    for coleta in posteriores:
        for a in coleta:
            if a.id not in vistos:
                vistos.add(a.id)
                novos.append(a)
    return novos
