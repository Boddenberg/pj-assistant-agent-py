"""
Rotas da API — endpoints REST.

Endpoints:
  POST /v1/chat       → Endpoint principal (BFA → Agente → Resposta)
  GET  /healthz       → Health check (liveness probe)
  GET  /readyz        → Readiness check (readiness probe)

Fluxo do endpoint principal (/v1/chat):
  ┌──────────────────────────────────────────────────────┐
  │  1. Recebe request do BFA (customer_id, query, ...)  │
  │  2. Valida input (tamanho, injection, PII)           │
  │  3. Executa o agente (LangGraph)                     │
  │  4. Verifica limite de custo                         │
  │  5. Registra métricas (Prometheus)                   │
  │  6. Retorna AgentResponse (JSON)                    │
  └──────────────────────────────────────────────────────┘

Tratamento de erros:
  - InputValidationError  → 400 Bad Request
  - CostLimitExceededError → 429 Too Many Requests
  - AgentError            → 500 Internal Server Error
  - Exception genérica    → 500 + fallback counter

Observabilidade:
  - Cada request gera um span OpenTelemetry
  - Métricas Prometheus: count, latency, tokens, cost
  - Log estruturado com customer_id, tokens, cost, duration
"""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from opentelemetry import trace

from src.core.models import AgentRequest, AgentResponse
from src.core.exceptions import (
    AgentError,
    InputValidationError,
    CostLimitExceededError,
)
from src.core.config import settings
from src.agent.runner import run_agent
from src.security.sanitizer import validate_input, mask_sensitive_data
from src.observability.logging import get_logger
from src.observability.metrics import (
    REQUEST_COUNT,
    REQUEST_LATENCY,
    TOKENS_USED,
    ESTIMATED_COST,
    MODEL_ERRORS,
    FALLBACK_COUNT,
)


# =============================================================================
# Setup do router
# =============================================================================

# APIRouter agrupa endpoints — equivale a Blueprint no Flask.
# Todas as rotas aqui são incluídas no app via app.include_router(router).
router = APIRouter()

# Logger e tracer específicos para a camada de API.
logger = get_logger("api")
tracer = trace.get_tracer("pj-assistant-agent")


# =============================================================================
# POST /v1/chat — Endpoint principal
# =============================================================================

