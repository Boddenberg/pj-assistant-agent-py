"""
Testes unitários — modelos e formatador de contexto financeiro.

Valida:
  1. Criação dos modelos FinancialContext e sub-contextos
  2. Null safety (sub-contextos podem ser None)
  3. Formatação para texto legível pelo LLM
  4. Integração com AgentRequest (campo financial_context)
  5. ConversationTurn com financial_context_keys
"""

import pytest

from src.core.models.financial import (
    AccountContext,
    CardInfo,
    CardInvoice,
    CardsContext,
    PixKey,
    PixTransfer,
    PixScheduledTransfer,
    PixContext,
    BillPayment,
    DebitPurchase,
    BillingContext,
    CompanyProfile,
    FinancialContext,
    TransactionItem,
    TransactionsContext,
)
from src.core.models import AgentRequest, ConversationTurn
from src.agent.financial_formatter import format_financial_context


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_account() -> AccountContext:
    return AccountContext(
        account_id="acc-001",
        branch="0001",
        account_number="123456",
        balance=50_000.00,
        available_balance=50_000.00,
        overdraft_limit=0.0,
        credit_limit=100_000.00,
        available_credit_limit=50_000.00,
        status="active",
    )


@pytest.fixture
def sample_cards() -> CardsContext:
    return CardsContext(
        cards=[
            CardInfo(
                card_id="card-001",
                last4="4567",
                brand="Visa",
                card_type="corporate",
                status="active",
                credit_limit=50_000.00,
                available_limit=30_000.00,
                used_limit=20_000.00,
                due_day=15,
                billing_day=5,
            ),
        ],
        invoices=[
            CardInvoice(
                card_id="card-001",
                reference_month="2026-03",
                total_amount=20_000.00,
                minimum_payment=2_000.00,
                due_date="2026-03-15",
                status="open",
            ),
        ],
    )


@pytest.fixture
def sample_pix() -> PixContext:
    return PixContext(
        keys=[PixKey(key_type="cnpj", key_value="12.345.678/0001-90", status="active")],
        recent_transfers=[
            PixTransfer(
                transfer_id="pix-001",
                amount=1_500.00,
                destination_name="Fornecedor ABC",
                status="completed",
                created_at="2026-03-03T14:00:00Z",
            ),
        ],
        scheduled_transfers=[
            PixScheduledTransfer(
                transfer_id="pix-sch-001",
                amount=3_000.00,
                destination_name="Aluguel Sala Comercial",
                scheduled_for="2026-03-10",
                status="pending",
            ),
        ],
    )


@pytest.fixture
def sample_billing() -> BillingContext:
    return BillingContext(
        recent_bills=[
            BillPayment(
                bill_id="bill-001",
                amount=1_200.00,
                beneficiary="CEMIG",
                due_date="2026-03-10",
                status="completed",
            ),
        ],
        recent_debits=[
            DebitPurchase(
                amount=85.50,
                merchant_name="Papelaria Central",
                category="office_supplies",
                date="2026-03-02",
            ),
        ],
    )


@pytest.fixture
def sample_company_profile() -> CompanyProfile:
    return CompanyProfile(
        customer_id="cust-001",
        company_name="Tech Solutions LTDA",
        document="12.345.678/0001-90",
        segment="small_business",
        email="contato@techsolutions.com.br",
    )


@pytest.fixture
def sample_transactions() -> TransactionsContext:
    return TransactionsContext(
        recent=[
            TransactionItem(
                date="2026-03-03",
                amount=-2640.32,
                type="bill_payment",
                category="contas",
                description="Internet Fibra",
                counterparty="Vivo Fibra",
            ),
            TransactionItem(
                date="2026-03-03",
                amount=10000.00,
                type="transfer_in",
                category="devtools",
                description="DevTools — Crédito de saldo R$ 10000.00",
            ),
        ],
        count=30,
    )


@pytest.fixture
def full_financial_context(
    sample_account, sample_cards, sample_pix, sample_billing, sample_company_profile,
) -> FinancialContext:
    return FinancialContext(
        account=sample_account,
        cards=sample_cards,
        pix=sample_pix,
        billing=sample_billing,
        profile=sample_company_profile,
        fetched_at="2026-03-04T10:30:00Z",
        context_keys=["account", "cards", "pix", "billing", "profile"],
    )


# ═══════════════════════════════════════════════════════════════════
# Testes dos modelos
# ═══════════════════════════════════════════════════════════════════

class TestFinancialModels:
    """Testes de criação e validação dos modelos de contexto financeiro."""

    def test_account_context(self, sample_account):
        assert sample_account.balance == 50_000.00
        assert sample_account.status == "active"

    def test_cards_context(self, sample_cards):
        assert len(sample_cards.cards) == 1
        assert sample_cards.cards[0].last4 == "4567"
        assert len(sample_cards.invoices) == 1
        assert sample_cards.invoices[0].status == "open"

    def test_pix_context(self, sample_pix):
        assert len(sample_pix.keys) == 1
        assert sample_pix.keys[0].key_type == "cnpj"
        assert len(sample_pix.recent_transfers) == 1
        assert len(sample_pix.scheduled_transfers) == 1

    def test_billing_context(self, sample_billing):
        assert len(sample_billing.recent_bills) == 1
        assert sample_billing.recent_bills[0].beneficiary == "CEMIG"
        assert len(sample_billing.recent_debits) == 1

    def test_company_profile(self, sample_company_profile):
        assert sample_company_profile.company_name == "Tech Solutions LTDA"
        assert sample_company_profile.document == "12.345.678/0001-90"

    def test_transactions_context(self, sample_transactions):
        assert len(sample_transactions.recent) == 2
        assert sample_transactions.count == 30
        assert sample_transactions.recent[0].amount == -2640.32
        assert sample_transactions.recent[0].counterparty == "Vivo Fibra"
        assert sample_transactions.recent[1].amount == 10000.00
        assert sample_transactions.recent[1].type == "transfer_in"

    def test_financial_context_full(self, full_financial_context):
        ctx = full_financial_context
        assert ctx.account is not None
        assert ctx.cards is not None
        assert ctx.pix is not None
        assert ctx.billing is not None
        assert ctx.profile is not None
        assert len(ctx.context_keys) == 5

    def test_financial_context_partial(self, sample_account):
        """Contexto parcial — apenas account e profile."""
        ctx = FinancialContext(
            account=sample_account,
            context_keys=["account"],
        )
        assert ctx.account is not None
        assert ctx.cards is None
        assert ctx.pix is None
        assert ctx.billing is None
        assert ctx.profile is None

    def test_financial_context_null(self):
        """Contexto totalmente vazio — cliente anonymous."""
        ctx = FinancialContext()
        assert ctx.account is None
        assert ctx.context_keys == []


