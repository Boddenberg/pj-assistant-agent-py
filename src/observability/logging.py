"""
Logs estruturados com structlog.

Por que structlog e não logging padrão?
  - Saída em JSON: fácil de parsear por ferramentas (Datadog, ELK, CloudWatch)
  - Contexto automático: timestamp, log_level, stack trace
  - Context vars: adicionar customer_id, request_id uma vez,
    e todos os logs daquela request têm o contexto
  - Performance: cache de loggers, processadores otimizados

Exemplo de saída:
  {"event": "request_completed", "customer_id": "cust-001", "tokens": 450,
   "cost_usd": 0.001, "duration_s": 2.3, "level": "info", "timestamp": "2026-..."}

Em produção:
  - Integrar com Datadog APM ou CloudWatch Logs
  - Adicionar correlation_id do BFA para tracing end-to-end
  - Configurar alerts em logs de error
"""

import structlog

from src.core.config import settings


def setup_logging() -> None:
    """
    Configura logging estruturado para toda a aplicação.

    Deve ser chamado UMA VEZ no startup (lifespan do FastAPI).
    Após isso, qualquer módulo pode usar get_logger() para logar.

    Processadores (executados em ordem):
      1. merge_contextvars → adiciona variáveis de contexto (request_id, etc.)
      2. add_log_level    → adiciona campo "level"
      3. TimeStamper      → adiciona campo "timestamp" em ISO 8601
      4. StackInfoRenderer → adiciona stack trace se houver
      5. format_exc_info  → formata exceções
      6. JSONRenderer     → serializa tudo como JSON
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,     # Contexto da request
            structlog.processors.add_log_level,          # Adiciona "level"
            structlog.processors.TimeStamper(fmt="iso"), # Adiciona timestamp
            structlog.processors.StackInfoRenderer(),    # Stack trace
            structlog.processors.format_exc_info,        # Formata exceções
            structlog.processors.JSONRenderer(),         # Saída JSON
        ],
        # Filtro de nível: só loga mensagens >= LOG_LEVEL
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,  # Performance: cacheia loggers
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Retorna um logger estruturado.

    Uso:
      logger = get_logger("api")
      logger.info("request_completed", customer_id="cust-001", tokens=450)

    O nome ajuda a identificar de qual módulo veio o log.
    """
    return structlog.get_logger(name)
