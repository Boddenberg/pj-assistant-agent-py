"""
Fixtures compartilhadas para testes.

O conftest.py é automaticamente descoberto pelo pytest.
Todas as fixtures definidas aqui ficam disponíveis para TODOS os testes
sem necessidade de import explícito.

Organização das fixtures:
  - sample_profile      → perfil de cliente PJ para testes
  - sample_transactions → lista de transações variadas
  - sample_request      → request completa (profile + transactions + query)

Essas fixtures simulam o payload que o BFA (Go) envia para o agente.
São dados fictícios mas realistas — representam uma empresa de médio porte
com operações típicas (fornecedores, vendas, folha, impostos).

Por que fixtures?
  - Evita duplicação de dados de teste
  - Garante consistência entre testes
  - Facilita manutenção (muda em um lugar, reflete em todos)
"""

import pytest

from src.core.models import CustomerProfile, Transaction, AgentRequest


# =============================================================================
# Fixture: Perfil do cliente PJ
# =============================================================================

@pytest.fixture
def sample_profile() -> CustomerProfile:
    """
    Perfil de um cliente PJ fictício.

    Dados simulam uma empresa de médio porte:
      - Score 720 → risco baixo (>= 700)
      - Segmento "Médias Empresas" → atendimento diferenciado
      - Faturamento R$ 1M - R$ 10M → elegível para crédito PJ
      - Cliente desde 2019 → relacionamento estabelecido
    """
    return CustomerProfile(
        customer_id="cust-001",
        company_name="Acme Ltda",
        segment="Médias Empresas",
        revenue_range="R$ 1M - R$ 10M",
        account_since="2019-03-15",
        credit_score=720,
    )


# =============================================================================
# Fixture: Lista de transações
# =============================================================================

@pytest.fixture
def sample_transactions() -> list[Transaction]:
    """
    Lista de transações variadas para testes.

    Transações cobrem diferentes categorias:
      - Fornecedores (saída) → pagamento de insumos
      - Vendas (entrada)     → recebimento de clientes
      - Folha (saída)        → salários
      - Impostos (saída)     → tributos

    Valores negativos = saída (pagamento)
    Valores positivos = entrada (recebimento)

    Total: -5000 + 15000 - 2500 - 800 + 8000 = R$ 14.700,00
    """
    return [
        Transaction(
            id="t1",
            date="2026-01-15",
            amount=-5000.00,
            category="Fornecedores",
            description="Pagamento fornecedor A",
        ),
        Transaction(
            id="t2",
            date="2026-01-20",
            amount=15000.00,
            category="Vendas",
            description="Recebimento cliente X",
        ),
        Transaction(
            id="t3",
            date="2026-02-01",
            amount=-2500.00,
            category="Folha",
            description="Salários",
        ),
        Transaction(
            id="t4",
            date="2026-02-05",
            amount=-800.00,
            category="Impostos",
            description="DAS",
        ),
        Transaction(
            id="t5",
            date="2026-02-10",
            amount=8000.00,
            category="Vendas",
            description="Recebimento cliente Y",
        ),
    ]


# =============================================================================
# Fixture: Request completa do BFA
# =============================================================================

@pytest.fixture
def sample_request(sample_profile, sample_transactions) -> AgentRequest:
    """
    Request completa que simula o que o BFA envia.

    Combina profile + transactions + query.
    A query é uma pergunta aberta sobre situação financeira
    — exercita o fluxo completo do agente.
    """
    return AgentRequest(
        customer_id="cust-001",
        profile=sample_profile,
        transactions=sample_transactions,
        query="Qual é minha situação financeira e o que posso melhorar?",
    )
