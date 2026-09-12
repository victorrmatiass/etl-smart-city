# Smart City - ETL de Dados Abertos

Componente de ETL do projeto **Smart City - Plataforma de Gestão de Demandas Urbanas**. Extrai dados de mobilidade urbana do Portal de Dados Abertos (dados.gov.br), carrega o bruto no MongoDB, transforma com pandas e salva o resultado final no SQLite.

## Integrantes do grupo

- André Felipe da Silva Braga - afsb@cesar.school
- Dayvid Cristiano - dcvs2@cesar.school
- Deyvison Conrado - dmc2@cesar.school
- Jennifer Cristine - jclc2@cesar.school
- Letícia Gabriella - lgcs@cesar.school
- Levi Moraes - lmma@cesar.school
- Luis Henrique Facunde da Silva - lhfs@cesar.school
- Manuele Macêdo - mmps2@cesar.school
- Maria Aparecida - maers@cesar.school
- Peterson Jesus Feitosa de Melo - pjfm@cesar.school
- Rhaldney Robert - rrcd@cesar.school
- Victor César Matias da Silva - vcms@cesar.school

## Fonte de dados

Conjunto de dados **Mobilidade Brasil**, recurso de fichas de projetos de mobilidade, disponível em:

```
https://dados.gov.br/dataset/cf41fb63-4496-43cb-a043-08998291c858/resource/ed69dbee-4eda-4831-9492-d41ea27ba8d9/download/mobilidade-fichas-projetos.csv
```

O pipeline filtra os dados para a região metropolitana do **Recife**, foco do projeto.

## Como funciona

```
CSV (API dados.gov.br ou arquivo local em data/)
        |
        v
   Extract (baixa ou carrega o CSV)
        |
        v
Load.load_mongo  ->  MongoDB (coleção bruta)
        |
        v
Extract.extract_collection_from_mongo (relê + filtra RM Recife)
        |
        v
   Transform (limpeza / DataFrame)
        |
        v
Load.load_sqlite  ->  SQLite (tabela final)
```

Se o download direto da API falhar, o `run_etl.py` usa automaticamente o CSV salvo em `data/mobilidade-fichas-projetos.csv`.

## Instalação

```
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto:

```
CHAVE_API_DADOS_ABERTOS=sua_chave_de_api_aqui
MONGODB_URI=mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

Não versione o `.env` (ele já deve estar no `.gitignore`).

## Rodando o pipeline

```
python run_etl.py
```

Isso grava os dados brutos na coleção `MOBILIDADE_FICHAS_PROJETOS` (banco `SMART_CITY`) no MongoDB e salva o resultado transformado na tabela `mobilidade_fichas_projetos` do arquivo `smart_city.db`.

## Estrutura dos arquivos

```
etl-smart-city/
├── .env                          # chave da API e URI do MongoDB (não versionado)
├── data/
│   └── mobilidade-fichas-projetos.csv   # CSV local (fallback)
├── src/
│   ├── extract.py                # Extract: API + CSV local + leitura do MongoDB
│   ├── transform.py              # Transform: limpeza e organização em DataFrame
│   └── load.py                   # Load: persistência no MongoDB e no SQLite
├── run_etl.py                    # Orquestra o pipeline completo
├── requirements.txt
└── README.md
```
