"""
FastAPI Application Factory — entry point da aplicação.

Este módulo é o ponto de entrada do serviço HTTP.
Ele cria a instância FastAPI e configura:
  1. Lifespan hooks (startup/shutdown)
  2. Rotas da aplicação
  3. Endpoint de métricas Prometheus (/metrics)

Como rodar:
  $ uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

Arquitetura:
  - Usamos o padrão "app factory" (a instância `app` é criada no module-level)
  - O uvicorn importa `src.api.main:app` diretamente
  - O `lifespan` context manager cuida de inicializações (logging, tracing)
  - Em produção, o Dockerfile roda uvicorn com workers via gunicorn

Por que lifespan ao invés de @app.on_event?
  - @app.on_event("startup") está deprecated desde FastAPI 0.93
  - lifespan é o padrão recomendado (asynccontextmanager)
  - Permite yield (código antes = startup, depois = shutdown)
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from src.api.routes import router
from src.observability.logging import setup_logging
from src.observability.tracing import setup_tracing


# =============================================================================
# Lifespan — Startup / Shutdown hooks
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.

    STARTUP (antes do yield):
      - Configura logging estruturado (structlog → JSON)
      - Configura tracing distribuído (OpenTelemetry)
      - Em produção: poderia pre-carregar o vector store aqui

    SHUTDOWN (depois do yield):
      - Não temos cleanup obrigatório por enquanto
      - Em produção: fechar conexões, flush de métricas, etc.
    """
    # ── Startup ──────────────────────────────────────────────────────
    setup_logging()     # structlog com JSON (ver observability/logging.py)
    setup_tracing()     # OpenTelemetry OTLP (ver observability/tracing.py)

    # yield = aplicação rodando e servindo requests
    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    # Nada por enquanto. Em produção:
    # - await close_db_connections()
    # - tracer_provider.shutdown()


# =============================================================================
# App Factory — instância FastAPI
# =============================================================================

app = FastAPI(
    # Metadata da API — aparece no Swagger UI (/docs)
    title="PJ Assistant Agent",
    description="Agente de IA Generativa para clientes PJ — Case Itaú",
    version="0.1.0",

    # Lifespan hooks (startup + shutdown)
    lifespan=lifespan,
)


# =============================================================================
# Rotas da aplicação
# =============================================================================

# Inclui todas as rotas definidas em routes.py
# O APIRouter é como um "mini-app" que agrupa endpoints
app.include_router(router)


# =============================================================================
# Prometheus Metrics — /metrics
# =============================================================================

# make_asgi_app() cria um mini-app ASGI que expõe todas as métricas
# registradas (counters, histograms) no formato texto do Prometheus.
#
# Acessar: GET http://localhost:8000/metrics
# O Prometheus faz scraping desse endpoint periodicamente.
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)
