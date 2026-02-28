"""
Rotas da API — endpoints REST.

Endpoints:
  POST /v1/assistant  → Endpoint principal (BFA → Agente → Resposta)
  GET  /healthz       → Health check (liveness probe)
  GET  /readyz        → Readiness check (readiness probe)

Fluxo do endpoint principal (/v1/assistant):
  ┌──────────────────────────────────────────────────────┐
  │  1. Recebe request do BFA (customer_id, query, ...)  │
  │  2. Valida input (tamanho, injection, PII)           │
  │  3. Executa o agente (LangGraph)                     │
  │  4. Verifica limite de custo                         │
  │  5. Registra métricas (Prometheus)                   │
  │  6. Retorna AssistantResponse (JSON)                 │
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

from src.core.models import AssistantRequest, AssistantResponse
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
# POST /v1/assistant — Endpoint principal
# =============================================================================

@router.post("/v1/assistant", response_model=AssistantResponse)
async def assistant(request: AssistantRequest) -> AssistantResponse:
    """
    Endpoint principal — recebe contexto do BFA e retorna resposta do agente.

    O BFA (Go) envia:
      - customer_id: identificador do cliente PJ
      - query: pergunta do cliente (texto livre)
      - profile: dados do perfil (faturamento, segmento, etc.)
      - transactions: lista de transações recentes (opcional)

    Retorna AssistantResponse com:
      - answer: resposta do agente em linguagem natural
      - sources: fontes usadas (knowledge base)
      - reasoning_steps: passos do raciocínio (transparência)
      - tokens_used / estimated_cost_usd: métricas de consumo
    """

    # Marca o início para calcular latência
    start = time.perf_counter()

    # Cria um span OpenTelemetry para rastreamento distribuído.
    # O trace_id propaga do BFA → Agente → LLM permitindo
    # visualizar a request inteira no Jaeger/Tempo.
    with tracer.start_as_current_span("assistant_request") as span:
        # Atributos do span — aparecem no trace para debugging
        span.set_attribute("customer_id", request.customer_id)

        try:
            # ─────────────────────────────────────────────────────
            # PASSO 1: Validar e sanitizar input
            # ─────────────────────────────────────────────────────
            # validate_input: checa tamanho, prompt injection
            # mask_sensitive_data: mascara CPF, CNPJ, etc.
            request.query = validate_input(request.query)
            request.query = mask_sensitive_data(request.query)

            # ─────────────────────────────────────────────────────
            # PASSO 2: Executar o agente
            # ─────────────────────────────────────────────────────
            # run_agent é o facade que invoca o grafo LangGraph.
            # Retorna AssistantResponse com answer, sources, etc.
            response = await run_agent(request)

            # ─────────────────────────────────────────────────────
            # PASSO 3: Verificar limite de custo
            # ─────────────────────────────────────────────────────
            # Proteção contra requests caras demais (ex: loop infinito).
            # O limite é configurável via MAX_COST_PER_REQUEST_USD.
            if response.estimated_cost_usd > settings.max_cost_per_request_usd:
                raise CostLimitExceededError(
                    f"Custo estimado ({response.estimated_cost_usd}) excede limite "
                    f"({settings.max_cost_per_request_usd})"
                )

            # ─────────────────────────────────────────────────────
            # PASSO 4: Registrar métricas e retornar
            # ─────────────────────────────────────────────────────
            duration = time.perf_counter() - start

            # Counters e histograms do Prometheus
            REQUEST_COUNT.labels(status="success").inc()
            REQUEST_LATENCY.observe(duration)
            TOKENS_USED.labels(direction="input").inc(response.tokens_used)
            ESTIMATED_COST.observe(response.estimated_cost_usd)

            # Atributos do span — enriquecem o trace
            span.set_attribute("tokens_used", response.tokens_used)
            span.set_attribute("cost_usd", response.estimated_cost_usd)
            span.set_attribute("duration_s", round(duration, 3))

            # Log estruturado — aparece no stdout como JSON
            logger.info(
                "request_completed",
                customer_id=request.customer_id,
                tokens=response.tokens_used,
                cost_usd=response.estimated_cost_usd,
                duration_s=round(duration, 3),
            )

            return response

        # ─────────────────────────────────────────────────────────
        # Tratamento de erros — cada tipo vira um HTTP status diferente
        # ─────────────────────────────────────────────────────────

        except InputValidationError as e:
            # 400 — input do usuário é inválido (vazio, injection, etc.)
            REQUEST_COUNT.labels(status="validation_error").inc()
            logger.warning(
                "input_validation_error",
                error=str(e),
                customer_id=request.customer_id,
            )
            raise HTTPException(status_code=400, detail=str(e))

        except CostLimitExceededError as e:
            # 429 — custo estimado excede o limite configurado.
            # Usamos 429 (Too Many Requests) por ser rate-limiting de custo.
            REQUEST_COUNT.labels(status="cost_limit").inc()
            logger.warning(
                "cost_limit_exceeded",
                error=str(e),
                customer_id=request.customer_id,
            )
            raise HTTPException(status_code=429, detail=str(e))

        except AgentError as e:
            # 500 — erro conhecido do agente (LLM, RAG, tool).
            # Registra qual modelo falhou para monitoramento.
            REQUEST_COUNT.labels(status="agent_error").inc()
            MODEL_ERRORS.labels(model=settings.llm_model).inc()
            logger.error(
                "agent_error",
                error=str(e),
                customer_id=request.customer_id,
            )
            # NÃO expor detalhes internos ao cliente (segurança)
            raise HTTPException(status_code=500, detail="Erro interno do agente.")

        except Exception as e:
            # 500 — erro totalmente inesperado (bug, dependência caiu, etc.).
            # Incrementa fallback_count para alertar que algo está muito errado.
            REQUEST_COUNT.labels(status="error").inc()
            FALLBACK_COUNT.inc()
            logger.error(
                "unexpected_error",
                error=str(e),
                customer_id=request.customer_id,
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
