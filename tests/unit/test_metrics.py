"""
Testes unitários — métricas e estimativa de custo.

Testa a função estimate_cost() que calcula o custo em USD
para cada chamada ao LLM baseado no número de tokens.

Fórmula:
  custo = (tokens_in × $0.15 + tokens_out × $0.60) / 1.000.000

Por que testar?
  - O custo é usado para o circuit breaker (MAX_COST_PER_REQUEST)
  - Erro no cálculo = gastar mais do que deveria
  - Em produção, esse valor aparece em dashboards e alertas

Nota: NÃO testamos os objetos Counter/Histogram do Prometheus aqui
porque eles são singletons globais que interferem entre testes.
Testamos apenas a lógica pura (estimate_cost).
"""

from src.observability.metrics import estimate_cost


class TestEstimateCost:
    """Testes da função estimate_cost."""

    def test_zero_tokens(self):
        """0 tokens = $0.00 — caso base."""
        assert estimate_cost(0, 0) == 0.0

    def test_known_cost(self):
        """Calcula custo para 1000 tokens in + 1000 tokens out.

        Matemática:
          input:  1000 × 0.15 = 150
          output: 1000 × 0.60 = 600
          total:  (150 + 600) / 1.000.000 = $0.00075
        """
        cost = estimate_cost(1000, 1000)
        assert cost == 0.00075

    def test_large_request(self):
        """Request grande deve ter custo > 0 e ser float.

        10k input + 4k output é um request típico com RAG:
          input:  10000 × 0.15 = 1500
          output: 4000  × 0.60 = 2400
          total:  3900 / 1.000.000 = $0.0039
        """
        cost = estimate_cost(10_000, 4_000)
        assert cost > 0
        assert isinstance(cost, float)
