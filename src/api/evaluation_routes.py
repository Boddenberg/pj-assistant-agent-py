"""
Rotas de avaliação — endpoint POST /v1/evaluate.

Rota apartada das rotas do agente (routes.py).
Registrada no app como um router separado.

Fluxo:
  BFA (Go) ──► POST /v1/evaluate ──► ConversationEvaluator ──► EvaluationResponse
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from src.core.models.evaluation import EvaluationRequest, EvaluationResponse
from src.evaluation.evaluator import ConversationEvaluator
from src.observability.logging import get_logger
from src.observability.metrics import REQUEST_COUNT

logger = get_logger("api.evaluation")

# Router separado — mantém rotas de avaliação apartadas das rotas do agente
evaluation_router = APIRouter()

# Instância única do evaluator (singleton)
_evaluator = ConversationEvaluator()


# =============================================================================
# POST /v1/evaluate — Avalia uma conversa
# =============================================================================

@evaluation_router.post("/v1/evaluate", response_model=EvaluationResponse)
async def evaluate(request: EvaluationRequest) -> EvaluationResponse:
    """
    Avalia a qualidade de uma conversa entre cliente e agente.

    O BFA envia a conversa completa (todos os turnos) e recebe:
      - Nota geral (0-10)
      - Veredito (PASS / SOFT_FAIL / HARD_FAIL)
      - Notas por critério com justificativa
      - Sugestões de melhoria

    Casos de uso:
      - Avaliar qualidade após cada atendimento
      - Dashboard de qualidade por período
      - Detectar degradação do agente
      - Escalar para humano se HARD_FAIL
    """
    start = time.perf_counter()

    logger.info(
        "🧑‍⚖️ [EVALUATE] REQUEST_RECEIVED — Avaliação solicitada",
        customer_id=request.customer_id,
        num_turns=len(request.conversation),
    )

    try:
        response = await _evaluator.evaluate(request)

        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(status="evaluation_success").inc()

        logger.info(
            "🧑‍⚖️ [EVALUATE] REQUEST_COMPLETED — Avaliação concluída",
            customer_id=request.customer_id,
            overall_score=response.overall_score,
            verdict=response.verdict.value,
            duration_s=round(duration, 3),
            tokens_used=response.metadata.tokens_used,
            cost_usd=response.metadata.estimated_cost_usd,
        )

        return response

    except Exception as e:
        duration = time.perf_counter() - start
        REQUEST_COUNT.labels(status="evaluation_error").inc()

        logger.error(
            "🧑‍⚖️ [EVALUATE] REQUEST_FAILED — Erro na avaliação",
            customer_id=request.customer_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=round(duration * 1000, 2),
        )

        raise HTTPException(
            status_code=500,
            detail="Erro ao avaliar conversa. Tente novamente.",
        )
