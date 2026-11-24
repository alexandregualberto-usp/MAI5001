"""Executor de experimentos.

ExecutorExperimentos recebe por composição as estratégias de ordenação, as
fábricas de estratégias de consulta e o gerador de cargas. Cada execução cria
seu próprio objeto Metricas; não há contador global.

Protocolo de medição:
- tempo com time.perf_counter_ns (nanossegundos), gc desligado durante a
  medição e ligado logo depois;
- leitura, geração da entrada e validação ficam fora do tempo;
- execuções de tempo NÃO usam Metricas (os contadores custam tempo); contagem
  de operações e memória são feitas em execuções separadas, na repetição 0;
- memória com tracemalloc: pico de bytes alocados pelo Python durante a
  chamada. Mede só o que foi alocado ali dentro (cópias, listas auxiliares,
  tabela), não os anúncios que já existiam;
- aquecimento: uma rodada pequena de cada estratégia antes de medir.

Saída: lista de ResultadoExecucao em formato longo (uma medida por linha),
com experimento, estratégia, n, perfil, parâmetro, repetição, semente, medida,
valor e unidade.
"""
import bisect
import csv
import gc
import tracemalloc
from dataclasses import dataclass, field, asdict
from pathlib import Path
from time import perf_counter_ns
from typing import Callable, Sequence

from airbnb.anuncio import Anuncio, chave_preco
from airbnb.cargas import GeradorCargas, resumo_sequencia
from airbnb.consulta import EstrategiaConsulta
from airbnb.hash_tabela import TabelaHash
from airbnb.metricas import Metricas
from airbnb.ordenacao import EstrategiaOrdenacao
from airbnb.repositorio import Repositorio


# ---------- referências nativas (fora do núcleo, só para comparação) ----------

class ReferenciaDict(EstrategiaConsulta):
    """dict do Python. Só aparece nos experimentos como referência."""
    nome = "ref_dict"

    def preparar(self, registros, metricas=None):
        self._d = {r.id: r for r in registros}
        self._preparada = True

    def buscar(self, id, metricas=None):
        return self._d.get(id)


class ReferenciaBisect(EstrategiaConsulta):
    """sorted + bisect (implementados em C). Só referência."""
    nome = "ref_bisect"

    def preparar(self, registros, metricas=None):
        self._v = sorted(registros, key=lambda r: r.id)
        self._ids = [r.id for r in self._v]
        self._preparada = True

    def buscar(self, id, metricas=None):
        p = bisect.bisect_left(self._ids, id)
        if p < len(self._ids) and self._ids[p] == id:
            return self._v[p]
        return None


class ReferenciaSorted(EstrategiaOrdenacao):
    nome = "ref_sorted"

    def ordenar(self, registros, chave, metricas=None):
        return sorted(registros, key=chave)

    def _ordenar_itens(self, v, m):
        pass


# ---------- configuração e resultado ----------

@dataclass
class ConfiguracaoExperimento:
    tipo: str                          # ordenacao | busca | hash | lote | misto
    tamanhos: tuple = ()
    perfis: tuple = ()                 # perfis de entrada ou distribuições de id
    repeticoes: int = 5
    semente: int = 2024
    q: int = 2000                      # consultas por lote
    alfas: tuple = ()
    qs: tuple = ()                     # tamanhos de lote (custo total)
    cenarios: dict = field(default_factory=dict)   # nome -> (base inicial, operações)


@dataclass
class ResultadoExecucao:
    experimento: str
    estrategia: str
    n: int
    perfil: str
    parametro: str
    repeticao: int
    semente: int
    medida: str
    valor: float
    unidade: str


