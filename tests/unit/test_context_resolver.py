"""
Testes do Context Resolver — fluxo de duas chamadas BFA ↔ Agente.

Cobertura:
  - resolve_required_contexts: mapeamento keyword → contextos
  - needs_financial_context: detecção de queries financeiras
  - build_context_request: resposta intermediária para o BFA
  - Integração com AgentResponse.required_contexts
"""

import pytest

from src.agent.context_resolver import (
    resolve_required_contexts,
    needs_financial_context,
    build_context_request,
    VALID_CONTEXTS,
)
from src.core.models.contracts import AgentResponse


# ═════════════════════════════════════════════════════════════════
# resolve_required_contexts — keyword → contextos
# ═════════════════════════════════════════════════════════════════

class TestResolveRequiredContexts:
    """Testa mapeamento de queries para contextos financeiros."""

    # ── Account ──────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Qual meu saldo?",
        "Quanto tenho na conta corrente?",
        "Qual meu saldo disponível?",
        "Quero ver meu cheque especial",
    ])
    def test_account_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "account" in result

    # ── Cards ────────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Me mostra meus cartões",
        "Qual o limite do meu cartão?",
        "Quero ver minha fatura",
        "Cartão de crédito corporativo",
    ])
    def test_cards_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "cards" in result

    # ── PIX ──────────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Quero fazer um PIX",
        "Me mostra minhas transferências",
        "Qual minha chave pix?",
        "Quero enviar pix",
        "Agendar pix para amanhã",
    ])
    def test_pix_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "pix" in result
        assert "account" in result  # PIX sempre inclui account

    # ── Billing ──────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Tenho boleto pra pagar",
        "Me mostra meus pagamentos",
        "Pagar boleto",
        "Ver cobrança",
    ])
    def test_billing_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "billing" in result

    # ── Profile ──────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Quero ver meus dados",
        "Qual o CNPJ da minha empresa?",
        "Me mostra a razão social",
        "Quero ver meu perfil",
        "Meu cadastro está atualizado?",
    ])
    def test_profile_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "profile" in result

    # ── Analytics ─────────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Me dá um resumo financeiro",
        "Quero ver uma visão geral",
        "Análise das minhas despesas",
        "Quais são meus gastos?",
    ])
    def test_analytics_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "analytics" in result
        assert "account" in result  # Analytics inclui account
        assert "transactions" in result  # Analytics inclui transactions

    # ── Transactions ──────────────────────────────────────────────

    @pytest.mark.parametrize("query", [
        "Me mostra o extrato",
        "Quero ver minhas transações",
        "Quais foram as últimas transações?",
        "Me mostra as movimentações",
        "Histórico de transações",
    ])
    def test_transactions_queries(self, query: str):
        result = resolve_required_contexts(query)
        assert "transactions" in result
        assert "account" in result  # Transactions sempre inclui account

    # ── Sem contexto (saudação, dúvida geral, onboarding) ───────

    @pytest.mark.parametrize("query", [
        "Oi, tudo bem?",
        "Olá!",
        "Como abrir uma conta PJ?",
        "Quais documentos preciso para abrir conta?",
        "Obrigado!",
        "O que vocês oferecem?",
    ])
    def test_no_financial_context_needed(self, query: str):
        result = resolve_required_contexts(query)
        assert result == []

    # ── Múltiplos contextos ──────────────────────────────────────

    def test_multiple_contexts_pix_and_cards(self):
        """Query que menciona PIX e cartão → inclui ambos."""
        result = resolve_required_contexts("Quero ver meu saldo e meus cartões")
        assert "account" in result
        assert "cards" in result

    def test_result_is_sorted(self):
        """Contextos retornados devem estar ordenados (determinístico)."""
        result = resolve_required_contexts("Me mostra PIX e cartões e boletos")
        assert result == sorted(result)

    def test_all_returned_are_valid(self):
        """Todos os contextos retornados devem ser válidos."""
        result = resolve_required_contexts("Resumo financeiro completo com tudo")
        for ctx in result:
            assert ctx in VALID_CONTEXTS


# ═════════════════════════════════════════════════════════════════
# needs_financial_context
# ═════════════════════════════════════════════════════════════════

class TestNeedsFinancialContext:
    """Testa se detecção binária (precisa/não precisa) funciona."""

    def test_financial_query_returns_true(self):
        assert needs_financial_context("Qual meu saldo?") is True

    def test_greeting_returns_false(self):
        assert needs_financial_context("Oi!") is False

    def test_knowledge_base_returns_false(self):
        assert needs_financial_context("Como funciona abertura de conta?") is False


# ═════════════════════════════════════════════════════════════════
# build_context_request — resposta intermediária
# ═════════════════════════════════════════════════════════════════

class TestBuildContextRequest:
    """Testa construção da resposta de 1ª chamada."""

    def test_returns_agent_response(self):
        resp = build_context_request("Qual meu saldo?", "cust-001")
        assert isinstance(resp, AgentResponse)

    def test_has_required_contexts(self):
        resp = build_context_request("Qual meu saldo?", "cust-001")
        assert "account" in resp.required_contexts

    def test_answer_is_empty(self):
        """Na 1ª chamada, answer é vazio (BFA não exibe)."""
        resp = build_context_request("Qual meu saldo?", "cust-001")
        assert resp.answer == ""

    def test_intent_is_awaiting_context(self):
        resp = build_context_request("Qual meu saldo?", "cust-001")
        assert resp.intent == "awaiting_context"

    def test_zero_tokens(self):
        """1ª chamada é determinística — zero tokens."""
        resp = build_context_request("Qual meu saldo?", "cust-001")
        assert resp.metadata.tokens_used == 0
        assert resp.metadata.estimated_cost_usd == 0.0

    def test_customer_id_preserved(self):
        resp = build_context_request("Qual meu saldo?", "cust-abc")
        assert resp.customer_id == "cust-abc"

    def test_pix_includes_account(self):
        """PIX sempre precisa de account (saldo disponível)."""
        resp = build_context_request("Quero fazer um PIX", "cust-001")
        assert "pix" in resp.required_contexts
        assert "account" in resp.required_contexts


# ═════════════════════════════════════════════════════════════════
# AgentResponse.required_contexts — campo no modelo
# ═════════════════════════════════════════════════════════════════

class TestAgentResponseRequiredContexts:
    """Testa o campo required_contexts no modelo AgentResponse."""

    def test_default_is_empty_list(self):
        resp = AgentResponse(customer_id="x", answer="Oi!")
        assert resp.required_contexts == []

    def test_serialization(self):
        resp = AgentResponse(
            customer_id="x",
            answer="",
            required_contexts=["account", "pix"],
        )
        data = resp.model_dump(mode="json")
        assert data["required_contexts"] == ["account", "pix"]

    def test_final_response_has_empty_required_contexts(self):
        """Resposta final (2ª chamada) tem required_contexts vazio."""
        resp = AgentResponse(
            customer_id="x",
            answer="Seu saldo é R$ 1.000,00",
            required_contexts=[],  # Resposta final
        )
        assert resp.required_contexts == []
