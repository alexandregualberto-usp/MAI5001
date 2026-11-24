"""Preparação da base com pandas: caracterização, limpeza e resumo do domínio.

O bruto (dados/bruto) nunca é sobrescrito. limpar() devolve o DataFrame limpo
e um log com cada transformação e quantas linhas ela afetou.
"""
from pathlib import Path

import pandas as pd

from airbnb.anuncio import COLUNAS_CSV, TIPOS_QUARTO

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BRUTO = RAIZ / "dados" / "bruto"
PASTA_LIMPO = RAIZ / "dados" / "limpo"
COLETAS = ["mar21", "jun21", "sep21", "dec21"]

RENOMEAR = {"name": "nome", "neighbourhood_cleansed": "bairro",
            "neighbourhood_group_cleansed": "municipio", "room_type": "tipo_quarto",
            "price": "preco", "accommodates": "capacidade",
            "number_of_reviews": "avaliacoes", "review_scores_rating": "nota",
            "license": "licenca"}


def ler_bruto(coleta: str) -> pd.DataFrame:
    # tudo como texto, como veio; a conversão de tipos é parte da limpeza
    return pd.read_csv(PASTA_BRUTO / f"listings_{coleta}.csv", dtype=str, keep_default_na=False)


def caracterizar(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por coluna: vazios, distintos e exemplo (sobre o bruto)."""
    linhas = []
    for c in df.columns:
        vazios = (df[c].str.strip() == "").sum()
        linhas.append({"coluna": c, "vazios": vazios, "pct_vazios": round(100 * vazios / len(df), 2),
                       "distintos": df[c].nunique(), "exemplo": df[c].iloc[0]})
    return pd.DataFrame(linhas)


def limpar(bruto: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = bruto.copy()
    log = []

    def registra(etapa, n, decisao):
        log.append({"etapa": etapa, "linhas": int(n), "decisao": decisao})

    registra("entrada", len(df), "linhas no bruto")

    # id
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    ruins = df["id"].isna() | (df["id"] < 0)
    registra("id inválido", ruins.sum(), "descartar: sem id não há registro")
    df = df[~ruins]
    df["id"] = df["id"].astype("int64")
    dup = df["id"].duplicated()
    registra("id duplicado", dup.sum(), "manter a primeira ocorrência")
    df = df[~dup]

    df = df.rename(columns=RENOMEAR)

    # nome
    df["nome"] = df["nome"].str.strip()
    vazio = df["nome"] == ""
    registra("nome vazio", vazio.sum(), "imputar '(sem nome)': o resto do anúncio é válido")
    df.loc[vazio, "nome"] = "(sem nome)"

    # preço: "$1,234.00" -> 1234.0. O Inside Airbnb usa o símbolo $ mas o valor
    # está na moeda local (euro em Lisboa)
    df["preco"] = pd.to_numeric(df["preco"].str.replace("$", "", regex=False)
                                .str.replace(",", "", regex=False), errors="coerce")
    ruins = df["preco"].isna() | (df["preco"] <= 0)
    registra("preço ausente ou <= 0", ruins.sum(), "descartar: preço é o atributo principal")
    df = df[~ruins]
    registra("preço > 1000 €/noite", (df["preco"] > 1000).sum(),
             "manter e sinalizar: pode ser erro do anfitrião, mas não há como provar")

    # capacidade
    df["capacidade"] = pd.to_numeric(df["capacidade"], errors="coerce")
    ruins = df["capacidade"].isna() | (df["capacidade"] < 1)
    registra("capacidade < 1", ruins.sum(), "descartar: anúncio para 0 hóspedes não é válido")
    df = df[~ruins]
    df["capacidade"] = df["capacidade"].astype(int)

    # tipo de quarto
    ruins = ~df["tipo_quarto"].isin(TIPOS_QUARTO)
    registra("tipo_quarto fora do domínio", ruins.sum(), "descartar")
    df = df[~ruins]

    # avaliações e nota
    df["avaliacoes"] = pd.to_numeric(df["avaliacoes"], errors="coerce").fillna(0).astype(int)
    df["nota"] = pd.to_numeric(df["nota"], errors="coerce")
    # na coleta de mar/21 a nota vem em 0-100; a partir de jun/21 o Inside Airbnb
    # passou a publicar 0-5. Se a coleta inteira está acima de 5, convertemos /20
    if df["nota"].max() > 5:
        registra("nota em escala 0-100", df["nota"].notna().sum(),
                 "converter para 0-5 dividindo por 20 (mudança de escala da fonte)")
        df["nota"] = df["nota"] / 20
    fora =df["nota"].notna() & ((df["nota"] < 0) | (df["nota"] > 5))
    registra("nota fora de [0,5]", fora.sum(), "virar ausente")
    df.loc[fora, "nota"] = None
    sem_nota = df["nota"].isna()
    registra("nota ausente", sem_nota.sum(),
             "manter ausente (None): anúncio sem avaliação, não imputar")
    registra("nota ausente com avaliacoes > 0", (sem_nota & (df["avaliacoes"] > 0)).sum(),
             "manter: o Airbnb só mostra nota a partir de algumas avaliações")

    # licença
    df["licenca"] = df["licenca"].str.strip()
    vazia = df["licenca"] == ""
    registra("licença ausente", vazia.sum(), "manter ausente (None)")
    df.loc[vazia, "licenca"] = None

    # texto de bairro/município
    registra("bairro/município com letras acentuadas perdidas na fonte", 0,
             "manter como veio (ex.: 'Belm' = Belém); é igual nas 4 coletas, então agrupa certo")

    # quase duplicados: mesmo anfitrião, nome, preço e capacidade
    quase = df.duplicated(subset=["host_id", "nome", "preco", "capacidade"])
    registra("quase duplicados (mesmo host/nome/preço/capacidade)", quase.sum(),
             "manter: são unidades diferentes de um mesmo anfitrião (ids diferentes)")

    registra("saída", len(df), "linhas no arquivo limpo")
    limpo = df[COLUNAS_CSV].sort_values("id").reset_index(drop=True)
    return limpo, pd.DataFrame(log)


def preparar_todas(salvar: bool = True) -> dict:
    """Limpa as quatro coletas. Devolve {coleta: (limpo, log)}."""
    saida = {}
    for coleta in COLETAS:
        limpo, log = limpar(ler_bruto(coleta))
        if salvar:
            PASTA_LIMPO.mkdir(parents=True, exist_ok=True)
            limpo.to_csv(PASTA_LIMPO / f"anuncios_{coleta}.csv", index=False)
            log.to_csv(PASTA_LIMPO / f"log_limpeza_{coleta}.csv", index=False)
        saida[coleta] = (limpo, log)
    return saida


def resumo_municipios(df: pd.DataFrame) -> pd.DataFrame:
    """Contagem, preço mediano e % sem licença por município."""
    g = df.groupby("municipio")
    r = pd.DataFrame({
        "anuncios": g.size(),
        "preco_mediano": g["preco"].median(),
        "pct_casa_inteira": g["tipo_quarto"].apply(lambda s: 100 * (s == "Entire home/apt").mean()),
        "pct_sem_licenca": g["licenca"].apply(lambda s: 100 * s.isna().mean()),
    })
    return r.sort_values("anuncios", ascending=False).round(1)


def resumo_tipos(df: pd.DataFrame) -> pd.DataFrame:
    return (df.groupby("tipo_quarto")["preco"]
            .describe(percentiles=[0.25, 0.5, 0.75, 0.95])
            .sort_values("count", ascending=False).round(1))
