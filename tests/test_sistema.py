import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airbnb import (Anuncio, chave_id, chave_preco, Metricas, InsertionSort, MergeSort, HeapSort,
                    TabelaHash, BuscaSequencial, BuscaBinaria, BuscaInterpolacao, ConsultaHash,
                    Repositorio)
from airbnb.arquivos import ler_anuncios_csv, escrever_anuncios_csv

ORDENACOES = [InsertionSort(), MergeSort(), HeapSort()]
CONSULTAS = [BuscaSequencial, BuscaBinaria, BuscaInterpolacao, ConsultaHash]


def novo(id, preco=50.0, nome="Apto", **kw):
    return Anuncio(id, nome, "Arroios", "Lisboa", "Entire home/apt", preco, 2, **kw)


def base_aleatoria(n, semente=1, precos=None):
    rnd = random.Random(semente)
    ids = rnd.sample(range(10_000_000), n)
    return [novo(i, rnd.choice(precos) if precos else round(rnd.uniform(10, 500), 2)) for i in ids]


# ---------- entidade ----------

def test_id_invalido():
    for ruim in (-1, 1.5, "3", True):
        with pytest.raises(ValueError):
            novo(ruim)


def test_id_imutavel():
    a = novo(10)
    with pytest.raises(AttributeError):
        a.id = 11
    with pytest.raises(ValueError):
        a.alterar(id=11)
    assert a.id == 10


def test_validacao_e_alteracao_atomica():
    with pytest.raises(ValueError):
        novo(1, preco=0)
    with pytest.raises(ValueError):
        Anuncio(1, "x", "b", "m", "Castelo", 10, 1)
    a = novo(1, preco=80)
    with pytest.raises(ValueError):
        a.alterar(preco=90, capacidade=0)   # capacidade inválida: nada muda
    assert a.preco == 80
    a.alterar(preco=90, nota=4.5)
    assert a.preco == 90 and a.nota == 4.5


def test_csv_ida_e_volta(tmp_path):
    regs = base_aleatoria(50) + [novo(7, nome='Casa "Alfama", vista', nota=None, licenca=None)]
    caminho = tmp_path / "a.csv"
    escrever_anuncios_csv(regs, caminho)
    assert ler_anuncios_csv(caminho) == regs


# ---------- ordenação ----------

@pytest.mark.parametrize("n", [0, 1, 2, 57, 300])
def test_ordenacoes_iguais_a_referencia(n):
    regs = base_aleatoria(n, precos=[10.0, 20.0, 30.0])   # muitos empates no preço
    esperado = sorted(regs, key=chave_preco)
    for o in ORDENACOES:
        copia_entrada = list(regs)
        saida = o.ordenar(regs, chave_preco)
        assert [r.id for r in saida] == [r.id for r in esperado], o.nome
        assert regs == copia_entrada          # não altera a entrada
        assert all(a is b for a, b in zip(sorted(saida, key=chave_id), sorted(regs, key=chave_id)))


def test_empate_desfeito_pelo_id():
    regs = [novo(5, 10), novo(3, 10), novo(9, 5), novo(1, 10)]
    for o in ORDENACOES:
        assert [r.id for r in o.ordenar(regs, chave_preco)] == [9, 1, 3, 5]


@pytest.mark.parametrize("perfil", ["ordenado", "inverso"])
def test_ordenacoes_perfis(perfil):
    regs = sorted(base_aleatoria(200), key=chave_preco, reverse=(perfil == "inverso"))
    for o in ORDENACOES:
        assert o.ordenar(regs, chave_preco) == sorted(regs, key=chave_preco)


def test_metricas_insertion_ordenado_e_linear():
    regs = sorted(base_aleatoria(100), key=chave_preco)
    m = Metricas()
    InsertionSort().ordenar(regs, chave_preco, m)
    assert m.comparacoes == 99


def test_heapsort_registra_passos():
    h = HeapSort(registrar_passos=True)
    h.ordenar([novo(i, p) for i, p in enumerate([5.0, 3.0, 8.0, 1.0, 9.0])], chave_preco)
    construida = [k[0] for k in h.passos[0][1]]
    assert construida[0] == 9.0
    for i in range(len(construida)):
        for f in (2 * i + 1, 2 * i + 2):
            if f < len(construida):
                assert construida[i] >= construida[f]   # propriedade de heap


# ---------- hash ----------

def test_hash_basico_e_colisao_deliberada():
    t = TabelaHash(11)
    m = t.capacidade
    a, b, c = novo(5), novo(5 + m), novo(5 + 2 * m)   # mesmo balde
    for r in (a, b, c):
        t.inserir(r)
    assert t.colisoes == 2
    assert t.buscar(5 + m) is b
    assert t.remover(5 + m) is True
    assert t.buscar(5 + m) is None            # consulta após remoção
    assert t.buscar(5 + 2 * m) is c           # o resto do balde continua acessível
    assert t.remover(5 + m) is False
    with pytest.raises(ValueError):
        t.inserir(novo(5))


