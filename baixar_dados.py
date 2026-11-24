"""Baixa a base do Kaggle e guarda o recorte bruto usado no projeto.

Fonte: "2021 Lisbon Airbnb Data" (maurylukas/listings), licença CC BY 4.0,
que redistribui os arquivos listings.csv do Inside Airbnb (insideairbnb.com)
de Lisboa em quatro coletas de 2021: mar, jun, set e dez.

O arquivo original tem 74 colunas e ~48 MB por coleta. Guardamos so as colunas
que o sistema usa, sem mexer nos valores (o preço continua texto "$1,234.00",
nulos continuam nulos). A limpeza fica em airbnb/dados.py.

Uso:  python baixar_dados.py
"""
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

URL = "https://www.kaggle.com/api/v1/datasets/download/maurylukas/listings"
COLETAS = {"mar21": "listings mar21.csv", "jun21": "listings jun21.csv",
           "sep21": "listings sep21.csv", "dec21": "listings dec21.csv"}
COLUNAS = ["id", "last_scraped", "name", "host_id", "neighbourhood_cleansed",
           "neighbourhood_group_cleansed", "room_type", "price", "accommodates",
           "number_of_reviews", "review_scores_rating", "license"]

PASTA = Path(__file__).parent / "dados" / "bruto"


def main():
    PASTA.mkdir(parents=True, exist_ok=True)
    print("baixando", URL)
    # com User-Agent de navegador o Kaggle responde 404, com um simples funciona
    pedido = urllib.request.Request(URL, headers={"User-Agent": "python"})
    with urllib.request.urlopen(pedido) as resp:
        conteudo = resp.read()
    print(f"{len(conteudo) / 1e6:.1f} MB recebidos")
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for coleta, nome in COLETAS.items():
            with z.open(nome) as f:
                df = pd.read_csv(f, usecols=COLUNAS, dtype=str, keep_default_na=False)
            # dtype=str e keep_default_na=False: o texto fica exatamente como veio
            df = df[COLUNAS]
            destino = PASTA / f"listings_{coleta}.csv"
            df.to_csv(destino, index=False)
            print(destino, df.shape)


if __name__ == "__main__":
    sys.exit(main())
