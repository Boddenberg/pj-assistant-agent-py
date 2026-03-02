"""
Logs estruturados com structlog + Axiom.

Por que structlog e não logging padrão?
  - Saída em JSON: fácil de parsear por ferramentas (Axiom, Datadog, ELK)
  - Contexto automático: timestamp, log_level, stack trace
  - Context vars: adicionar customer_id, request_id uma vez,
    e todos os logs daquela request têm o contexto
  - Performance: cache de loggers, processadores otimizados

Por que Axiom?
  - 500GB/mês free, 30 dias de retenção
  - Parse automático de JSON estruturado
  - Queries tipo SQL (APL) para análise
  - Dashboards + alertas integrados
  - Setup em 3 linhas (token + dataset)

Exemplo de saída:
  {
    "event": "request_completed",
    "customer_id": "cust-001",
    "tokens": 450,
    "cost_usd": 0.001,
    "duration_s": 2.3,
    "level": "info",
    "timestamp": "2026-..."
  }

Os logs vão para:
  1. stdout (sempre) — visível no Railway, Docker, terminal
  2. Axiom (se AXIOM_TOKEN configurado) — dashboard centralizado
"""

from __future__ import annotations

import json
import logging
from logging import Handler, LogRecord
from typing import Any

import structlog

from src.core.config import settings


# =============================================================================
# Axiom Handler — envia logs para o Axiom via API
# =============================================================================

class AxiomHandler(Handler):
    """
    Handler do stdlib logging que envia logs para o Axiom.

    Funciona com structlog porque o structlog renderiza JSON e emite
    via PrintLoggerFactory → stdout. Este handler intercepta os mesmos
    logs no nível do stdlib e envia ao Axiom em batch.

    Usa a lib oficial axiom-py que faz batching automático.
    """

    def __init__(self, token: str, dataset: str, org_id: str = "") -> None:
        super().__init__()
        from axiom_py import Client

        client_kwargs: dict[str, Any] = {"token": token}
        if org_id:
            client_kwargs["org_id"] = org_id

        self._client = Client(**client_kwargs)
        self._dataset = dataset

    def emit(self, record: LogRecord) -> None:
        """Envia um log record para o Axiom."""
        try:
            # structlog renderiza JSON no record.msg
            # Tentar parsear para enviar como objeto estruturado
            try:
                event = json.loads(record.getMessage())
            except (json.JSONDecodeError, TypeError):
                event = {
                    "event": record.getMessage(),
                    "level": record.levelname.lower(),
                }

            self._client.ingest_events(
                dataset=self._dataset,
                events=[event],
            )
        except Exception:
            # Nunca deixar o Axiom derrubar a aplicação
            pass


def setup_logging() -> None:
    """
    Configura logging estruturado para toda a aplicação.

    Deve ser chamado UMA VEZ no startup (lifespan do FastAPI).
    Após isso, qualquer módulo pode usar get_logger() para logar.

    Outputs:
      1. stdout (sempre) — structlog JSON, visível em Railway/Docker
      2. Axiom (se AXIOM_TOKEN configurado) — dashboard centralizado

    Modo de renderização:
      - LOG_LEVEL=DEBUG → JSON pretty-printed (indentado no console)
      - LOG_LEVEL=INFO+ → JSON compacto (uma linha, machine-readable)
    """
    # Em dev (DEBUG): JSON indentado e legível
    # Em prod: JSON compacto (uma linha) para ferramentas de log
    is_dev = settings.log_level.upper() == "DEBUG"

    # ── Configurar Axiom handler no stdlib logging ──────────────────
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.getLevelName(settings.log_level.upper()))

    if settings.axiom_token:
        axiom_handler = AxiomHandler(
            token=settings.axiom_token,
            dataset=settings.axiom_dataset,
            org_id=settings.axiom_org_id,
        )
        axiom_handler.setLevel(logging.getLevelName(settings.log_level.upper()))
        root_logger.addHandler(axiom_handler)

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

    # ── Log de confirmação ──────────────────────────────────────────
    if settings.axiom_token:
        boot_logger = structlog.get_logger("boot")
        boot_logger.info(
            "✅ [AXIOM] Logs sendo enviados para Axiom",
            dataset=settings.axiom_dataset,
        )
    else:
        boot_logger = structlog.get_logger("boot")
        boot_logger.info(
            "📋 [LOGGING] Axiom não configurado — logs apenas em stdout",
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
