# Smart City - ETL de Dados Abertos

Componente de ETL do projeto **Smart City - Plataforma de Gestão de Demandas Urbanas**. Extrai dados de mobilidade urbana do Portal de Dados Abertos (dados.gov.br), carrega o dado bruto no MongoDB Atlas, transforma com pandas e salva o resultado final no PostgreSQL do NeonDB.

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
https://dadosabertos.bndes.gov.br/dataset/cf41fb63-4496-43cb-a043-08998291c858/resource/ed69dbee-4eda-4831-9492-d41ea27ba8d9/download/mobilidade-fichas-projetos.csv
```

O pipeline filtra os dados para a região metropolitana do **Recife**, foco do projeto.
O endereço atual do arquivo não fica fixo no código: o pipeline consulta os
metadados do conjunto pela API oficial do dados.gov.br e utiliza o link do
recurso retornado pela API.

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
Load.load_neon  ->  NeonDB/PostgreSQL (tabela final)
```

Se o download direto da API falhar, o `run_etl.py` usa automaticamente o CSV salvo em `data/mobilidade-fichas-projetos.csv`.

## Instalação

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Linux / MacOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Configuração do `.env`

Crie um arquivo `.env` na raiz do projeto:

```
CHAVE_API_DADOS_ABERTOS="sua_chave_de_api_aqui"
MONGODB_URI="mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
NEON_DATABASE_URL="postgresql://usuario:senha@servidor.neon.tech/neondb?sslmode=require"
```

Não versione o `.env` (ele já está no `.gitignore`). O arquivo
`.env.example` serve como modelo e não contém credenciais reais.

## Configuração do NeonDB

1. Crie uma conta e um projeto em [neon.tech](https://neon.tech/).
2. No painel do projeto, clique em **Connect**.
3. Copie a connection string PostgreSQL e salve-a em `NEON_DATABASE_URL`.

Uma chave da API administrativa do Neon não é necessária. O pipeline usa
diretamente a connection string PostgreSQL. A tabela final é criada
automaticamente durante a carga.

## Rodando o pipeline

### Windows

```powershell
python run_etl.py
```

### Linux / WSL

```bash
source .venv/bin/activate
python run_etl.py
```

Se o comando `python` não estiver disponível, use:

```bash
source .venv/bin/activate
python3 run_etl.py
```

Isso grava os dados brutos na coleção `MOBILIDADE_FICHAS_PROJETOS` (banco `SMART_CITY`) no MongoDB Atlas, recupera e transforma os registros da RM Recife e salva o resultado na tabela `mobilidade_fichas_projetos` do NeonDB. Ao final, o programa consulta a tabela no Neon para confirmar a quantidade persistida.

> **Atenção:** cada execução substitui o conteúdo da coleção bruta
> no MongoDB e da tabela final no NeonDB.

## Executando os testes

### Windows

```powershell
python -m unittest discover -s tests -v
```

### Linux / WSL

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

Se o comando `python` não estiver disponível, use:

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -v
```

Os testes verificam o filtro regional, a preservação dos códigos de projeto
alfanuméricos e a validação básica da URL do Neon.

## Estrutura dos arquivos

```
etl-smart-city/
├── .env                          # credenciais locais (não versionado)
├── .env.example                  # modelo das variáveis de ambiente
├── data/
│   └── mobilidade-fichas-projetos.csv   # CSV local (fallback)
├── src/
│   ├── extract.py                # Extract: API + CSV local + leitura do MongoDB
│   ├── transform.py              # Transform: limpeza e organização em DataFrame
│   └── load.py                   # Load: persistência no MongoDB e no NeonDB
├── tests/                         # testes automatizados
├── run_etl.py                    # Orquestra o pipeline completo
├── requirements.txt
└── README.md
```
