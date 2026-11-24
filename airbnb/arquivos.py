"""Leitura e escrita de anúncios em CSV (formato do arquivo limpo).

Formato: separador vírgula, UTF-8, cabeçalho igual a COLUNAS_CSV.
nota e licenca vazias significam None. preço em euros por noite.
Fica separado do repositório e dos algoritmos: eles não sabem de arquivo.
"""
import csv
from pathlib import Path
from typing import Iterable

from airbnb.anuncio import Anuncio, COLUNAS_CSV


def ler_anuncios_csv(caminho: str | Path) -> list[Anuncio]:
    anuncios = []
    with open(caminho, newline="", encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        if leitor.fieldnames != COLUNAS_CSV:
            raise ValueError(f"cabeçalho inesperado em {caminho}: {leitor.fieldnames}")
        for n_linha, lin in enumerate(leitor, start=2):
            try:
                anuncios.append(Anuncio(
                    id=int(lin["id"]),
                    nome=lin["nome"],
                    bairro=lin["bairro"],
                    municipio=lin["municipio"],
                    tipo_quarto=lin["tipo_quarto"],
                    preco=float(lin["preco"]),
                    capacidade=int(lin["capacidade"]),
                    avaliacoes=int(lin["avaliacoes"]),
                    nota=float(lin["nota"]) if lin["nota"] != "" else None,
                    licenca=lin["licenca"] if lin["licenca"] != "" else None,
                ))
            except ValueError as e:
                raise ValueError(f"{caminho}, linha {n_linha}: {e}") from e
    return anuncios


def escrever_anuncios_csv(anuncios: Iterable[Anuncio], caminho: str | Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUNAS_CSV)
        for a in anuncios:
            w.writerow(a.como_linha())
