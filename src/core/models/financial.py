"""
Modelos do contexto financeiro — dados enviados pelo BFA junto com cada request.

O BFA enriquece cada AgentRequest com dados reais do cliente (saldo, cartões,
PIX, boletos, perfil da empresa). Cada sub-contexto é independente e pode
ser null se não disponível ou se a busca falhou.

Contrato: docs/BFA_CONTRACT_v9.md §2-3
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─── Account (Conta Corrente) ────────────────────────────────────

class AccountContext(BaseModel):
    """Dados da conta corrente do cliente PJ."""

    account_id: str
    branch: str
    account_number: str
    balance: float
    available_balance: float
    overdraft_limit: float = 0.0
    credit_limit: float = 0.0
    available_credit_limit: float = 0.0
    status: str = "active"


# ─── Cards (Cartões de Crédito) ──────────────────────────────────

class CardInfo(BaseModel):
    """Dados de um cartão de crédito corporativo."""

    card_id: str
    last4: str
    brand: str
    card_type: str = "corporate"
    status: str = "active"
    credit_limit: float = 0.0
    available_limit: float = 0.0
    used_limit: float = 0.0
    due_day: int = 0
    billing_day: int = 0


class CardInvoice(BaseModel):
    """Fatura de um cartão (open, closed ou overdue)."""

    card_id: str
    reference_month: str
    total_amount: float
    minimum_payment: float
    due_date: str
    status: str = "open"


class CardsContext(BaseModel):
    """Cartões e faturas do cliente."""

    cards: list[CardInfo] = Field(default_factory=list)
    invoices: list[CardInvoice] = Field(default_factory=list)


# ─── PIX ─────────────────────────────────────────────────────────

class PixKey(BaseModel):
    """Chave PIX registrada."""

    key_type: str
    key_value: str
    status: str = "active"


class PixTransfer(BaseModel):
    """Transferência PIX realizada."""

    transfer_id: str
    amount: float
    destination_name: str
    status: str = "completed"
    funded_by: str = "balance"
    created_at: str = ""


class PixScheduledTransfer(BaseModel):
    """Transferência PIX agendada."""

    transfer_id: str
    amount: float
    destination_name: str
    scheduled_for: str
    status: str = "pending"


class PixContext(BaseModel):
    """Chaves PIX, transferências recentes e agendamentos."""

    keys: list[PixKey] = Field(default_factory=list)
    recent_transfers: list[PixTransfer] = Field(default_factory=list)
    scheduled_transfers: list[PixScheduledTransfer] = Field(default_factory=list)


# ─── Billing (Boletos e Débitos) ─────────────────────────────────

class BillPayment(BaseModel):
    """Boleto pago ou a pagar."""

    bill_id: str
    amount: float
    beneficiary: str
    due_date: str
    status: str = "completed"


class DebitPurchase(BaseModel):
    """Compra no débito."""

    amount: float
    merchant_name: str
    category: str = ""
    date: str = ""
    status: str = "completed"


class BillingContext(BaseModel):
    """Boletos pagos e compras no débito."""

    recent_bills: list[BillPayment] = Field(default_factory=list)
    recent_debits: list[DebitPurchase] = Field(default_factory=list)


# ─── Profile (Perfil da Empresa) ─────────────────────────────────

class CompanyProfile(BaseModel):
    """Perfil corporativo resumido — dados cadastrais da empresa."""

    customer_id: str
    company_name: str
    document: str
    segment: str = ""
    email: str = ""

# ─── Transactions (Transações Recentes) ───────────────

class TransactionItem(BaseModel):
    """Transação individual da conta corrente."""

    date: str
    amount: float
    type: str = ""                # bill_payment, transfer_in, pix_out, etc.
    category: str = ""
    description: str = ""
    counterparty: str = ""        # Nome da contraparte (fornecedor, cliente, etc.)


class TransactionsContext(BaseModel):
    """Transações recentes da conta corrente."""

    recent: list[TransactionItem] = Field(default_factory=list)
    count: int = 0                # Total de transações no período (pode ser > len(recent))

# ─── FinancialContext (Raiz) ─────────────────────────────────────

class FinancialContext(BaseModel):
    """
    Contexto financeiro completo enviado pelo BFA.

    Cada sub-contexto pode ser null (não disponível).
    O campo context_keys lista quais foram preenchidos com sucesso.
    """

    account: AccountContext | None = None
    cards: CardsContext | None = None
    pix: PixContext | None = None
    billing: BillingContext | None = None
    profile: CompanyProfile | None = None
    transactions: TransactionsContext | None = None
    fetched_at: str = ""
    context_keys: list[str] = Field(default_factory=list)
