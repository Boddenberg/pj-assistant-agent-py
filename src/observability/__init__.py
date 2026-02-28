# =============================================================================
# Observability — logs, métricas e tracing
# =============================================================================
# Três pilares de observabilidade implementados:
#
#   1. LOGS (logging.py)
#      - structlog com JSON → fácil de parsear por Datadog/ELK/CloudWatch
#      - Logs estruturados com contexto (customer_id, duration, tokens)
#
#   2. MÉTRICAS (metrics.py)
#      - Prometheus counters e histograms
#      - Latência, tokens, custo, erros por tool/modelo
#      - Endpoint /metrics para scraping
#
#   3. TRACING (tracing.py)
#      - OpenTelemetry spans distribuídos
#      - Cada request tem um trace_id único
#      - Permite rastrear o fluxo BFA → Agent → LLM → RAG
# =============================================================================
