"""
Tracing distribuído com OpenTelemetry.

O que é tracing?
  Tracing permite rastrear uma request através de múltiplos serviços.
  Cada operação é um "span" com início, fim e metadados.

  Exemplo de trace para uma request:
    [BFA (Go)]          ──────────────────────────
      [Profile API]     ────
      [Transactions API]──────
      [Agent Service]   ────────────────
        [Planner]       ────
        [Tools]         ──────
        [Synthesizer]   ────

  Isso permite identificar gargalos e debug de problemas.

Setup atual:
  - ConsoleSpanExporter: imprime spans no console (dev)
  - Em produção: usar OTLPSpanExporter para enviar ao collector
    (Jaeger, Tempo, Datadog, AWS X-Ray)
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter


def setup_tracing() -> None:
    """
    Configura OpenTelemetry tracing.

    Deve ser chamado UMA VEZ no startup (lifespan do FastAPI).

    Em produção, substituir por:
      from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
      exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317")
    """
    # Criar o provider de tracing
    provider = TracerProvider()

    # Adicionar exporter (para onde os spans são enviados)
    # SimpleSpanProcessor: síncrono, bom para dev
    # Em produção: usar BatchSpanProcessor (assíncrono, melhor performance)
    provider.add_span_processor(
        SimpleSpanProcessor(ConsoleSpanExporter())
    )

    # Registrar globalmente
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "pj-assistant-agent") -> trace.Tracer:
    """
    Retorna um tracer para criar spans.

    Uso:
      tracer = get_tracer("api")
      with tracer.start_as_current_span("process_request") as span:
          span.set_attribute("customer_id", "cust-001")
          # ... lógica ...
    """
    return trace.get_tracer(name)
