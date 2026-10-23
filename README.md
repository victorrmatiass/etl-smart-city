# Smart City - ETL de Dados Abertos

**Recife em demandas**: pipeline e dashboard para explorar as solicitações da Central 156 da EMLURB por bairro, RPA, grupo de serviço e situação. O painel é um retrato histórico dos registros disponíveis; não é um censo oficial nem um acompanhamento em tempo real.

**Repositório:** https://github.com/victorrmatiass/etl-smart-city

![Dashboard conectado ao Neon](docs/dashboard.png)

Fluxo: **API CKAN → MongoDB Atlas (bronze histórico) → transformação → NeonDB → Streamlit**. O SQLite permanece como saída local auxiliar.

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

Cada linha é um registro de solicitação de serviço urbano (iluminação, limpeza, drenagem, arborização etc.). **EMLURB é a origem temática dos atendimentos; EMPREL está associada ao portal municipal.** O pipeline consulta a API pública `datastore_search`, pagina todos os resultados com ordenação `_id asc` e verifica o total anunciado. Se ela falhar, tenta CSV online e depois `data/156_cco_diario_2026.csv`, se disponível. A origem efetivamente usada fica registrada em cada carga. Usar um fallback não comprova a etapa de API na apresentação.

O recurso se chama **2026**, mas o perfil consultado em **23/10/2026** contém **11.374 registros**, com `DATA_ULT_SITUACAO` entre **01 e 30/01/2026** e aberturas entre **19/05/2009 e 30/01/2026**. São 8.301 abertos em 2026 e 3.073 em anos anteriores. O nome do arquivo não deve ser usado para descartar esses registros. O painel calcula o período a partir dos dados, sem fixá-lo no código.

Essa base sustenta a ideia do grupo de um “Censo de Demandas do Recife”, entendido aqui como **retrato dos atendimentos publicados**. Não permite inferir todas as necessidades da cidade, taxa por habitante ou pendências atuais. O portal informa atualização do recurso em junho de 2026; isso não altera as datas internas de janeiro. Não foi presumida aprovação do professor para essa abordagem histórica.

Para trocar o recurso, ajuste `RESOURCE_ID`, `PACKAGE_ID` e `NOME_ARQUIVO_CSV` em `src/config.py` e confira o contrato de colunas da fonte.

### Campos originais (13)

`GRUPOSERVICO_CODIGO`, `GRUPOSERVICO_DESCRICAO`, `SERVICO_CODIGO`, `SERVICO_DESCRICAO`, `LOGRADOURO`, `NUMERO`, `BAIRRO`, `RPA`, `DATA_DEMANDA`, `SITUACAO`, `DATA_ULT_SITUACAO`, `latitude`, `longitude`.

### Tabelas geradas (SQLite e NeonDB)

**`emlurb_156_demandas`** (uma linha por demanda, chave primária `id_demanda`):

| Campo | Descrição |
| --- | --- |
| `id_demanda`, `id_origem` | ID de linha CKAN, com sufixo de ocorrência para unicidade; no CSV usa hash + ocorrência. Não é protocolo oficial e não elimina linhas |
| `data_extracao`, `carga_id`, `origem_extracao` | Data UTC, identificação do lote e canal usado (API, CSV online ou local) |
| `grupo_servico_codigo`, `grupo_servico`, `servico_codigo`, `servico` | Tipo de demanda |
| `logradouro`, `numero`, `bairro`, `rpa` | Localização (RPA de 1 a 6) |
| `latitude`, `longitude`, `tem_coordenadas` | Coordenadas validadas dentro de Recife; inválidas viram nulas |
| `data_demanda`, `ano`, `mes`, `ano_mes`, `dia_semana`, `hora` | Campos de tempo para filtros e gráficos |
| `situacao`, `situacao_categoria`, `concluida` | Situação original e categoria (Concluída, Em andamento, Cancelada, Outros) |
| `data_ultima_situacao`, `tempo_resolucao_dias` | Tempo até a conclusão (só para demandas concluídas) |

