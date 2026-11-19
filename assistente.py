"""Cliente de IA usado para gerar SQL e explicar resultados do Neon."""

from typing import Any

from openai import OpenAI


class AssistenteGPT:
    def __init__(
        self,
        chave_api: str,
        modelo: str = "gpt-6-luna",
        base_url: str = "",
    ) -> None:
        self.chave_api = chave_api
        self.modelo = modelo or "gpt-6-luna"
        self.base_url = base_url
        self._cliente: OpenAI | None = None

    def _obter_cliente(self) -> OpenAI:
        if not self.chave_api:
            raise ValueError("Configure GPT_API_KEY no arquivo .env.")
        if self._cliente is None:
            argumentos: dict[str, Any] = {"api_key": self.chave_api}
            if self.base_url:
                argumentos["base_url"] = self.base_url
            self._cliente = OpenAI(**argumentos)
        return self._cliente

    def perguntar(self, instrucao: str, pergunta: str) -> str:
        """Envia uma pergunta ao modelo e devolve somente o texto da resposta."""
        resposta = self._obter_cliente().chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": instrucao},
                {"role": "user", "content": pergunta},
            ],
        )
        conteudo = resposta.choices[0].message.content
        if not conteudo:
            raise RuntimeError("O modelo devolveu uma resposta vazia.")
        return conteudo.strip()

    def gerar_sql(self, pergunta: str, esquema: str) -> str:
        """Transforma uma pergunta em português em um único SELECT PostgreSQL."""
        instrucao = (
            "Você é especialista em PostgreSQL. Com base apenas nas tabelas abaixo, "
            "escreva UM comando SELECT que responda à pergunta. Não use INSERT, UPDATE, "
            "DELETE, DDL nem mais de uma instrução. Responda somente com SQL, sem "
            f"explicações e sem blocos Markdown.\n\nTabelas:\n{esquema}"
        )
        resposta = self.perguntar(instrucao, pergunta)
        return resposta.replace("```sql", "").replace("```", "").strip()

    def explicar_resultado(self, pergunta: str, dados: list[dict[str, Any]]) -> str:
        """Produz uma resposta curta usando apenas os dados consultados."""
        instrucao = (
            "Responda em português, de forma curta e objetiva, usando somente os "
            "dados fornecidos. Se os dados forem insuficientes, informe isso."
        )
        return self.perguntar(
            instrucao, f"Pergunta: {pergunta}\nDados consultados: {dados}"
        )
