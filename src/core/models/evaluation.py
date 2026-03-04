"""
Modelos do LLM-as-Judge — entrada e saída da avaliação.

O LLM-as-Judge é um LLM separado que avalia a QUALIDADE da conversa
entre o cliente e o agente. Ele não participa da conversa — só critica.

Fluxo:
  BFA (Go) ──► POST /v1/evaluate ──► Judge LLM ──► EvaluationResponse ──► BFA

Por que um módulo apartado?
  - Modelos de avaliação ≠ modelos de conversa
  - Pode evoluir independentemente (novos critérios, novo prompt)
  - Fácil de desligar sem afetar o agente principal
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# =============================================================================
# Enum — Veredito do Judge
# =============================================================================

class Verdict(str, Enum):
    """
    Resultado final da avaliação.

    O BFA usa para decidir ações:
      - PASS       → conversa OK, nenhuma ação necessária
      - SOFT_FAIL  → problemas menores, logar para análise
      - HARD_FAIL  → problemas graves, escalar para humano
    """
    PASS = "pass"
    SOFT_FAIL = "soft_fail"
    HARD_FAIL = "hard_fail"


# =============================================================================
# Request — o que o BFA envia para avaliação
# =============================================================================

class ConversationTurn(BaseModel):
    """
    Um turno da conversa (pergunta + resposta) com metadados.

    O BFA envia a conversa completa para o judge avaliar.
    Os metadados (latency, confidence) permitem ao judge
    considerar aspectos operacionais além do texto.
    """
    query: str                                           # O que o cliente perguntou
    answer: str                                          # O que o agente respondeu
    step: str | None = None                              # Step do onboarding (se aplicável)
    intent: str | None = None                            # Intenção detectada
    confidence: float | None = None                      # Confiança do agente naquele turno
    latency_ms: float | None = None                      # Latência em ms
    created_at: str | None = None                        # Timestamp ISO 8601
    contexts: list[str] = Field(                          # Chunks RAG usados neste turno
        default_factory=list,                             # Vazio = turno sem RAG (onboarding, etc.)
        description="Chunks da knowledge base usados para gerar a resposta",
    )
    financial_context_keys: list[str] = Field(             # Sub-contextos financeiros disponíveis
        default_factory=list,                             # Ex: ["account", "cards", "pix"]
        description="Quais sub-contextos financeiros foram enviados ao agente neste turno",
    )


class EvaluationRequest(BaseModel):
    """
    Payload de entrada do endpoint /v1/evaluate.

    O BFA envia a conversa completa (todos os turnos)
    para que o judge avalie a qualidade como um todo.
    """
    customer_id: str = "anonymous"
    conversation: list[ConversationTurn] = Field(
        ...,                                              # Obrigatório
        min_length=1,                                     # Ao menos 1 turno
        description="Lista de turnos da conversa a avaliar",
    )


# =============================================================================
# Response — o que o judge devolve ao BFA
# =============================================================================

class CriterionResult(BaseModel):
    """
    Resultado de UM critério de avaliação.

    O judge avalia cada critério separadamente e dá uma nota + justificativa.
    Isso permite ao BFA saber EXATAMENTE onde a conversa falhou.

    Exemplo:
      {
        "criterion": "correctness",
        "score": 8,
        "max_score": 10,
        "reasoning": "Todas as informações estavam corretas..."
      }
    """
    criterion: str                                        # Nome do critério
    score: int = Field(ge=0, le=10)                       # Nota 0-10
    max_score: int = 10                                   # Nota máxima
    reasoning: str                                        # Justificativa do judge


class EvaluationResponse(BaseModel):
    """
    Resposta completa da avaliação — o que vai para o BFA.

    Contém:
      - Nota geral (overall_score) → média ponderada dos critérios
      - Veredito (verdict) → PASS / SOFT_FAIL / HARD_FAIL
      - Critérios individuais → nota + justificativa por critério
      - Resumo executivo → texto curto para dashboards
      - Sugestões de melhoria → ações concretas para o time

    O BFA pode usar o veredito para:
      - Logar qualidade por atendimento
      - Escalar para humano se HARD_FAIL
      - Alimentar dashboards de qualidade
    """
    customer_id: str
    overall_score: float = Field(ge=0.0, le=10.0)         # Nota final (0-10)
    verdict: Verdict                                       # PASS / SOFT_FAIL / HARD_FAIL
    criteria: list[CriterionResult]                        # Notas por critério
    summary: str                                           # Resumo executivo
    improvements: list[str] = Field(default_factory=list)  # Sugestões concretas
    num_turns: int                                         # Turnos avaliados
    metadata: EvaluationMetadata = Field(
        default_factory=lambda: EvaluationMetadata(),
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
    )


class EvaluationMetadata(BaseModel):
    """Metadados da avaliação — observabilidade."""
    judge_model: str = ""                                  # Modelo usado pelo judge
    judge_prompt_version: str = ""                         # Versão do prompt
    tokens_used: int = 0                                   # Tokens consumidos na avaliação
    estimated_cost_usd: float = 0.0                        # Custo da avaliação
    evaluation_duration_ms: float = 0.0                    # Latência da avaliação