**`emlurb_156_agregado_mensal`**: total e tempo médio por mês de **abertura**, RPA, bairro, grupo e situação. Categorias ausentes permanecem nulas e entram no agrupamento (`dropna=False`). A soma da coluna `total` precisa ser igual à quantidade de linhas da tabela detalhada. O dashboard lê a detalhada para permitir filtros combinados.

**`emlurb_156_auditoria`**: contagens bronze/transformação/destino/agregado, ausências, hashes repetidos preservados, carimbo e origem da carga. É gravada na mesma transação que as tabelas finais.

### Regras de transformação

- Nomes padronizados em minúsculas; textos sem espaços extras; vazio, `NULL`, `NONE`, `NAN`, `NA`, `N/A`, `-`, `...` e `NÃO INFORMADO` viram nulo. Nenhum preenchimento por zero é aplicado a ausência.
- Textos todo em MAIÚSCULAS passam para caixa de título ("RUA DO FUTURO" vira "Rua do Futuro").
- Datas aceitam formato ISO e brasileiro; data inválida vira nulo e a linha permanece. Anos anteriores a 2026 são preservados.
- Coordenadas com vírgula decimal são convertidas; latitude/longitude trocadas são corrigidas; fora de Recife viram nulas.
- Nenhuma linha é eliminada por coincidência de hash. O hash antigo se repetia em 154 registros da amostra; isso não prova duplicidade de atendimento. O ID CKAN é preservado como `id_origem` e os sufixos de ocorrência garantem unicidade sem perdas.
- A categoria da situação é definida por palavras-chave em `Transform.CATEGORIAS_SITUACAO`. Ao rodar, o pipeline imprime cada situação encontrada e a categoria atribuída; ajuste a lista se algo cair em "Outros".

Na fonte consultada: `ATENDIDA` (7.662) é concluída; `EXECUCAO` (1.439), `CADASTRADA` (1.333), `PREPARACAO` (722), `PENDENCIA` (208) e `FISCALIZACAO` (10) entram em andamento. Situação ausente mantém `situacao_categoria` e `concluida` nulos. Desconhecidas entram em Outros. A taxa de atendimento do recorte inteiro é **67,4%**, sem inferência de SLA.

### Adequações da Aula 08

| Requisito | Aplicação neste projeto |
| --- | --- |
| `.env` lido uma vez | Apenas `src/config.py` usa `load_dotenv` e `os.getenv`; Extract, Load, executores e dashboard compartilham essa configuração. As credenciais são validadas quando o recurso é utilizado, permitindo testes locais sem banco |
| Todas as linhas da fonte | Todas as páginas CKAN são concatenadas; interrupção prematura ou contagem divergente causa erro. Transform percorre o DataFrame inteiro e preserva as 13 colunas de negócio, além de campos novos |
| Revisão de índices fixos | Não há acesso `[0]` a uma lista de resultados no Transform. O `[0]` de `splitlines()` em Extract lê apenas o cabeçalho para detectar delimitador; as linhas do CSV são percorridas por completo. As perdas reais eram filtro de ano/data/serviço e deduplicação por hash, agora removidos |
| Ausências | A API devolveu `null` em latitude e longitude de 5.289 registros; outros dois pares ficaram fora da caixa geográfica validada, totalizando 5.291 sem coordenadas válidas. Todos continuam nos totais. Os demais marcadores são aceitos defensivamente, mas não foram observados nesta consulta |
| Bronze histórico | Cada lote recebe `data_extracao` UTC, `carga_id` e `origem_extracao`; não há `delete_many`. Documentos anteriores sem carimbo ficam preservados |
| Última carga | `extract_latest_from_mongo()` seleciona o último lote **completo**. Um manifesto em `EMLURB_156_DEMANDAS_2026_CARGAS` só é criado após inserção e conferência. Lotes interrompidos não são promovidos. Os executores passam o ID do lote recém-gravado para não misturar execuções concorrentes |
| Reconciliação | Fonte = lote bronze = tabela detalhada = soma do agregado. A gravação SQL confere os totais antes de confirmar a transação e publica a auditoria |

