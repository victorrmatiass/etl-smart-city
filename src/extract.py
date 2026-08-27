import os
from typing import Any, Dict, List, Optional, Union

import requests
from dotenv import load_dotenv

load_dotenv()


JsonResponse = Union[Dict[str, Any], List[Any], None]


class Extract:
    """Extrai dados públicos do Portal de Dados Abertos."""

    BASE_URL = "https://dados.gov.br"
    API_KEY_ENV = "CHAVE_API_DADOS_ABERTOS"
    DEFAULT_PRIVATE_FILTER = "false"

    def __init__(self, api_key: Optional[str] = None) -> None:
        """Inicializa o extrator usando uma chave informada ou configurada no `.env`."""
        self.api_key = api_key or os.getenv(self.API_KEY_ENV, "")
        if not self.api_key:
            raise ValueError(
                f"Chave de API não encontrada. Defina {self.API_KEY_ENV} no .env."
            )

        self.headers = {
            "accept": "application/json",
            "chave-api-dados-abertos": self.api_key,
        }

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> JsonResponse:
        """Executa uma requisição GET e retorna a resposta em JSON."""
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, params=params, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def listar_conjuntos_de_dados(
        self,
        pagina: int,
        nome_conjunto_dados: Optional[str] = None,
        dados_abertos: Optional[bool] = None,
        id_organizacao: Optional[str] = None,
    ) -> JsonResponse:
        """Lista conjuntos de dados, com filtros opcionais de nome, abertura e organização.

        Args:
            pagina: Número da página desejada.
            nome_conjunto_dados: Parte do nome do conjunto a pesquisar.
            dados_abertos: Filtra conjuntos marcados como dados abertos.
            id_organizacao: Identificador da organização responsável.
        """
        params = {
            "pagina": pagina,
            "isPrivado": self.DEFAULT_PRIVATE_FILTER,
        }

        if nome_conjunto_dados:
            params["nomeConjuntoDados"] = nome_conjunto_dados

        if dados_abertos is not None:
            params["dadosAbertos"] = str(dados_abertos).lower()

        if id_organizacao:
            params["idOrganizacao"] = id_organizacao

        return self._get("/dados/api/publico/conjuntos-dados", params=params)
    def detalhar_conjunto_de_dados(self, id_conjunto: str) -> JsonResponse:
        """Busca os detalhes de um conjunto de dados pelo seu identificador.

        Args:
            id_conjunto: Identificador do conjunto de dados.
        """
        return self._get(f"/dados/api/publico/conjuntos-dados/{id_conjunto}")

    def listar_tags_conjunto_de_dados(self, id_conjunto: str) -> JsonResponse:
        """Lista as tags associadas a um conjunto de dados.

        Args:
            id_conjunto: Identificador do conjunto de dados.
        """
        return self._get(f"/dados/api/publico/conjuntos-dados/{id_conjunto}/tag")

    def listar_observancia_legal(self) -> JsonResponse:
        """Extrai os registros de observância legal dos conjuntos de dados."""
        return self._get("/dados/api/publico/conjuntos-dados/observancia-legal")

    def listar_objetivos_desenvolvimento_sustentavel(self) -> JsonResponse:
        """Extrai os Objetivos de Desenvolvimento Sustentável disponíveis."""
        return self._get("/dados/api/publico/conjuntos-dados/objetivos-desenvolvimento-sustentavel")

    def listar_formatos(self) -> JsonResponse:
        """Extrai os formatos de arquivo disponíveis nos conjuntos de dados."""
        return self._get("/dados/api/publico/conjuntos-dados/formatos")

    def consultar_solicitacoes(
        self,
        data_abertura: Optional[str] = None,
        tipo_solicitacao: Optional[str] = None,
        status_solicitacao: Optional[str] = None,
    ) -> JsonResponse:
        """Consulta solicitações usando data, tipo e status como filtros opcionais.

        Args:
            data_abertura: Data de abertura no formato `YYYY-MM-DD`.
            tipo_solicitacao: Tipo da solicitação definido pela API.
            status_solicitacao: Status da solicitação definido pela API.
        """
        params = {
            "dataAbertura": data_abertura,
            "tipoSolicitacao": tipo_solicitacao,
            "statusSolicitacao": status_solicitacao,
        }
        return self._get("/dados/api/solicitacoes", params=params)

    def listar_reusos(
        self,
        nome_reuso: Optional[str] = None,
        nome_autor: Optional[str] = None,
        id_organizacao: Optional[str] = None,
    ) -> JsonResponse:
        """Lista reúsos com filtros opcionais de nome, autor e organização.

        Args:
            nome_reuso: Parte do nome do reúso a pesquisar.
            nome_autor: Nome do autor do reúso.
            id_organizacao: Identificador da organização responsável.
        """
        params = {
            "nomeReuso": nome_reuso,
            "nomeAutor": nome_autor,
            "idOrganizacao": id_organizacao,
        }
        return self._get("/dados/api/publico/reusos", params=params)

    def detalhar_reuso(self, id_reuso: int) -> JsonResponse:
        """Busca os detalhes de um reúso pelo identificador numérico.

        Args:
            id_reuso: Identificador numérico do reúso.
        """
        return self._get(f"/dados/api/publico/reuso/{id_reuso}")

    def consultar_temas(self) -> JsonResponse:
        """Extrai a lista de temas cadastrados no portal."""
        return self._get("/dados/api/temas")

    def consultar_tags(self, nome: str) -> JsonResponse:
        """Busca tags pelo nome informado.

        Args:
            nome: Nome ou termo da tag a pesquisar.
        """
        return self._get("/dados/api/tags", params={"nome": nome})

    def listar_organizacoes(self, pagina: int, nome: Optional[str] = None) -> JsonResponse:
        """Lista organizações cadastradas, filtrando opcionalmente pelo nome.

        Args:
            pagina: Número da página desejada.
            nome: Parte do nome da organização a pesquisar.
        """
        return self._get(
            "/dados/api/publico/organizacao",
            params={"pagina": pagina, "nome": nome},
        )

    def detalhar_organizacao(self, id_organizacao: str) -> JsonResponse:
        """Busca os detalhes de uma organização pelo seu identificador.

        Args:
            id_organizacao: Identificador da organização.
        """
        return self._get(f"/dados/api/publico/organizacao/{id_organizacao}")
