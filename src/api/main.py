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
from src.core.config import settings
from src.observability.logging import setup_logging, get_logger
from src.observability.tracing import setup_tracing


# =============================================================================
# Lifespan — Startup / Shutdown hooks
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    """
    # ── Startup ──────────────────────────────────────────────────────
    setup_logging()
    setup_tracing()

    logger = get_logger("startup")

    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🏦  PJ ASSISTANT AGENT — Itaú IA Generativa               ║
║                                                              ║
║   ✅ Servidor iniciado com sucesso!                          ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   🌐 Host:        {settings.host:<40}║
║   🔌 Porta:       {settings.port:<40}║
║   🤖 Modelo LLM:  {settings.llm_model:<40}║
║   🌡️  Temperatura: {str(settings.llm_temperature):<40}║
║   📊 Log Level:   {settings.log_level:<40}║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   📖 Swagger UI:   http://{settings.host}:{settings.port}/docs{' ' * (25 - len(str(settings.port)))}║
║   ❤️  Health:       http://{settings.host}:{settings.port}/healthz{' ' * (22 - len(str(settings.port)))}║
║   📊 Métricas:     http://{settings.host}:{settings.port}/metrics{' ' * (22 - len(str(settings.port)))}║
║   🤖 Chat:         POST /v1/chat{' ' * 30}║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)

    logger.info(
        "🚀 SERVER_STARTED — PJ Assistant Agent iniciado com sucesso",
        host=settings.host,
        port=settings.port,
        llm_model=settings.llm_model,
        llm_temperature=settings.llm_temperature,
        log_level=settings.log_level,
        embedding_model=settings.embedding_model,
        rag_top_k=settings.rag_top_k,
        max_tokens_per_request=settings.max_tokens_per_request,
        max_cost_per_request_usd=settings.max_cost_per_request_usd,
    )

    yield

    # ── Shutdown ─────────────────────────────────────────────────────
    logger.info("🛑 SERVER_STOPPING — PJ Assistant Agent encerrando...")
    print("\n🛑 PJ Assistant Agent encerrado. Até a próxima! 👋")


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
