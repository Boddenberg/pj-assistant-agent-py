"""
Logs estruturados com structlog.

Por que structlog e não logging padrão?
  - Saída em JSON: fácil de parsear por ferramentas (Datadog, ELK, CloudWatch)
  - Contexto automático: timestamp, log_level, stack trace
  - Context vars: adicionar customer_id, request_id uma vez,
    e todos os logs daquela request têm o contexto
  - Performance: cache de loggers, processadores otimizados

Exemplo de saída (dev — pretty):
  {
    "event": "request_completed",
    "customer_id": "cust-001",
    "tokens": 450,
    "cost_usd": 0.001,
    "duration_s": 2.3,
    "level": "info",
    "timestamp": "2026-..."
  }

Em produção:
  - JSON compacto (uma linha por log) para ferramentas de log
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

    Modo de renderização:
      - LOG_LEVEL=DEBUG → JSON pretty-printed (indentado, colorido no console)
      - LOG_LEVEL=INFO+ em produção → JSON compacto (uma linha, machine-readable)

    Dica: Para forçar pretty em dev, defina LOG_LEVEL=DEBUG no .env
    """
    import logging

    # Em dev (DEBUG/INFO local): JSON indentado e legível
    # Em prod: JSON compacto (uma linha) para ELK/Datadog/CloudWatch
    is_dev = settings.log_level.upper() == "DEBUG"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,     # Contexto da request
            structlog.processors.add_log_level,          # Adiciona "level"
            structlog.processors.TimeStamper(fmt="iso"), # Adiciona timestamp
            structlog.processors.StackInfoRenderer(),    # Stack trace
            structlog.processors.format_exc_info,        # Formata exceções
            structlog.processors.JSONRenderer(
                indent=2 if is_dev else None,            # Pretty print em dev
                sort_keys=True,                          # Campos ordenados A-Z
                ensure_ascii=False,                      # Manter acentos (português)
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
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
