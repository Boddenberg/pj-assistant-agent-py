"""
Formatador de contexto financeiro — converte FinancialContext em texto para o LLM.

Gera um resumo legível dos dados financeiros do cliente para injetar
no prompt do agente. Cada sub-contexto é formatado separadamente.
Se o sub-contexto for None, é ignorado silenciosamente.
"""

from __future__ import annotations

from src.core.models.financial import FinancialContext


def format_financial_context(ctx: FinancialContext | None) -> str:
    """
    Converte FinancialContext em texto para o prompt do LLM.

    Retorna string vazia se ctx for None ou não tiver dados.
    """
    if not ctx or not ctx.context_keys:
        return ""

    sections: list[str] = []

    if ctx.account:
        sections.append(_format_account(ctx))

    if ctx.cards:
        sections.append(_format_cards(ctx))

    if ctx.pix:
        sections.append(_format_pix(ctx))

    if ctx.billing:
        sections.append(_format_billing(ctx))

    if ctx.profile:
        sections.append(_format_profile(ctx))

    if ctx.transactions:
        sections.append(_format_transactions(ctx))

    if not sections:
        return ""

    header = "## Dados financeiros do cliente (contexto real — use para responder)"
    return header + "\n\n" + "\n\n".join(sections)


# ─── Formatadores por sub-contexto ───────────────────────────────

def _format_account(ctx: FinancialContext) -> str:
    acc = ctx.account
    if not acc:
        return ""
    return (
        "### Conta Corrente\n"
        f"- Agência: {acc.branch} | Conta: {acc.account_number}\n"
        f"- Saldo: R$ {acc.balance:,.2f}\n"
        f"- Saldo disponível: R$ {acc.available_balance:,.2f}\n"
        f"- Limite de crédito: R$ {acc.credit_limit:,.2f}\n"
        f"- Limite de crédito disponível: R$ {acc.available_credit_limit:,.2f}\n"
        f"- Status: {acc.status}"
    )


def _format_cards(ctx: FinancialContext) -> str:
    cards_ctx = ctx.cards
    if not cards_ctx:
        return ""

    lines = ["### Cartões de Crédito"]

    for card in cards_ctx.cards:
        lines.append(
            f"- {card.brand} final {card.last4} ({card.card_type}) — "
            f"limite R$ {card.credit_limit:,.2f}, "
            f"disponível R$ {card.available_limit:,.2f}, "
            f"usado R$ {card.used_limit:,.2f} | "
            f"vencimento dia {card.due_day} | status: {card.status}"
        )

    for inv in cards_ctx.invoices:
        lines.append(
            f"- Fatura {inv.reference_month}: R$ {inv.total_amount:,.2f} "
            f"(mínimo R$ {inv.minimum_payment:,.2f}), "
            f"vence {inv.due_date}, status: {inv.status}"
        )

    return "\n".join(lines)


def _format_pix(ctx: FinancialContext) -> str:
    pix = ctx.pix
    if not pix:
        return ""

    lines = ["### PIX"]

    if pix.keys:
        keys_str = ", ".join(f"{k.key_type}: {k.key_value}" for k in pix.keys)
        lines.append(f"- Chaves: {keys_str}")

    for t in pix.recent_transfers:
        lines.append(
            f"- PIX enviado: R$ {t.amount:,.2f} → {t.destination_name} "
            f"({t.status}, {t.created_at})"
        )

    for s in pix.scheduled_transfers:
        lines.append(
            f"- PIX agendado: R$ {s.amount:,.2f} → {s.destination_name} "
            f"em {s.scheduled_for} ({s.status})"
        )

    return "\n".join(lines)


def _format_billing(ctx: FinancialContext) -> str:
    billing = ctx.billing
    if not billing:
        return ""

    lines = ["### Boletos e Débitos"]

    for b in billing.recent_bills:
        lines.append(
            f"- Boleto: R$ {b.amount:,.2f} — {b.beneficiary}, "
            f"vencimento {b.due_date}, status: {b.status}"
        )

    for d in billing.recent_debits:
        lines.append(
            f"- Débito: R$ {d.amount:,.2f} — {d.merchant_name} "
            f"({d.category}), {d.date}"
        )

    return "\n".join(lines)


def _format_profile(ctx: FinancialContext) -> str:
    p = ctx.profile
    if not p:
        return ""
    return (
        "### Perfil da Empresa\n"
        f"- Empresa: {p.company_name}\n"
        f"- CNPJ: {p.document}\n"
        f"- Segmento: {p.segment}\n"
        f"- Email: {p.email}"
    )


def _format_transactions(ctx: FinancialContext) -> str:
    txn = ctx.transactions
    if not txn or not txn.recent:
        return ""

    lines = [f"### Transações Recentes ({txn.count} no período)"]

    for t in txn.recent:
        sign = "+" if t.amount >= 0 else "-"
        abs_amount = abs(t.amount)
        counterparty = f" — {t.counterparty}" if t.counterparty else ""
        category = f" ({t.category})" if t.category else ""
        lines.append(
            f"- {t.date}: {sign}R$ {abs_amount:,.2f}{counterparty}{category} — {t.description}"
        )

    return "\n".join(lines)