def salvar_resultados(resultados: Sequence[ResultadoExecucao], caminho: str | Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    campos = list(ResultadoExecucao.__dataclass_fields__)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for r in resultados:
            w.writerow(asdict(r))


# ---------- medição ----------

def medir_tempo(f, *args) -> int:
    gc.collect()
    gc.disable()
    try:
        t0 = perf_counter_ns()
        f(*args)
        return perf_counter_ns() - t0
    finally:
        gc.enable()


def medir_pico(f, *args) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        f(*args)
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def rodar_lote(consulta: EstrategiaConsulta, lote: Sequence[int]) -> None:
    for id in lote:
        consulta.buscar(id)


# ---------- executor ----------

class ExecutorExperimentos:
    def __init__(self, gerador: GeradorCargas,
                 ordenacoes: Sequence[EstrategiaOrdenacao] = (),
                 consultas: Sequence[Callable[[], EstrategiaConsulta]] = (),
                 referencias: bool = True):
        self.gerador = gerador
        self.ordenacoes = list(ordenacoes)
        self.consultas = list(consultas)
        self.referencias = referencias
        self.avisos: list[str] = []      # divergências encontradas na validação

    def executar(self, config: ConfiguracaoExperimento) -> list[ResultadoExecucao]:
        metodos = {"ordenacao": self._ordenacao, "busca": self._busca, "hash": self._hash,
                   "lote": self._lote, "misto": self._misto}
        if config.tipo not in metodos:
            raise ValueError(f"tipo de experimento desconhecido: {config.tipo}")
        self._aquecer()
        return metodos[config.tipo](config)

    def _aquecer(self):
        pequena = self.gerador.amostra(min(200, len(self.gerador.base)), 0)
        for o in self.ordenacoes:
            o.ordenar(pequena, chave_preco)
        for fabrica in self.consultas:
            c = fabrica()
            c.preparar(pequena)
            rodar_lote(c, [a.id for a in pequena])

    # ----- ordenação -----
    def _ordenacao(self, cfg):
        res = []
        ordenacoes = self.ordenacoes + ([ReferenciaSorted()] if self.referencias else [])
        for n in cfg.tamanhos:
            for perfil in cfg.perfis:
                for rep in range(cfg.repeticoes):
                    s = cfg.semente + 1000 * rep + n
                    entrada = self.gerador.perfil(self.gerador.amostra(n, s), perfil, s)
                    esperado = [a.id for a in sorted(entrada, key=chave_preco)]

                    def add(est, medida, valor, unidade):
                        res.append(ResultadoExecucao("ordenacao", est, n, perfil, "chave=(preco,id)",
                                                     rep, s, medida, valor, unidade))

                    for o in ordenacoes:
                        add(o.nome, "tempo", medir_tempo(o.ordenar, entrada, chave_preco), "ns")
                        if rep == 0 and not o.nome.startswith("ref_"):
                            m = Metricas()
                            saida = o.ordenar(entrada, chave_preco, m)
                            if [a.id for a in saida] != esperado:
                                self.avisos.append(f"ordenação {o.nome} n={n} {perfil} divergiu")
                            add(o.nome, "comparacoes", m.comparacoes, "contagem")
                            add(o.nome, "movimentacoes", m.movimentacoes, "contagem")
                            add(o.nome, "memoria_pico", medir_pico(o.ordenar, entrada, chave_preco), "bytes")
        return res

    # ----- busca -----
    def _fabricas_busca(self):
        fabricas = list(self.consultas)
        if self.referencias:
            fabricas += [ReferenciaDict, ReferenciaBisect]
        return fabricas

    def _busca(self, cfg):
        res = []
        for dist in cfg.perfis:
            for n in cfg.tamanhos:
                for rep in range(cfg.repeticoes):
                    s = cfg.semente + 1000 * rep + n
                    base = self.gerador.com_distribuicao(self.gerador.amostra(n, s), dist, s)
                    lote = self.gerador.lote_consultas(base, cfg.q, s)
                    respostas_ref = None
                    for fabrica in self._fabricas_busca():
                        c = fabrica()
                        nome = c.rotulo

                        def add(medida, valor, unidade):
                            res.append(ResultadoExecucao("busca", nome, n, dist, f"Q={cfg.q}",
                                                         rep, s, medida, valor, unidade))

                        add("tempo_preparacao", medir_tempo(c.preparar, base), "ns")
                        t = medir_tempo(rodar_lote, c, lote)
                        add("tempo_lote", t, "ns")
                        add("tempo_por_consulta", t / cfg.q, "ns")
                        if rep == 0:
                            c2 = fabrica()
                            add("memoria_preparacao", medir_pico(c2.preparar, base), "bytes")
                            if nome.startswith("ref_"):
                                continue
                            passos_ok, passos_erro, respostas = [], [], []
                            for id in lote:
                                m = Metricas()
                                r = c2.buscar(id, m)
                                respostas.append(r)
                                (passos_ok if r is not None else passos_erro).append(m.passos)
                            if respostas_ref is None:
                                respostas_ref = respostas
                            elif any(a is not b for a, b in zip(respostas, respostas_ref)):
                                self.avisos.append(f"busca {nome} n={n} {dist} divergiu")
                            add("passos_medio_acerto", sum(passos_ok) / max(1, len(passos_ok)), "passos")
                            add("passos_medio_erro", sum(passos_erro) / max(1, len(passos_erro)), "passos")
                            add("passos_max", max(passos_ok + passos_erro), "passos")
        return res

    # ----- hash -----
    def _hash(self, cfg):
        res = []
        base = self.gerador.base
        n = len(base)
        for alfa in cfg.alfas:
            for rep in range(cfg.repeticoes):
                s = cfg.semente + 1000 * rep
                lote = self.gerador.lote_consultas(base, cfg.q, s)
                t = TabelaHash(round(n / alfa))

                def construir():
                    for a in base:
                        t.inserir(a)

                def add(medida, valor, unidade):
                    res.append(ResultadoExecucao("hash", "hash_encadeamento", n, "real",
                                                 f"alfa={alfa}", rep, s, medida, valor, unidade))

                add("tempo_construcao", medir_tempo(construir), "ns")
                def consultar():
                    for i in lote:
                        t.buscar(i)

                tl = medir_tempo(consultar)
                add("tempo_por_consulta", tl / cfg.q, "ns")
                if rep == 0:
                    tam = t.tamanhos_baldes()
                    add("capacidade_M", t.capacidade, "baldes")
                    add("alfa_real", t.fator_carga, "N/M")
                    add("colisoes", t.colisoes, "contagem")
                    add("baldes_vazios_pct", 100 * tam.count(0) / len(tam), "%")
                    add("maior_balde", max(tam), "elementos")
                    ok, erro = [], []
                    for i in lote:
                        m = Metricas()
                        (ok if t.buscar(i, m) is not None else erro).append(m.passos)
                    add("passos_medio_acerto", sum(ok) / len(ok), "comparacoes")
                    add("passos_medio_erro", sum(erro) / len(erro), "comparacoes")
                    add("teoria_acerto", 1 + t.fator_carga / 2, "comparacoes")
                    add("teoria_erro", t.fator_carga, "comparacoes")
                    add("memoria_construcao", medir_pico(self._montar_hash, base, alfa), "bytes")
        return res

    @staticmethod
    def _montar_hash(base, alfa):
        t = TabelaHash(round(len(base) / alfa))
        for a in base:
            t.inserir(a)
        return t

    # ----- lote estático: preparação + Q consultas -----
    def _lote(self, cfg):
        res = []
        base = self.gerador.base
        n = len(base)
        for q in cfg.qs:
            for rep in range(cfg.repeticoes):
                s = cfg.semente + 1000 * rep + q
                lote = self.gerador.lote_consultas(base, q, s)
                for fabrica in self._fabricas_busca():
                    c = fabrica()

                    def tudo():
                        c.preparar(base)
                        rodar_lote(c, lote)

                    res.append(ResultadoExecucao("lote", c.rotulo, n, "real", f"Q={q}", rep, s,
                                                 "tempo_total", medir_tempo(tudo), "ns"))
        return res

    # ----- misto: consultas + inserções + alterações + remoções -----
    def _misto(self, cfg):
        res = []
        for cenario, (base, ops) in cfg.cenarios.items():
            cont = resumo_sequencia(ops)
            param = ";".join(f"{k}={v}" for k, v in cont.items())
            for rep in range(cfg.repeticoes):
                respostas_ref = None
                for fabrica in self.consultas:
                    c = fabrica()
                    nome = c.rotulo
                    repo = Repositorio([c])
                    repo.carregar([a.copia() for a in base])        # fora do tempo
                    ops_rep = [("inserir", op[1].copia()) if op[0] == "inserir" else op for op in ops]
                    respostas = []
                    tempos = {"consulta": 0, "inserir": 0, "alterar": 0, "remover": 0}
                    gc.collect()
                    gc.disable()
                    try:
                        for op in ops_rep:
                            t0 = perf_counter_ns()
                            tipo = op[0]
                            if tipo == "consulta":
                                r = repo.buscar(op[1], c.nome)
                                respostas.append(None if r is None else (r.id, r.preco))
                            elif tipo == "inserir":
                                repo.inserir(op[1])
                            elif tipo == "alterar":
                                repo.atualizar(op[1], {"preco": op[2]})
                            else:
                                repo.remover(op[1])
                            tempos[tipo] += perf_counter_ns() - t0
                    finally:
                        gc.enable()
                    if respostas_ref is None:
                        respostas_ref = respostas
                    elif respostas != respostas_ref:
                        self.avisos.append(f"misto {cenario} {nome} rep={rep} divergiu")

                    def add(medida, valor, unidade):
                        res.append(ResultadoExecucao("misto", nome, len(base), cenario, param, rep,
                                                     cfg.semente, medida, valor, unidade))

                    add("tempo_total", sum(tempos.values()), "ns")
                    for tipo, v in tempos.items():
                        add(f"tempo_{tipo}", v, "ns")
                    add("reconstrucoes", repo.reconstrucoes[c.nome], "contagem")
                    add("respostas_iguais", 1 if respostas == respostas_ref else 0, "bool")
        return res
