# Projeto final – Anúncios do Airbnb em Lisboa

Sistema de consulta e manutenção de anúncios de hospedagem (Inside Airbnb, Lisboa, 4 coletas de 2021),
com ordenações, buscas e tabela hash próprias e uma investigação de quando vale a pena preparar índice.

O relatório completo está em `projeto_final.ipynb`.

## Ambiente

Testado com Python 3.14 (CPython, macOS arm64). Qualquer Python >= 3.10 deve servir.

```
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Dados

`dados/bruto/` já vem no zip (recorte de 12 colunas das 74 originais, valores sem alteração).
Para baixar de novo do Kaggle (dataset `maurylukas/listings`, CC BY 4.0, ~53 MB):

```
python baixar_dados.py
```

A limpeza gera `dados/limpo/anuncios_<coleta>.csv` e `log_limpeza_<coleta>.csv`; roda sozinha na
primeira vez que algum script precisa dela.

## Comandos

```
python demo.py                      # demonstração no terminal
python -m pytest -q                 # testes
python rodar_experimentos.py        # experimentos completos (~5 min), grava resultados/ e graficos/
python rodar_experimentos.py --rapido   # versão curta para conferir que tudo roda
jupyter nbconvert --to notebook --execute projeto_final.ipynb --output projeto_final.ipynb
```

No Colab: subir a pasta inteira (ou o zip e descompactar), `%cd` para ela e rodar o notebook do início.

## Estrutura

```
airbnb/anuncio.py        entidade Anuncio (validação, id imutável)
airbnb/metricas.py       contadores por execução
airbnb/ordenacao.py      EstrategiaOrdenacao + InsertionSort, MergeSort, HeapSort
airbnb/hash_tabela.py    TabelaHash (encadeamento, h = id mod M primo)
airbnb/consulta.py       EstrategiaConsulta + sequencial, binária, interpolação, adaptador da hash
airbnb/repositorio.py    Repositorio (coleção principal e consistência dos índices)
airbnb/arquivos.py       importar/exportar CSV
airbnb/dados.py          limpeza e resumos com pandas
airbnb/cargas.py         gerador das entradas e das sequências de operações
airbnb/experimentos.py   ExecutorExperimentos, configuração, resultados, referências nativas
airbnb/graficos.py       tabelas e gráficos a partir dos CSV de resultados
tests/test_sistema.py    testes (pytest)
resultados/*.csv         medições brutas (formato longo) e ambiente.txt
graficos/*.png           os quatro gráficos do relatório
```

Os gráficos podem ser refeitos só a partir dos CSV: `python -c "from airbnb import graficos; graficos.gerar_todos()"`.
