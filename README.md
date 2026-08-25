# Smart City - ETL de Dados Abertos

Este repositório contém um componente de **ETL** do projeto Smart City - Plataforma de Gestão de Demandas Urbanas. O objetivo deste componente é buscar dados públicos que possam apoiar análises e funcionalidades relacionadas à gestão urbana, como mobilidade, infraestrutura, meio ambiente e serviços públicos.

Ele será utilizado em conjunto com o projeto principal do Smart City. Não é o aplicativo mobile nem o backend da plataforma: é um serviço de ingestão de dados que poderá ser executado pelo pipeline do projeto existente.

## Escopo atual

Nesta primeira etapa, o foco está exclusivamente na camada **Extract**:

- Consumo da API do Portal de Dados Abertos (`dados.gov.br`)
- Métodos tipados para consultar conjuntos de dados, organizações, temas, tags e outros recursos públicos
- Menu interativo para testar as consultas manualmente

A camada **Load** ainda não faz parte desta versão. Ela será implementada posteriormente para persistir os dados no destino definido pelo projeto Smart City, como MongoDB ou arquivos locais.

## Integrantes do grupo

1. André Felipe da Silva Braga - afsb@cesar.school
2. Dayvid Cristiano - dcvs2@cesar.school
3. Deyvison Conrado - dmc2@cesar.school
4. Jennifer Cristine - jclc2@cesar.school
5. Letícia Gabriella - lgcs@cesar.school
6. Levi Moraes - lmma@cesar.school
7. Luis Henrique Facunde da Silva - lhfs@cesar.school
8. Manuele Macêdo - mmps2@cesar.school
9. Maria Aparecida - maers@cesar.school
10. Peterson Jesus Feitosa de Melo - pjfm@cesar.school
11. Rhaldney Robert - rrcd@cesar.school
12. Victor César Matias da Silva - vcms@cesar.school

---

## Como funciona

A classe `Extract`, localizada em `src/extract.py`, centraliza as requisições à API e retorna os dados em JSON. O menu em `menu_api.py` existe apenas como apoio para desenvolvimento e demonstração; ele permite que a equipe teste os endpoints antes de integrá-los ao pipeline principal.

O fluxo atual é:

```text
Portal de Dados Abertos
       |
       v
    Extract (API)
       |
       v
   Dados em JSON
```

O `Load` será acrescentado entre a extração e o armazenamento definitivo quando a integração com o projeto principal estiver definida.

## Requisitos

- Python 3.10 ou superior
- Uma chave de acesso da API do Portal de Dados Abertos

## Instalação

1. Crie e ative um ambiente virtual:

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Instale as dependências:

   ```powershell
   python -m pip install -r requirements.txt
   ```

## Configuração do `.env`

O arquivo `.env` guarda configurações do projeto, como a chave de acesso da API, fora do código-fonte. A biblioteca `python-dotenv` carrega automaticamente essas variáveis quando o programa é iniciado.

Na raiz do projeto, crie um arquivo chamado `.env` com o seguinte conteúdo:

```env
CHAVE_API_DADOS_ABERTOS=sua_chave_de_api_aqui
```

Substitua `sua_chave_de_api_aqui` pela chave real fornecida pelo Portal de Dados Abertos.

Por segurança:

- Não coloque a chave diretamente no código Python.
- Não compartilhe o arquivo `.env`.
- Não versione o `.env` em repositórios públicos.

Se a variável não existir, o programa exibirá uma mensagem informando que a chave não foi encontrada. A chave é usada no header das requisições feitas pela classe `Extract`.

## Uso da classe `Extract`

Depois de configurar o `.env`, a classe pode ser utilizada pelo pipeline do projeto Smart City:

```python
from src.extract import Extract

extrator = Extract()
dados = extrator.listar_organizacoes(pagina=1)
```

Também é possível informar a chave diretamente, embora o uso do `.env` seja recomendado:

```python
extrator = Extract(api_key="sua_chave_de_api")
```

Os métodos de extração realizam requisições HTTP e usam `raise_for_status()` para interromper o fluxo quando a API retorna um erro.

## Executando o menu de testes

Com o ambiente virtual ativado, execute:

```powershell
python menu_api.py
```

Também é possível executar diretamente pelo interpretador do ambiente virtual:

```powershell
.\venv\Scripts\python.exe menu_api.py
```

O menu permanece em loop até que a opção `0. Sair` seja escolhida. Ele permite consultar:

- Conjuntos de dados
- Tags e formatos
- Observância legal e ODS
- Solicitações
- Reúsos
- Temas
- Organizações

As respostas da API são exibidas em formato JSON no terminal. Esse menu não substitui a execução do pipeline principal; ele serve para validar consultas e visualizar o formato dos dados retornados.

## Estrutura dos arquivos

```text
ETL - Projeto/
├── .env                         # Configurações locais e chave da API
├── menu_api.py                  # Menu interativo para testar a extração
├── src/
│   └── extract.py               # Classe Extract e métodos de extração
├── requirements.txt             # Dependências do projeto
└── README.md                    # Documentação
```

## Integração com o projeto Smart City

Este repositório deve ser tratado como uma fonte de dados do projeto Smart City. O código responsável por executar o pipeline poderá importar a classe `Extract`, selecionar os métodos necessários e encaminhar o resultado para a futura camada `Load`.

Exemplo de integração futura:

```python
from src.extract import Extract
from src.load import Load

extrator = Extract()
dados = extrator.listar_conjuntos_de_dados(pagina=1)

carregador = Load()
carregador.load_json(dados)
```

O exemplo acima representa a próxima etapa do projeto. O módulo `src.load` ainda não está implementado neste repositório.

## Dependências

As dependências estão listadas em `requirements.txt`. Para atualizar esse arquivo depois de instalar ou remover pacotes do ambiente virtual, execute:

```powershell
python -m pip freeze > requirements.txt
```
