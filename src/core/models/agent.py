"""
Modelos internos do agente — controle do workflow LangGraph.

Estes modelos são usados internamente pelo agente para
rastreabilidade, reasoning e observabilidade.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

from src.core.models.customer import CustomerProfile  # noqa: F401 — re-export p/ tools.py


class StepType(str, Enum):
    """
    Tipos de passos que o agente pode executar.

    Cada passo é registrado para rastreabilidade (reasoning).
    O BFA e o front podem exibir esses passos ao usuário.
    """
    PLAN = "plan"                   # Planejamento: decidir o que fazer
    RETRIEVE = "retrieve"           # Busca RAG: consultar base de conhecimento
    TOOL_CALL = "tool_call"         # Execução de tool: analisar dados
    SYNTHESIZE = "synthesize"       # Síntese: gerar resposta final


class AgentStep(BaseModel):
    """
    Registro de um passo executado pelo agente.

    Esses registros formam o "reasoning" — a justificativa estruturada
    de como o agente chegou à resposta. Útil para:
      - Auditoria (por que o agente disse X?)
      - Debug (qual passo demorou mais?)
      - Transparência (mostrar ao cliente o raciocínio)
    """
    step: StepType                  # Tipo do passo
    detail: str                     # Descrição do que foi feito
    duration_ms: float = 0.0        # Tempo gasto nesse passo (ms)


class AgentMetadata(BaseModel):
    """
    Metadados de observabilidade — NÃO usados para decisão do BFA.

    Servem para monitoramento, debug e auditoria.
    O BFA pode logar/encaminhar para dashboards, mas não usa para routing.
    """
    reasoning: list[AgentStep] = Field(default_factory=list)   # Passos executados
    sources: list[str] = Field(default_factory=list)           # Fontes RAG consultadas
    tokens_used: int = 0                                       # Total tokens consumidos
    estimated_cost_usd: float = 0.0                            # Custo estimado USD