`NUMERO=0`/`00` é normalizado como `S/N` (rótulo textual de endereço, não medição). Coordenadas 0/0 são inválidas para Recife e viram nulas; zero não é tratado globalmente como ausência. `tempo_resolucao_dias` fica nulo para não concluídas, datas ausentes ou inválidas. Os valores originais continuam disponíveis no bronze para auditoria.

## Como funciona

```
API do portal (CKAN)  ->  CSV online  ->  CSV local em data/   (fallbacks, nessa ordem)
        |
        v
   Extract (baixa os atendimentos)
        |
        v
Load.load_mongo  ->  MongoDB (novo lote, sem apagar o histórico)
        |
        v
Extract.extract_latest_from_mongo (relê somente o lote completo)
        |
        v
   Transform (limpeza, validação, campos derivados, agregação)
        |
        +--> Load.load_sqlite  ->  data/db/smart_city.db
        |
        +--> Load.load_neon    ->  NeonDB/PostgreSQL -> dashboard/app.py
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

## Dashboard: Recife em demandas

Depois de configurar as conexões e executar o pipeline, rode **a partir da raiz**:

```powershell
python -m streamlit run dashboard/app.py
```

Abra http://localhost:8501. No Windows, sem ativar o ambiente, use `.\.venv\Scripts\python.exe -m streamlit run dashboard/app.py`.

- **Filtros combináveis:** RPA, bairro, grupo de serviço, situação original, ano de abertura e período da última situação. Seleção vazia nos multiselects significa “todos”.
- **Indicadores:** total de solicitações, percentual atendido, registros em andamento no recorte e bairros representados.
- **Panorama:** distribuição por situação, cinco grupos mais demandados, demandas por RPA e oito bairros com maior volume.
- **Território e serviços:** cruzamento bairro × grupo, andamento por bairro e ano de abertura.
- **Dados e metodologia:** auditoria da carga, limitações, tabela filtrada e download CSV. Ausências recebem rótulo só na exibição.

Todos os indicadores/gráficos usam a mesma seleção; a auditoria identifica explicitamente a carga inteira. Nenhuma combinação correspondente mostra um estado vazio. A consulta é **direta ao Neon**, com cache de dez minutos; não consulta API/MongoDB nem inventa dados se a conexão falhar. O botão “Atualizar leitura do Neon” limpa o cache, sem executar a ETL.

Os volumes refletem uso do canal 156 e cobertura da publicação, não população ou qualidade do serviço por região. O painel não inclui mapa: 46,5% dos registros do recorte não têm coordenadas válidas. A ausência de informação geográfica não reduz os totais dos gráficos.

### Entrega

1. Execute `python run_etl.py` para publicar uma carga atual no Neon.
2. Inicie o Streamlit e confira a aba **Dados e metodologia**.
3. O print da execução validada está em [`docs/dashboard.png`](docs/dashboard.png).
4. Faça commit e push do código, README e print, e envie o [link do repositório](https://github.com/victorrmatiass/etl-smart-city). O `.env` não deve ser versionado.

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

### Executar com Prefect

O arquivo `orchestration_prefect.py` organiza a extração, a carga bruta no
MongoDB, a transformação e as cargas no SQLite e no NeonDB em tarefas Prefect.
Ele reutiliza as classes e os fallbacks do ETL atual. Instale as dependências
do projeto e execute, por exemplo:

```powershell
python -m pip install -r requirements.txt
python orchestration_prefect.py --somente-sqlite
```

As opções `--somente-sqlite` e `--rpa` têm o mesmo comportamento descrito acima.
No modo SQLite-only, as etapas do MongoDB e do NeonDB são ignoradas.

Isso grava os dados brutos na coleção `EMLURB_156_DEMANDAS_2026` (banco `SMART_CITY`) no MongoDB Atlas, transforma os registros e salva as tabelas `emlurb_156_demandas` e `emlurb_156_agregado_mensal` no SQLite (`data/db/smart_city.db`, para abrir no VS Code) e no NeonDB. Ao final, o programa consulta as tabelas para confirmar a quantidade persistida.

O MongoDB **acumula cargas históricas**. Apenas as tabelas derivadas EMLURB (detalhada, agregada e auditoria) são substituídas no SQLite e Neon, de forma transacional. Tabelas de outros projetos não são modificadas. As cargas parciais no bronze permanecem para diagnóstico, sem manifesto de conclusão. Não há política automática de retenção; o armazenamento cresce por execução.

O modo `--somente-sqlite` é auxiliar e não cumpre o fluxo obrigatório com os dois bancos. O parâmetro `--rpa` faz um recorte intencional na fonte; para a entrega e para comparar toda a cidade, execute sem ele. Não execute cargas com recortes distintos simultaneamente contra o mesmo destino: a última publicação SQL será a exibida no painel.

### Conferência de registros

No SQL Editor do Neon:

```sql
SELECT * FROM emlurb_156_auditoria;
SELECT COUNT(*) AS linhas_finais FROM emlurb_156_demandas;
SELECT SUM(total) AS linhas_representadas FROM emlurb_156_agregado_mensal;
SELECT situacao, COUNT(*) FROM emlurb_156_demandas GROUP BY situacao ORDER BY COUNT(*) DESC;
```

No Atlas, filtre `EMLURB_156_DEMANDAS_2026` pelo `carga_id` apresentado pela auditoria. Compare a quantidade **desse lote**, não o histórico inteiro, com a tabela final. Para ler todo o histórico programaticamente, `extract_collection_from_mongo()` continua disponível, mas não é chamado na transformação.

Validação em 23/10/2026: **11.374 linhas da API = 11.374 no lote bronze = 11.374 no Neon = soma 11.374 no agregado** (2.698 grupos). Os IDs de origem também foram reconciliados. O Mongo preservou os 11.374 documentos preexistentes e acrescentou o novo lote, totalizando 22.748 documentos naquele momento. O print usa essa carga real, não uma fixture.

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
a preservação de todas as linhas (inclusive antigas, incompletas e hashes repetidos),
nulos, categorias reais, carimbo de carga, seleção do lote completo, auditoria SQL,
agregação, filtros e denominadores do dashboard. Os testes locais usam fixtures,
SQLite temporário e mocks; não gravam nos bancos de nuvem.

Para verificar filtros, estado vazio e falha de conexão na interface com dados
de teste: `python scripts/check_dashboard.py`. Para reconciliar a carga efetiva
nos bancos configurados, somente com leituras: `python scripts/verify_pipeline.py`.

## Estrutura dos arquivos

```
etl-smart-city/
├── .env                          # credenciais locais (não versionado)
├── .env.example                  # modelo das variáveis de ambiente
├── data/
│   ├── 156_cco_diario_2026.csv   # CSV local (fallback, opcional)
│   └── db/smart_city.db          # SQLite gerado pelo ETL (não versionado)
├── src/
│   ├── config.py                 # configuração única e conexão Neon compartilhada
│   ├── extract.py                # Extract: API CKAN + CSV + CSV local + leitura do MongoDB
│   ├── transform.py              # Transform: limpeza, campos derivados e agregação
│   └── load.py                   # Load: persistência no MongoDB, SQLite e NeonDB
├── tests/                         # testes automatizados
├── dashboard/app.py              # Streamlit conectado diretamente ao Neon
├── dashboard/data.py             # consultas, filtros e indicadores
├── .streamlit/config.toml         # tema visual
├── docs/dashboard.png            # print para a entrega
├── scripts/inspect_source.py     # perfil da fonte pública (diagnóstico opcional)
├── run_etl.py                    # Orquestra o pipeline completo
├── orchestration_prefect.py      # Executa o pipeline atual como um flow Prefect
├── requirements.txt
└── README.md
```
