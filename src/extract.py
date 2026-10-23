import csv
import io
import json
import certifi
import requests
from pathlib import Path
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from typing import Any, Dict, List, Optional

from src import config


class Extract:
    """
    Responsável por extrair os atendimentos da Central 156 da EMLURB
    (Prefeitura do Recife), publicados no Portal de Dados Abertos do Recife.
    """

    # Conjunto fechado de opções da API: as 6 Regiões Político-Administrativas
    # (RPAs) do Recife. Chave = código da RPA; valor = nome da região.
    RPAS = {
        1: "Centro",
        2: "Norte",
        3: "Noroeste",
        4: "Oeste",
        5: "Sudoeste",
        6: "Sul",
    }

    def __init__(self, usar_mongo: bool = True) -> None:
        """
        Inicializa o extrator, os valores fixos da API e, opcionalmente,
        a conexão com o MongoDB.

        Parâmetros:
            usar_mongo: se False, não exige nem abre conexão com o MongoDB
                (modo "somente SQLite").
        """

        # Valores fixos da API (CKAN do Portal de Dados Abertos do Recife)
        self.ckan_base_url = config.CKAN_BASE_URL
        self.datastore_api = "/api/3/action/datastore_search"
        self.resource_id = config.RESOURCE_ID
        self.package_id = config.PACKAGE_ID
        self.nome_arquivo_csv = config.NOME_ARQUIVO_CSV
        self.origem = "desconhecida"
        self.total_fonte = None
        self.campo_rpa = "RPA"
        self.tamanho_pagina = 10_000
        self.timeout_segundos = 60

        # Configurações do MongoDB
        self.mongodb_uri_env = "MONGODB_URI"
        self.mongo_db = config.MONGO_DB
        self.mongo_collection = config.MONGO_COLLECTION

        self.client = None

        if not usar_mongo:
            return

        self.mongo_uri = config.MONGODB_URI

        if not self.mongo_uri:
            raise ValueError(f"Variável {self.mongodb_uri_env} não encontrada no .env.")

        self.client = MongoClient(
            self.mongo_uri,
            server_api=ServerApi("1"),
            tlsCAFile=certifi.where(),
        )

    def close(self) -> None:
        """Encerra a conexão com o MongoDB."""
        if self.client is not None:
            self.client.close()

    @property
    def url_csv(self) -> str:
        """URL pública de download do CSV de 2026."""

        return (
            f"{self.ckan_base_url}/dataset/{self.package_id}"
            f"/resource/{self.resource_id}/download/{self.nome_arquivo_csv}"
        )

    def _validar_rpa(self, rpa: Optional[int]) -> None:
        """
        Garante que a RPA informada existe em `RPAS`.

        Parâmetros:
            rpa: código da RPA (1 a 6) ou None para não filtrar.
        """

        if rpa is not None and rpa not in self.RPAS:
            raise ValueError(f"RPA inválida: {rpa!r}. Opções disponíveis: {self.RPAS}")

    def _filtrar_por_rpa(
        self,
        linhas: List[Dict[str, Any]],
        rpa: Optional[int],
    ) -> List[Dict[str, Any]]:
        """Filtra, em memória, as linhas de um CSV pela RPA (se informada)."""

        if rpa is None:
            return linhas

        chave = self.campo_rpa.lower()

        def mesma_rpa(linha: Dict[str, Any]) -> bool:
            valores = {str(k).lower(): v for k, v in linha.items()}
            try:
                return int(float(str(valores.get(chave, "")).replace(",", "."))) == rpa
            except ValueError:
                return False

        return [linha for linha in linhas if mesma_rpa(linha)]

    def baixar_demandas_api(self, rpa: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Baixa os atendimentos do 156 pela API de datastore do CKAN
        (requests.get + raise_for_status), paginando os resultados.

        Parâmetros:
            rpa: código da RPA (1 a 6, ver `RPAS`) para filtrar a consulta.
                Se None, traz todas as RPAs.

        Retorno:
            Lista de dicionários com os atendimentos do 156.
        """

        self._validar_rpa(rpa)

        url = f"{self.ckan_base_url}{self.datastore_api}"
        registros: List[Dict[str, Any]] = []
        offset = 0

        while True:
            parametros: Dict[str, Any] = {
                "resource_id": self.resource_id,
                "limit": self.tamanho_pagina,
                "offset": offset,
                "sort": "_id asc",
            }

            if rpa is not None:
                parametros["filters"] = json.dumps({self.campo_rpa: rpa})

            resposta = requests.get(
                url, params=parametros, timeout=self.timeout_segundos
            )
            resposta.raise_for_status()

            corpo = resposta.json()

            if not corpo.get("success"):
                raise requests.exceptions.RequestException(
                    f"A API do CKAN retornou erro: {corpo.get('error')}"
                )

            pagina = corpo["result"]["records"]
            total = corpo["result"].get("total")

            registros.extend(pagina)
            offset += len(pagina)

            if not pagina and total is not None and offset < total:
                raise requests.exceptions.RequestException(
                    "Paginação incompleta: API encerrou antes do total anunciado."
                )
            if not pagina or (total is not None and offset >= total):
                break

        if total is not None and len(registros) != total:
            raise requests.exceptions.RequestException(
                "Contagem extraída difere do total anunciado pela API."
            )

        # Preserva a identidade da linha CKAN sem conflitar com o _id do Mongo.
        for registro in registros:
            if "_id" in registro:
                registro["id_origem"] = registro.pop("_id")

        self.origem = "API CKAN"
        self.total_fonte = len(registros)

        print("Dados extraídos com sucesso da API do Portal de Dados do Recife!")
        print(f"Total de registros extraídos: {len(registros)}")

        return registros

    def baixar_demandas_csv(self, rpa: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Baixa o CSV completo diretamente do portal.

        Parâmetros:
            rpa: código da RPA (1 a 6, ver `RPAS`) para filtrar os registros.
                Se None, mantém todas as RPAs.

        Retorno:
            Lista de dicionários com os atendimentos do 156.
        """

        self._validar_rpa(rpa)

        resposta = requests.get(self.url_csv, timeout=self.timeout_segundos)
        resposta.raise_for_status()

        linhas = self._filtrar_por_rpa(self._ler_csv_bytes(resposta.content), rpa)
        self.origem = "CSV online"
        self.total_fonte = len(linhas)

        print("CSV baixado com sucesso do Portal de Dados do Recife!")
        print(f"Total de registros extraídos: {len(linhas)}")

        return linhas

    def carregar_demandas_local(
        self,
        caminho_arquivo: str,
        rpa: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Lê o CSV de um arquivo já baixado. Serve como alternativa quando
        o portal está fora do ar.

        Parâmetros:
            caminho_arquivo: caminho local do CSV do 156.
            rpa: código da RPA (1 a 6, ver `RPAS`) para filtrar os registros.
                Se None, mantém todas as RPAs.

        Retorno:
            Lista de dicionários com os atendimentos do 156.
        """

        self._validar_rpa(rpa)

        conteudo = Path(caminho_arquivo).read_bytes()
        linhas = self._filtrar_por_rpa(self._ler_csv_bytes(conteudo), rpa)
        self.origem = "CSV local"
        self.total_fonte = len(linhas)

        print(f"Dados carregados com sucesso do arquivo local '{caminho_arquivo}'!")
        print(f"Total de registros carregados: {len(linhas)}")

        return linhas

    @staticmethod
    def _ler_csv_bytes(conteudo: bytes) -> List[Dict[str, Any]]:
        """
        Converte os bytes de um CSV em lista de dicionários, detectando
        encoding (UTF-8 com/sem BOM ou cp1252) e delimitador (; , ou tab).
        """

        try:
            texto = conteudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            texto = conteudo.decode("cp1252")

        primeira_linha = texto.splitlines()[0] if texto else ""
        delimitador = max(";,\t", key=primeira_linha.count)

        leitor = csv.DictReader(io.StringIO(texto, newline=""), delimiter=delimitador)

        return [dict(linha) for linha in leitor]

    def extract_collection_from_mongo(self) -> List[Dict[str, Any]]:
        """
        Recupera os dados brutos armazenados no MongoDB.

        Retorno:
            Lista de documentos armazenados na coleção.
        """

        collection = self.client[self.mongo_db][self.mongo_collection]

        documentos = list(collection.find())

        print(f"Dados lidos com sucesso da coleção '{self.mongo_collection}'!")
        print(f"Total de documentos recuperados: {len(documentos)}")

        return documentos

    def extract_latest_from_mongo(self, carga_id=None) -> List[Dict[str, Any]]:
        """Lê só o lote completo mais recente (ou o lote desta execução).

        O manifesto só é inserido após todos os documentos: uma carga parcial
        nunca substitui uma completa. Documentos antigos sem carimbo permanecem.
        """
        db = self.client[self.mongo_db]
        filtro = {"carga_id": carga_id} if carga_id else {}
        carga = db[config.MONGO_CARGAS].find_one(filtro, sort=[("data_extracao", -1)])
        if carga is None:
            raise ValueError(
                "Nenhuma carga completa com data_extracao encontrada. Execute a extração primeiro."
            )
        documentos = list(
            db[self.mongo_collection].find({"carga_id": carga["carga_id"]})
        )
        if len(documentos) != carga["total"]:
            raise ValueError(
                "Carga bronze incompleta: contagem diferente do manifesto."
            )
        print(f"Carga {carga['carga_id']}: {len(documentos)} registros do bronze.")
        return documentos
