"""
Métricas Prometheus + estimativa de custo.

Métricas implementadas (expostas em /metrics):

  COUNTERS (valores acumulativos):
    - agent_requests_total{status}     → Total de requests por status
    - agent_tokens_total{direction}    → Total de tokens (input/output)
    - agent_tool_errors_total{tool}    → Erros por tool
    - agent_model_errors_total{model}  → Erros por modelo LLM
    - agent_fallback_total             → Vezes que caiu em fallback

  HISTOGRAMS (distribuição de valores):
    - agent_request_duration_seconds   → Latência por request
    - agent_request_cost_usd           → Custo estimado por request

Como funciona Prometheus?
  1. A aplicação registra métricas (counters, histograms)
  2. Prometheus faz scraping do endpoint /metrics periodicamente
  3. Grafana visualiza as métricas em dashboards
  4. Alertmanager dispara alerts (ex: latência > 10s)

Estimativa de custo:
  - Baseada nos preços do GPT-4o-mini (mais barato)
  - Input: $0.15 / 1M tokens
  - Output: $0.60 / 1M tokens
  - Em produção: ajustar conforme modelo usado
"""

from prometheus_client import Counter, Histogram


# =============================================================================
# Counters — valores que só sobem (total de X)
# =============================================================================

# Total de requests ao agente, separado por status.
# Labels: "success", "validation_error", "cost_limit", "agent_error", "error"
REQUEST_COUNT = Counter(
    "agent_requests_total",
    "Total de requisições ao agente",
    ["status"],
)

# Total de tokens consumidos, separado por direção.
# Labels: "input" (tokens enviados ao LLM), "output" (tokens gerados pelo LLM)
TOKENS_USED = Counter(
    "agent_tokens_total",
    "Total de tokens consumidos",
    ["direction"],
)

# Erros por tool — monitora quais tools estão falhando.
# Labels: "analyze_transactions", "search_knowledge_base", "assess_credit_profile"
TOOL_ERRORS = Counter(
    "agent_tool_errors_total",
    "Erros por tool do agente",
    ["tool_name"],
)

# Erros por modelo LLM — monitora falhas do provedor.
# Labels: "gpt-4o-mini", "gpt-4o", etc.
MODEL_ERRORS = Counter(
    "agent_model_errors_total",
    "Erros do modelo LLM",
    ["model"],
)

# Contagem de fallbacks — quando o agente não consegue responder.
# Alto valor aqui = problema de qualidade.
FALLBACK_COUNT = Counter(
    "agent_fallback_total",
    "Vezes que o agente recorreu a fallback",
)


# =============================================================================
# Histograms — distribuição de valores (latência, custo)
# =============================================================================

# Latência por request.
# Buckets definem os intervalos de medição.
# Ex: quantas requests levaram <0.5s? <1s? <5s?
REQUEST_LATENCY = Histogram(
    "agent_request_duration_seconds",
    "Latência das requisições ao agente",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Custo por request em USD.
# Permite monitorar gasto e definir alerts (ex: custo > $0.10)
ESTIMATED_COST = Histogram(
    "agent_request_cost_usd",
    "Custo estimado por request (USD)",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
)


# =============================================================================
# Estimativa de Custo
# =============================================================================

# Preços GPT-4o-mini (USD por 1 milhão de tokens) — fev/2026
# Input (prompt): mais barato porque é só leitura
# Output (resposta): mais caro porque é geração
COST_PER_1M_INPUT = 0.15    # $0.15 por 1M tokens de input
COST_PER_1M_OUTPUT = 0.60   # $0.60 por 1M tokens de output


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    """
    Estima o custo em USD para uma chamada ao LLM.

    Fórmula:
      custo = (tokens_in × preço_input + tokens_out × preço_output) / 1M

    Exemplo:
      1000 tokens in + 500 tokens out
      = (1000 × 0.15 + 500 × 0.60) / 1_000_000
      = (150 + 300) / 1_000_000
      = $0.00045

    Args:
        tokens_in: Número de tokens de entrada.
        tokens_out: Número de tokens de saída.

    Returns:
        Custo estimado em USD (arredondado para 6 casas).
    """
    cost = (tokens_in * COST_PER_1M_INPUT + tokens_out * COST_PER_1M_OUTPUT) / 1_000_000
    return round(cost, 6)
