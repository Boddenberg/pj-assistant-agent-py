"""
Testes unitários — modelos de domínio.

Testa os modelos Pydantic que definem o contrato entre BFA e Agente.

O que validamos:
  1. Criação de modelos com dados válidos
  2. Valores default (campos opcionais)
  3. Timestamp automático no response
  4. Enum StepType nos reasoning steps

Por que testar modelos?
  - São o contrato da API — se quebrarem, o BFA quebra junto
  - Defaults incorretos causam bugs silenciosos
  - Validação do Pydantic é part da lógica de negócio
"""

import pytest
from src.core.models import (
    CustomerProfile,
    Transaction,
    AgentRequest,
    AgentResponse,
    AgentStep,
    StepType,
)


class TestCustomerProfile:
    """Testes do modelo CustomerProfile."""

    def test_create_profile(self, sample_profile):
        """Perfil com todos os campos deve ser criado corretamente."""
        assert sample_profile.customer_id == "cust-001"
        assert sample_profile.credit_score == 720

    def test_profile_defaults(self):
        """Campos opcionais devem ter defaults seguros."""
        # Apenas customer_id e company_name são obrigatórios
        p = CustomerProfile(customer_id="x", company_name="Test")

        # Todos os outros campos devem ter defaults
        assert p.segment == ""
        assert p.credit_score == 0


class TestTransaction:
    """Testes do modelo Transaction."""

    def test_create_transaction(self):
        """Transação com campos mínimos deve funcionar."""
        t = Transaction(
            id="t1",
            date="2026-01-01",
            amount=100.0,
            category="Vendas",
        )
        assert t.amount == 100.0
        # description é opcional e tem default vazio
        assert t.description == ""


class TestAgentRequest:
    """Testes do modelo AgentRequest (entrada do agente)."""

    def test_full_request(self, sample_request):
        """Request completa (com profile e transactions) deve funcionar."""
        assert sample_request.customer_id == "cust-001"
        assert sample_request.profile is not None
        assert len(sample_request.transactions) == 5

    def test_minimal_request(self):
        """
        Request mínima (somente query) deve funcionar.

        Cenário: o front-end envia apenas a pergunta, sem contexto de perfil.
        O agente deve aceitar e usar defaults seguros:
          - customer_id = "anonymous"
          - profile = None
          - transactions = lista vazia
        """
        r = AgentRequest(query="Quais as taxas do Itaú?")

        assert r.query == "Quais as taxas do Itaú?"
        assert r.customer_id == "anonymous"
        assert r.profile is None
        assert r.transactions == []


class TestAgentResponse:
    """Testes do modelo AgentResponse (saída do agente)."""

    def test_response_has_timestamp(self):
        """Response deve gerar timestamp automaticamente."""
        r = AgentResponse(customer_id="x", answer="test")

        # Timestamp é gerado por default_factory (datetime.now)
        assert r.timestamp is not None

        # Tokens default = 0 (ainda não processou nada)
        assert r.tokens_used == 0

    def test_response_with_steps(self):
        """Response com reasoning steps deve preservar a sequência."""
        step = AgentStep(
            step=StepType.PLAN,
            detail="test",
            duration_ms=10.0,
        )
        r = AgentResponse(
            customer_id="x",
            answer="ok",
            reasoning=[step],
        )

        # Deve ter exatamente 1 step do tipo PLAN
        assert len(r.reasoning) == 1
        assert r.reasoning[0].step == StepType.PLAN