@router.post("/v1/chat", response_model=AgentResponse)
async def chat(request: AgentRequest) -> AgentResponse:
    """
    Endpoint principal — recebe contexto do BFA e retorna resposta do agente.

    O BFA (Go) envia:
      - customer_id: identificador do cliente PJ
      - query: pergunta do cliente (texto livre)
      - profile: dados do perfil (faturamento, segmento, etc.)
      - transactions: lista de transações recentes (opcional)

    Retorna AgentResponse com:
      - answer: resposta do agente em linguagem natural
      - sources: fontes usadas (knowledge base)
      - reasoning_steps: passos do raciocínio (transparência)
      - tokens_used / estimated_cost_usd: métricas de consumo
    """

    # Marca o início para calcular latência
    start = time.perf_counter()

    # ═══════════════════════════════════════════════════════════════
    # LOG: REQUEST RECEBIDA
    # ═══════════════════════════════════════════════════════════════
    logger.info(
        "📥 [1/6] REQUEST_RECEIVED — Nova requisição recebida",
        customer_id=request.customer_id,
        company_name=request.profile.company_name if request.profile else "N/A",
        query=request.query[:100] + ("..." if len(request.query) > 100 else ""),
        query_length=len(request.query),
        num_transactions=len(request.transactions),
        segment=request.profile.segment if request.profile else "N/A",
        credit_score=request.profile.credit_score if request.profile else 0,
    )

    # Cria um span OpenTelemetry para rastreamento distribuído.
    with tracer.start_as_current_span("chat_request") as span:
        span.set_attribute("customer_id", request.customer_id)

        try:
            # ─────────────────────────────────────────────────────
            # PASSO 1: Validar e sanitizar input
            # ─────────────────────────────────────────────────────
            validation_start = time.perf_counter()
            request.query = validate_input(request.query)
            request.query = mask_sensitive_data(request.query)
            validation_duration = (time.perf_counter() - validation_start) * 1000

            logger.info(
                "🛡️  [2/6] INPUT_VALIDATED — Input validado e sanitizado",
                customer_id=request.customer_id,
                sanitized_query=request.query[:100] + ("..." if len(request.query) > 100 else ""),
                validation_duration_ms=round(validation_duration, 2),
            )

            # ─────────────────────────────────────────────────────
            # PASSO 2: Executar o agente
            # ─────────────────────────────────────────────────────
            agent_start = time.perf_counter()

            logger.info(
                "🤖 [3/6] AGENT_STARTED — Iniciando execução do agente LangGraph",
                customer_id=request.customer_id,
                llm_model=settings.llm_model,
                llm_temperature=settings.llm_temperature,
                max_tokens=settings.max_tokens_per_request,
            )

            response = await run_agent(request)

            agent_duration = (time.perf_counter() - agent_start) * 1000

            logger.info(
                "✅ [4/6] AGENT_COMPLETED — Agente finalizou execução",
                customer_id=request.customer_id,
                agent_duration_ms=round(agent_duration, 2),
                tokens_used=response.tokens_used,
                estimated_cost_usd=response.estimated_cost_usd,
                num_reasoning_steps=len(response.reasoning),
                num_sources=len(response.sources),
                answer_length=len(response.answer),
            )

            # ─────────────────────────────────────────────────────
            # PASSO 3: Verificar limite de custo
            # ─────────────────────────────────────────────────────
            logger.info(
                "💰 [5/6] COST_CHECK — Verificando limite de custo",
                customer_id=request.customer_id,
                estimated_cost_usd=response.estimated_cost_usd,
                cost_limit_usd=settings.max_cost_per_request_usd,
                within_limit=response.estimated_cost_usd <= settings.max_cost_per_request_usd,
            )

            if response.estimated_cost_usd > settings.max_cost_per_request_usd:
                raise CostLimitExceededError(
                    f"Custo estimado ({response.estimated_cost_usd}) excede limite "
                    f"({settings.max_cost_per_request_usd})"
                )

            # ─────────────────────────────────────────────────────
            # PASSO 4: Registrar métricas e retornar
            # ─────────────────────────────────────────────────────
            duration = time.perf_counter() - start

            REQUEST_COUNT.labels(status="success").inc()
            REQUEST_LATENCY.observe(duration)
            TOKENS_USED.labels(direction="input").inc(response.tokens_used)
            ESTIMATED_COST.observe(response.estimated_cost_usd)

            span.set_attribute("tokens_used", response.tokens_used)
            span.set_attribute("cost_usd", response.estimated_cost_usd)
            span.set_attribute("duration_s", round(duration, 3))

            logger.info(
                "📤 [6/6] REQUEST_COMPLETED — Resposta enviada com sucesso",
                customer_id=request.customer_id,
                status="success",
                total_duration_s=round(duration, 3),
                total_duration_ms=round(duration * 1000, 2),
                tokens_used=response.tokens_used,
                estimated_cost_usd=response.estimated_cost_usd,
                num_reasoning_steps=len(response.reasoning),
                num_sources=len(response.sources),
                answer_preview=response.answer[:150] + ("..." if len(response.answer) > 150 else ""),
            )

            return response

        # ─────────────────────────────────────────────────────────
        # Tratamento de erros — cada tipo vira um HTTP status diferente
        # ─────────────────────────────────────────────────────────

        except InputValidationError as e:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(status="validation_error").inc()
            logger.warning(
                "🚫 [ERRO] VALIDATION_FAILED — Input rejeitado na validação",
                customer_id=request.customer_id,
                error=str(e),
                query_preview=request.query[:80],
                duration_ms=round(duration * 1000, 2),
            )
            raise HTTPException(status_code=400, detail=str(e))

        except CostLimitExceededError as e:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(status="cost_limit").inc()
            logger.warning(
                "💸 [ERRO] COST_LIMIT_EXCEEDED — Custo excedeu limite permitido",
                customer_id=request.customer_id,
                error=str(e),
                estimated_cost_usd=response.estimated_cost_usd if 'response' in dir() else "N/A",
                cost_limit_usd=settings.max_cost_per_request_usd,
                duration_ms=round(duration * 1000, 2),
            )
            raise HTTPException(status_code=429, detail=str(e))

        except AgentError as e:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(status="agent_error").inc()
            MODEL_ERRORS.labels(model=settings.llm_model).inc()
            logger.error(
                "🔥 [ERRO] AGENT_ERROR — Erro na execução do agente",
                customer_id=request.customer_id,
                error=str(e),
                error_type=type(e).__name__,
                llm_model=settings.llm_model,
                duration_ms=round(duration * 1000, 2),
            )
            raise HTTPException(status_code=500, detail="Erro interno do agente.")

        except Exception as e:
            duration = time.perf_counter() - start
            REQUEST_COUNT.labels(status="error").inc()
            FALLBACK_COUNT.inc()
            logger.error(
                "💥 [ERRO] UNEXPECTED_ERROR — Erro inesperado não tratado",
                customer_id=request.customer_id,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2),
            )
            raise HTTPException(status_code=500, detail="Erro interno inesperado.")


# =============================================================================
# Health Checks — probes do Kubernetes
# =============================================================================

@router.get("/healthz")
async def healthz() -> dict:
    """
    Liveness probe — "o processo está vivo?"

    Kubernetes chama periodicamente. Se falhar:
      → kubelet mata o pod e recria.

    Aqui retornamos sempre 200.
    Em produção poderia checar se o event loop não está bloqueado.
    """
    return {"status": "ok"}


@router.get("/readyz")
async def readyz() -> dict:
    """
    Readiness probe — "o serviço está pronto para receber tráfego?"

    Kubernetes chama periodicamente. Se falhar:
      → pod é removido do Service (não recebe mais requests).

    Em produção poderia checar:
      - Vector store carregado?
      - LLM API respondendo?
      - BFA acessível?
    """
    return {"status": "ready"}