# ═══════════════════════════════════════════════════════════════════
# Testes do formatador
# ═══════════════════════════════════════════════════════════════════

class TestFinancialFormatter:
    """Testes da função format_financial_context."""

    def test_format_none_returns_empty(self):
        assert format_financial_context(None) == ""

    def test_format_empty_context_returns_empty(self):
        ctx = FinancialContext()
        assert format_financial_context(ctx) == ""

    def test_format_full_context(self, full_financial_context):
        result = format_financial_context(full_financial_context)

        assert "## Dados financeiros do cliente" in result
        assert "### Conta Corrente" in result
        assert "50,000.00" in result
        assert "### Cartões de Crédito" in result
        assert "4567" in result
        assert "### PIX" in result
        assert "Fornecedor ABC" in result
        assert "### Boletos e Débitos" in result
        assert "CEMIG" in result
        assert "### Perfil da Empresa" in result
        assert "Tech Solutions LTDA" in result

    def test_format_account_only(self, sample_account):
        ctx = FinancialContext(account=sample_account, context_keys=["account"])
        result = format_financial_context(ctx)

        assert "### Conta Corrente" in result
        assert "50,000.00" in result
        assert "### Cartões" not in result
        assert "### PIX" not in result

    def test_format_cards_shows_invoice(self, sample_cards):
        ctx = FinancialContext(cards=sample_cards, context_keys=["cards"])
        result = format_financial_context(ctx)

        assert "Visa final 4567" in result
        assert "Fatura 2026-03" in result
        assert "20,000.00" in result

    def test_format_pix_shows_all_sections(self, sample_pix):
        ctx = FinancialContext(pix=sample_pix, context_keys=["pix"])
        result = format_financial_context(ctx)

        assert "cnpj: 12.345.678/0001-90" in result
        assert "Fornecedor ABC" in result
        assert "Aluguel Sala Comercial" in result

    def test_format_billing(self, sample_billing):
        ctx = FinancialContext(billing=sample_billing, context_keys=["billing"])
        result = format_financial_context(ctx)

        assert "CEMIG" in result
        assert "Papelaria Central" in result

    def test_format_transactions(self, sample_transactions):
        ctx = FinancialContext(
            transactions=sample_transactions,
            context_keys=["transactions"],
        )
        result = format_financial_context(ctx)

        assert "### Transações Recentes (30 no período)" in result
        assert "Vivo Fibra" in result
        assert "Internet Fibra" in result
        assert "-R$ 2,640.32" in result
        assert "+R$ 10,000.00" in result

    def test_format_transactions_without_counterparty(self):
        ctx = FinancialContext(
            transactions=TransactionsContext(
                recent=[TransactionItem(
                    date="2026-03-03",
                    amount=500.00,
                    description="Crédito",
                )],
                count=1,
            ),
            context_keys=["transactions"],
        )
        result = format_financial_context(ctx)
        assert "— Crédito" in result
        # Não deve ter counterparty se vazio
        assert "\u2014  \u2014" not in result


# ═══════════════════════════════════════════════════════════════════
# Testes de integração com modelos existentes
# ═══════════════════════════════════════════════════════════════════

class TestFinancialContextIntegration:
    """Testes de integração com AgentRequest e ConversationTurn."""

    def test_request_without_financial_context(self):
        """Request sem financial_context (backwards compatible)."""
        r = AgentRequest(query="Olá")
        assert r.financial_context is None

    def test_request_with_financial_context(self, full_financial_context):
        """Request com financial_context completo."""
        r = AgentRequest(
            query="Qual meu saldo?",
            customer_id="cust-001",
            financial_context=full_financial_context,
        )
        assert r.financial_context is not None
        assert r.financial_context.account is not None
        assert r.financial_context.account.balance == 50_000.00

    def test_request_with_null_financial_context(self):
        """Request com financial_context=null (anonymous)."""
        r = AgentRequest(query="Como abrir conta?", financial_context=None)
        assert r.financial_context is None

    def test_conversation_turn_with_financial_keys(self):
        """ConversationTurn com financial_context_keys."""
        turn = ConversationTurn(
            query="qual meu saldo?",
            answer="Seu saldo é R$ 50.000,00",
            financial_context_keys=["account", "cards"],
        )
        assert turn.financial_context_keys == ["account", "cards"]

    def test_conversation_turn_without_financial_keys(self):
        """ConversationTurn sem financial_context_keys (backwards compatible)."""
        turn = ConversationTurn(query="oi", answer="Olá!")
        assert turn.financial_context_keys == []
