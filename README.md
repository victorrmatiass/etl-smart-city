# Smart City - ETL de Dados Abertos

Componente de ETL do projeto **Smart City - Plataforma de Gestão de Demandas Urbanas**. Extrai os atendimentos da Central 156 da EMLURB (Portal de Dados Abertos do Recife, 2026), carrega o dado bruto no MongoDB Atlas, transforma com pandas e salva o resultado final no SQLite (local) e no PostgreSQL do NeonDB.

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

Conjunto de dados **Central de Atendimento de Serviços da EMLURB - 156**, recurso de **2026**, do Portal de Dados Abertos da Prefeitura do Recife (licença ODbL):

```
https://dados.recife.pe.gov.br/dataset/central-de-atendimento-de-servicos-da-emlurb-156/resource/80c5b3cd-d4f7-466e-9031-e636ef56dd99
```

Cada linha é uma demanda registrada pelo cidadão (buraco, lâmpada apagada, poda, capina etc.). O pipeline consulta a API de datastore do CKAN, que dispensa chave de API. Se ela falhar, baixa o CSV e, por último, usa o arquivo local `data/156_cco_diario_2026.csv`.

Para usar outro ano, troque `RESOURCE_ID`, `PACKAGE_ID` e `NOME_ARQUIVO_CSV` em `src/extract.py` e `ANO_ALVO` em `src/transform.py`.

### Campos originais (13)

`GRUPOSERVICO_CODIGO`, `GRUPOSERVICO_DESCRICAO`, `SERVICO_CODIGO`, `SERVICO_DESCRICAO`, `LOGRADOURO`, `NUMERO`, `BAIRRO`, `RPA`, `DATA_DEMANDA`, `SITUACAO`, `DATA_ULT_SITUACAO`, `latitude`, `longitude`.

### Tabelas geradas (SQLite e NeonDB)

**`emlurb_156_demandas`** (uma linha por demanda, chave primária `id_demanda`):

| Campo | Descrição |
| --- | --- |
| `id_demanda` | ID determinístico (hash de serviço + endereço + data + coordenadas); não muda quando a situação muda |
| `grupo_servico_codigo`, `grupo_servico`, `servico_codigo`, `servico` | Tipo de demanda |
| `logradouro`, `numero`, `bairro`, `rpa` | Localização (RPA de 1 a 6) |
| `latitude`, `longitude`, `tem_coordenadas` | Coordenadas validadas dentro de Recife; inválidas viram nulas |
| `data_demanda`, `ano`, `mes`, `ano_mes`, `dia_semana`, `hora` | Campos de tempo para filtros e gráficos |
| `situacao`, `situacao_categoria`, `concluida` | Situação original e categoria (Concluída, Em andamento, Cancelada, Outros) |
| `data_ultima_situacao`, `tempo_resolucao_dias` | Tempo até a conclusão (só para demandas concluídas) |

**`emlurb_156_agregado_mensal`**: total de demandas e tempo médio de resolução por `ano_mes`, `rpa`, `bairro`, `grupo_servico` e `situacao_categoria`. É leve para alimentar o dashboard do app mobile sem trazer todas as demandas.

### Regras de transformação

- Nomes de colunas padronizados em minúsculas; textos sem espaços extras; "NULL"/"NÃO INFORMADO"/vazio viram nulo.
- Textos todo em MAIÚSCULAS passam para caixa de título ("RUA DO FUTURO" vira "Rua do Futuro").
- Datas aceitam formato ISO e brasileiro; só ficam demandas de 2026.
- Coordenadas com vírgula decimal são convertidas; latitude/longitude trocadas são corrigidas; fora de Recife viram nulas.
- Duplicatas removidas pelo `id_demanda`.
- A categoria da situação é definida por palavras-chave em `Transform.CATEGORIAS_SITUACAO`. Ao rodar, o pipeline imprime cada situação encontrada e a categoria atribuída; ajuste a lista se algo cair em "Outros".

## Como funciona

```
API do portal (CKAN)  ->  CSV online  ->  CSV local em data/   (fallbacks, nessa ordem)
        |
        v
   Extract (baixa os atendimentos)
        |
        v
Load.load_mongo  ->  MongoDB (coleção bruta EMLURB_156_DEMANDAS_2026)
        |
        v
Extract.extract_collection_from_mongo (relê o bruto)
        |
        v
   Transform (limpeza, validação, campos derivados, agregação)
        |
        +--> Load.load_sqlite  ->  data/db/smart_city.db
        |
        +--> Load.load_neon    ->  NeonDB/PostgreSQL
```

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

### Gerar só o banco SQLite (sem MongoDB nem Neon)

Para criar `data/db/smart_city.db` sem precisar de credenciais no `.env`:

```bash
python run_etl.py --somente-sqlite
```

Depois é só abrir o arquivo no VS Code (por exemplo, com a extensão SQLite Viewer).

### Filtrar por RPA

A extração aceita uma das 6 RPAs do Recife (1 Centro, 2 Norte, 3 Noroeste, 4 Oeste, 5 Sudoeste, 6 Sul). Qualquer outro valor é rejeitado:

```bash
python run_etl.py --rpa 6
python run_etl.py --somente-sqlite --rpa 6
```

Isso grava os dados brutos na coleção `EMLURB_156_DEMANDAS_2026` (banco `SMART_CITY`) no MongoDB Atlas, transforma os registros e salva as tabelas `emlurb_156_demandas` e `emlurb_156_agregado_mensal` no SQLite (`data/db/smart_city.db`, para abrir no VS Code) e no NeonDB. Ao final, o programa consulta as tabelas para confirmar a quantidade persistida.

> **Atenção:** cada execução substitui o conteúdo da coleção bruta
> no MongoDB e das tabelas finais no SQLite e no NeonDB.

## Executando os testes

### Windows

```powershell
python -m unittest discover -s tests -t . -v
```

### Linux / WSL

```bash
source .venv/bin/activate
python -m unittest discover -s tests -t . -v
```

Se o comando `python` não estiver disponível, use:

```bash
source .venv/bin/activate
python3 -m unittest discover -s tests -t . -v
```

Os testes verificam a paginação da API, a leitura do CSV (encoding e delimitador),
a limpeza dos dados (datas, coordenadas, nulos, duplicatas, categorias de situação),
a agregação, a gravação no SQLite e a validação básica da URL do Neon.

## Estrutura dos arquivos

```
etl-smart-city/
├── .env                          # credenciais locais (não versionado)
├── .env.example                  # modelo das variáveis de ambiente
├── data/
│   ├── 156_cco_diario_2026.csv   # CSV local (fallback, opcional)
│   └── db/smart_city.db          # SQLite gerado pelo ETL (não versionado)
├── src/
│   ├── extract.py                # Extract: API CKAN + CSV + CSV local + leitura do MongoDB
│   ├── transform.py              # Transform: limpeza, campos derivados e agregação
│   └── load.py                   # Load: persistência no MongoDB, SQLite e NeonDB
├── tests/                         # testes automatizados
├── run_etl.py                    # Orquestra o pipeline completo
├── requirements.txt
└── README.md
```
