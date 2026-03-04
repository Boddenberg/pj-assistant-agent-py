"""
Testes unitários — Auth Guard.

Valida:
  1. Detecção de keywords que requerem autenticação
  2. Respostas de redirecionamento por tema (PIX, cartão, saldo, boleto)
  3. Integração com AgentRequest.is_authenticated
  4. Queries que NÃO requerem auth (onboarding, saudação)
"""

import pytest

from src.agent.auth_guard import requires_auth, build_auth_redirect, _detect_topic
from src.core.models import AgentRequest


# ═══════════════════════════════════════════════════════════════════
# requires_auth — detecção de keywords de app
# ═══════════════════════════════════════════════════════════════════

class TestRequiresAuth:
    """Testa se keywords de funcionalidades do app são corretamente detectadas."""

    @pytest.mark.parametrize("query", [
        "Qual meu saldo?",
        "Quero fazer um PIX",
        "Me mostra o extrato",
        "Qual a fatura do meu cartão?",
        "Quero pagar um boleto",
        "Quanto tenho disponível?",
        "Quero transferir dinheiro",
        "Qual o limite do meu cartão?",
        "Meus dados cadastrais",
        "Quero alterar minha senha",
        "Me mostra meu resumo financeiro",
    ])
    def test_app_queries_require_auth(self, query):
        assert requires_auth(query) is True

    @pytest.mark.parametrize("query", [
        "Quero abrir uma conta PJ",
        "Como funciona a abertura de conta?",
        "Olá, bom dia",
        "Obrigado pela ajuda",
        "Quais os tipos de conta?",
        "O que é o Itaú PJ?",
    ])
    def test_non_app_queries_dont_require_auth(self, query):
        assert requires_auth(query) is False


# ═══════════════════════════════════════════════════════════════════
# _detect_topic — classificação de tema para redirect
# ═══════════════════════════════════════════════════════════════════

class TestDetectTopic:
    """Testa classificação de tema para escolher resposta de redirect."""

    def test_pix_topic(self):
        assert _detect_topic("quero fazer um pix") == "pix"

    def test_card_topic(self):
        assert _detect_topic("qual a fatura do cartão?") == "cartao"

    def test_balance_topic(self):
        assert _detect_topic("qual meu saldo?") == "saldo"

    def test_bill_topic(self):
        assert _detect_topic("quero pagar um boleto") == "boleto"

    def test_unknown_topic_returns_default(self):
        assert _detect_topic("meus dados cadastrais") == "default"


# ═══════════════════════════════════════════════════════════════════
# build_auth_redirect — resposta de redirecionamento
# ═══════════════════════════════════════════════════════════════════

class TestBuildAuthRedirect:
    """Testa geração de respostas de redirecionamento."""

    def test_pix_redirect_mentions_pix(self):
        response = build_auth_redirect("quero fazer um pix", "anon-001")
        assert "PIX" in response.answer
        assert "conta" in response.answer.lower()
        assert response.context == "onboarding"
        assert response.intent == "open_account"
        assert response.confidence == 1.0

    def test_card_redirect_mentions_cartao(self):
        response = build_auth_redirect("qual meu cartão?", "anon-002")
        assert "cartõ" in response.answer.lower() or "conta" in response.answer.lower()
        assert response.context == "onboarding"

    def test_balance_redirect_mentions_saldo(self):
        response = build_auth_redirect("qual meu saldo?", "anon-003")
        assert "saldo" in response.answer.lower() or "conta" in response.answer.lower()

    def test_redirect_has_suggested_actions(self):
        response = build_auth_redirect("quero pagar boleto", "anon-004")
        assert len(response.suggested_actions) > 0
        assert "Abrir conta PJ" in response.suggested_actions

    def test_redirect_zero_cost(self):
        """Redirect é determinístico — zero tokens, zero custo."""
        response = build_auth_redirect("extrato", "anon-005")
        assert response.metadata.tokens_used == 0
        assert response.metadata.estimated_cost_usd == 0.0


# ═══════════════════════════════════════════════════════════════════
# Integração com AgentRequest
# ═══════════════════════════════════════════════════════════════════

class TestAuthRequestIntegration:
    """Testa integração do campo is_authenticated com AgentRequest."""

    def test_default_is_not_authenticated(self):
        r = AgentRequest(query="Olá")
        assert r.is_authenticated is False

    def test_authenticated_flag(self):
        r = AgentRequest(query="Qual meu saldo?", is_authenticated=True)
        assert r.is_authenticated is True

    def test_anonymous_not_authenticated(self):
        r = AgentRequest(query="Quero abrir conta", customer_id="anonymous")
        assert r.is_authenticated is False
        assert r.customer_id == "anonymous"
