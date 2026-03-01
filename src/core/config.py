"""
Configuração centralizada do agente.

Todas as variáveis vêm de .env ou environment variables.
Usa pydantic-settings para validação automática de tipos.

Por que pydantic-settings?
  - Validação em startup (fail-fast se falta config obrigatória)
  - Tipagem forte (int vira int, float vira float)
  - Um único lugar para toda config → fácil de auditar
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Configurações do agente — carregadas automaticamente de .env ou env vars.

    Agrupadas por responsabilidade para facilitar leitura e manutenção.
    Cada grupo pode virar um serviço separado no futuro (12-factor app).
    """

    # ─── LLM ────────────────────────────────────────────────────────
    # Chave de API do provedor LLM. Obrigatória para o agente funcionar.
    openai_api_key: str = Field(default="", description="Chave da API OpenAI")

    # Modelo usado pelo agente. gpt-4o-mini é o melhor custo-benefício atual.
    llm_model: str = Field(default="gpt-4o-mini")

    # Temperatura baixa = respostas mais determinísticas e consistentes.
    # Para assistente financeiro, consistência é mais importante que criatividade.
    llm_temperature: float = Field(default=0.1)

    # ─── BFA (Backend Go) ──────────────────────────────────────────
    # URL do BFA que orquestra as chamadas. O agente é chamado pelo BFA.
    bfa_base_url: str = Field(default="http://localhost:8080")

    # ─── RAG ────────────────────────────────────────────────────────
    # Diretório onde ChromaDB persiste os vetores em disco.
    chroma_persist_dir: str = Field(default="./data/chroma")

    # Modelo de embedding local. all-MiniLM-L6-v2:
    #   - 384 dimensões (compacto, rápido)
    #   - Roda em CPU sem GPU
    #   - Bom o suficiente para português + inglês
    #   - Em produção: usar text-embedding-3-large da OpenAI
    embedding_model: str = Field(default="all-MiniLM-L6-v2")

    # Tamanho de cada chunk em caracteres.
    # 1024 = ~256 tokens → garante que tabelas markdown e seções
    # inteiras cabem em um único chunk (512 cortava tabelas ao meio).
    chunk_size: int = Field(default=1024)

    # Overlap entre chunks para não perder informação nas bordas.
    # 128 chars com chunks de 1024 = ~12% de sobreposição.
    chunk_overlap: int = Field(default=128)

    # Quantos chunks retornar na busca semântica.
    rag_top_k: int = Field(default=5)

    # ─── Observabilidade ────────────────────────────────────────────
    # LangFuse — plataforma de observabilidade para LLMs.
    # Registra traces, custos, latência e qualidade por request.
    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # Nível de log: DEBUG, INFO, WARNING, ERROR.
    log_level: str = Field(default="INFO")

    # ─── Segurança ──────────────────────────────────────────────────
    # Limite máximo de caracteres no input do usuário.
    # Protege contra payloads excessivos e ataques de negação de serviço.
    max_input_length: int = Field(default=2000)

    # Limite de tokens por request. Controla custo e previne loops.
    max_tokens_per_request: int = Field(default=4096)

    # Limite de custo em USD por request. Se exceder, request é rejeitado.
    max_cost_per_request_usd: float = Field(default=0.10)

    # ─── Servidor ───────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # pydantic-settings carrega automaticamente do arquivo .env
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# ─── Singleton ──────────────────────────────────────────────────────
# Importar `settings` em qualquer módulo:
#   from src.core.config import settings
#
# O objeto é criado UMA VEZ no import. Todos compartilham a mesma instância.
settings = Settings()