def test_hash_fator_de_carga_e_rehash():
    t = TabelaHash(11, fator_max=0.75)
    for r in base_aleatoria(100):
        t.inserir(r)
    assert len(t) == 100 and t.fator_carga <= 0.75 and t.rehashes > 0
    t2 = TabelaHash(101)
    for r in base_aleatoria(50):
        t2.inserir(r)
    assert t2.fator_carga == pytest.approx(50 / 101)


# ---------- consultas ----------

def ids_teste(regs, rnd, k=200):
    presentes = [r.id for r in rnd.sample(regs, min(k, len(regs)))]
    ausentes = [rnd.randrange(-5, 10_000_100) for _ in range(k)]
    return presentes + ausentes + [0, 10_000_000]


@pytest.mark.parametrize("n", [0, 1, 2, 500])
def test_todas_as_consultas_concordam(n):
    rnd = random.Random(n)
    regs = base_aleatoria(n, semente=n + 3)
    consultas = [C() for C in CONSULTAS]
    for c in consultas:
        with pytest.raises(RuntimeError):
            c.buscar(1)
        c.preparar(regs)
    for id in ids_teste(regs, rnd):
        respostas = [c.buscar(id) for c in consultas]
        esperado = next((r for r in regs if r.id == id), None)
        assert all(r is esperado for r in respostas), id


def test_interpolacao_chaves_concentradas():
    # ids pequenos + alguns gigantes (como os ids de 18 dígitos do Airbnb)
    regs = [novo(i) for i in range(1000)] + [novo(10 ** 18 + i) for i in range(5)]
    c = BuscaInterpolacao()
    c.preparar(regs)
    for r in regs:
        assert c.buscar(r.id) is r
    assert c.buscar(1000) is None and c.buscar(10 ** 18 + 99) is None


def test_mesmo_cliente_estrategias_diferentes():
    # o mesmo código cliente funciona com qualquer EstrategiaConsulta
    def contar_presentes(consulta, regs, ids):
        consulta.preparar(regs)
        return sum(consulta.buscar(i) is not None for i in ids)
    regs = base_aleatoria(300)
    ids = [r.id for r in regs[:100]] + list(range(10_000_001, 10_000_101))
    assert {contar_presentes(C(), regs, ids) for C in CONSULTAS} == {100}


# ---------- repositório ----------

def repo_com(regs):
    r = Repositorio([C() for C in CONSULTAS])
    r.carregar(regs)
    return r


def test_repositorio_vazio_e_um_registro():
    r = repo_com([])
    for nome in r.nomes_consultas:
        assert r.buscar(1, nome) is None
    r.inserir(novo(42))
    for nome in r.nomes_consultas:
        assert r.buscar(42, nome).id == 42


def test_repositorio_rejeita_duplicado_e_id_imutavel():
    r = repo_com([novo(1), novo(2)])
    with pytest.raises(ValueError):
        r.inserir(novo(1, preco=99))
    with pytest.raises(ValueError):
        r.atualizar(1, {"id": 3})
    with pytest.raises(KeyError):
        r.atualizar(999, {"preco": 10.0})
    assert len(r) == 2


def test_consistencia_apos_atualizacoes():
    rnd = random.Random(7)
    regs = base_aleatoria(400)
    r = repo_com(regs)
    for nome in r.nomes_consultas:      # prepara todas
        r.buscar(regs[0].id, nome)
    removidos = [x.id for x in rnd.sample(regs, 50)]
    for i in removidos:
        assert r.remover(i) is True
    assert r.remover(removidos[0]) is False
    novos = [novo(20_000_000 + i, 33.0) for i in range(30)]
    for x in novos:
        r.inserir(x)
    r.atualizar(novos[0].id, {"preco": 77.0})
    for i in removidos:                   # objeto removido não volta
        assert all(r.buscar(i, nome) is None for nome in r.nomes_consultas)
    for x in novos:
        assert all(r.buscar(x.id, nome) is x for nome in r.nomes_consultas)
    assert r.buscar(novos[0].id, "binaria").preco == 77.0
    assert r.reconstrucoes["binaria"] == 2 and r.reconstrucoes["hash"] == 1
    assert len(r) == 400 - 50 + 30


def test_relatorio_tres_ordenacoes_iguais():
    r = repo_com(base_aleatoria(300, precos=[40.0, 60.0, 60.0, 90.0]))
    rel = [r.relatorio(o) for o in ORDENACOES]
    assert rel[0] == rel[1] == rel[2]
    assert len(rel[0]) == 300


def test_busca_ordenada_incremental():
    regs = base_aleatoria(300)
    r = Repositorio([BuscaBinaria(incremental=True), BuscaSequencial()])
    r.carregar(regs)
    r.buscar(regs[0].id, "binaria")
    for x in regs[:40]:
        r.remover(x.id)
    novos = [novo(i) for i in (3, 10_500_000, 5_000_001)]
    for x in novos:
        r.inserir(x)
    for id in [x.id for x in regs] + [x.id for x in novos] + [4, 11_000_000]:
        assert r.buscar(id, "binaria") is r.buscar(id, "sequencial")
    assert r.reconstrucoes["binaria"] == 1
