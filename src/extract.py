import csv
import io
import os
from typing import Any, Dict, List

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import requests

load_dotenv()


class Extract:
    """
    Responsável por extrair os dados públicos de mobilidade urbana
    utilizados no projeto Smart City.
    """

    # Configurações da fonte de dados
    DADOS_GOV_BR_BASE_URL = "https://dados.gov.br"
    API_KEY_ENV = "CHAVE_API_DADOS_ABERTOS"

    # Configurações do MongoDB
    MONGODB_URI_ENV = "MONGODB_URI"
    MONGO_DB = "SMART_CITY"
    MONGO_COLLECTION = "MOBILIDADE_FICHAS_PROJETOS"

    # Recursos disponíveis para extração
    RECURSOS_CSV = {
        "mobilidade_fichas_projetos": {
            "dataset_id": "cf41fb63-4496-43cb-a043-08998291c858",
            "resource_id": "ed69dbee-4eda-4831-9492-d41ea27ba8d9",
            "arquivo": "mobilidade-fichas-projetos.csv",
            "delimitador": ";",
            "encoding": "cp1252",
        },
    }

    # Regiões metropolitanas disponíveis no dataset
    REGIOES_METROPOLITANAS = {
        "RIDE Distrito Federal": "RIDEDF",
        "RIDE Teresina": "RIDEGT",
        "RM Baixada Santista": "RMBS",
        "RM Belo Horizonte": "RMBH",
        "RM Belém": "RMB",
        "RM Campinas": "RMC",
        "RM Curitiba": "RMC",
        "RM Florianópolis": "RMF",
        "RM Fortaleza": "RMF",
        "RM Goiânia": "RMG",
        "RM Grande Vitória": "RMGV",
        "RM João Pessoa": "RMJP",
        "RM Maceió": "RMM",
        "RM Manaus": "RMM",
        "RM Natal": "RMN",
        "RM Porto Alegre": "RMPA",
        "RM Recife": "RMR",
        "RM Rio de Janeiro": "RMRJ",
        "RM Salvador": "RMS",
        "RM São Luís": "RMGSL",
        "RM São Paulo": "RMSP",
    }

    def __init__(self) -> None:
        """
        Inicializa o extrator, configura a chave de API (opcional) e a
        conexão com o MongoDB.
        """

        self.dados_gov_br_base_url = self.DADOS_GOV_BR_BASE_URL
        self.mongodb_uri_env = self.MONGODB_URI_ENV
        self.mongo_db = self.MONGO_DB
        self.mongo_collection = self.MONGO_COLLECTION

        self.api_key = os.getenv(self.API_KEY_ENV, "")
        if not self.api_key:
            print(
                f"Aviso: {self.API_KEY_ENV} não foi definida no .env. "
                "O download do CSV pela API pode falhar; nesse caso, use "
                "carregar_mobilidade_fichas_projetos_local com o arquivo "
                "baixado manualmente."
            )

        self.headers = {
            "accept": "application/json",
            "chave-api-dados-abertos": self.api_key,
        }

        self.mongo_uri = os.getenv(self.mongodb_uri_env)

        if not self.mongo_uri:
            raise ValueError(f"Variável {self.mongodb_uri_env} não encontrada no .env.")

        self.client = MongoClient(
            self.mongo_uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )

    def close(self) -> None:
        """Encerra a conexão com o MongoDB."""
        self.client.close()

    def baixar_recurso_csv(
        self,
        recurso: str,
    ) -> List[Dict[str, Any]]:
        """
        Baixa um recurso CSV diretamente do portal dados.gov.br.

        Parâmetros:
            recurso: nome do recurso disponível em RECURSOS_CSV.

        Retorno:
            Lista de dicionários contendo os registros extraídos.
        """

        if recurso not in self.RECURSOS_CSV:
            raise ValueError(
                f"Recurso CSV inválido: {recurso!r}. "
                f"Opções disponíveis: {list(self.RECURSOS_CSV)}"
            )

        info = self.RECURSOS_CSV[recurso]

        url = (
            f"{self.dados_gov_br_base_url}/dataset/"
            f"{info['dataset_id']}/resource/"
            f"{info['resource_id']}/download/"
            f"{info['arquivo']}"
        )

        response = requests.get(url, headers=self.headers, timeout=60)
        response.raise_for_status()

        conteudo = response.content.decode(info["encoding"])

        leitor = csv.DictReader(
            io.StringIO(conteudo),
            delimiter=info["delimitador"],
        )

        linhas = [dict(linha) for linha in leitor]

        print("Dados extraídos com sucesso do dados.gov.br!")
        print(f"Recurso: {recurso}")
        print(f"Total de registros extraídos: {len(linhas)}")

        return linhas

    def baixar_mobilidade_fichas_projetos(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Baixa as fichas de projetos de mobilidade urbana do dados.gov.br.

        Retorno:
            Lista de dicionários com os projetos de mobilidade.
        """

        return self.baixar_recurso_csv("mobilidade_fichas_projetos")

    def carregar_csv_local(
        self,
        recurso: str,
        caminho_arquivo: str,
    ) -> List[Dict[str, Any]]:
        """
        Lê, de um arquivo já baixado no disco, o mesmo recurso CSV de
        `baixar_recurso_csv`. Serve como alternativa quando o download
        direto do dados.gov.br não está disponível, reaproveitando a
        mesma configuração de delimitador e encoding de RECURSOS_CSV.

        Parâmetros:
            recurso: nome do recurso disponível em RECURSOS_CSV.
            caminho_arquivo: caminho local do arquivo CSV já baixado.

        Retorno:
            Lista de dicionários contendo os registros lidos do arquivo.
        """

        if recurso not in self.RECURSOS_CSV:
            raise ValueError(
                f"Recurso CSV inválido: {recurso!r}. "
                f"Opções disponíveis: {list(self.RECURSOS_CSV)}"
            )

        info = self.RECURSOS_CSV[recurso]

        with open(
            caminho_arquivo,
            "r",
            encoding=info["encoding"],
            newline="",
        ) as arquivo:
            leitor = csv.DictReader(
                arquivo,
                delimiter=info["delimitador"],
            )
            linhas = [dict(linha) for linha in leitor]

        print(f"Dados carregados com sucesso do arquivo local '{caminho_arquivo}'!")
        print(f"Total de registros carregados: {len(linhas)}")

        return linhas

    def carregar_mobilidade_fichas_projetos_local(
        self,
        caminho_arquivo: str,
    ) -> List[Dict[str, Any]]:
        """
        Atalho para carregar as fichas de mobilidade a partir de um
        arquivo local, quando o download direto não está disponível.

        Parâmetros:
            caminho_arquivo: caminho do CSV baixado manualmente do
                dados.gov.br.

        Retorno:
            Lista de dicionários com os projetos de mobilidade.
        """

        return self.carregar_csv_local(
            "mobilidade_fichas_projetos",
            caminho_arquivo,
        )

    def filtrar_por_regiao_metropolitana(
        self,
        dados: List[Dict[str, Any]],
        regiao_metropolitana: str,
    ) -> List[Dict[str, Any]]:
        """
        Filtra os projetos pertencentes a uma região metropolitana.

        Parâmetros:
            dados: registros brutos extraídos.
            regiao_metropolitana: região que será utilizada no filtro.

        Retorno:
            Lista contendo somente os registros da região informada.
        """

        if regiao_metropolitana not in self.REGIOES_METROPOLITANAS:
            raise ValueError(
                f"Região metropolitana inválida: "
                f"{regiao_metropolitana!r}. "
                f"Opções disponíveis: "
                f"{list(self.REGIOES_METROPOLITANAS)}"
            )

        dados_filtrados = [
            linha for linha in dados if linha.get("rm") == regiao_metropolitana
        ]

        print(f"Região selecionada: {regiao_metropolitana}")
        print("Registros encontrados para a região: " f"{len(dados_filtrados)}")

        return dados_filtrados

    def extract_collection_from_mongo(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Recupera os dados brutos armazenados no MongoDB.

        Retorno:
            Lista de documentos armazenados na coleção.
        """

        collection = self.client[self.mongo_db][self.mongo_collection]

        documentos = list(collection.find())

        print(f"Dados lidos com sucesso da coleção " f"'{self.mongo_collection}'!")
        print("Total de documentos recuperados: " f"{len(documentos)}")

        return documentos
