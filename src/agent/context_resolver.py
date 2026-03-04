"""
Context Resolver — identifica quais contextos financeiros o BFA deve buscar.

Fluxo de duas chamadas (BFA ↔ Agente):
  1ª chamada: BFA envia query SEM financial_context
              → Agente analisa e retorna required_contexts
  2ª chamada: BFA busca só os contextos necessários no Supabase e reenvia
              → Agente responde com os dados

Isso evita que o BFA busque todos os 6 contextos (account, cards, pix,
billing, profile, analytics) em toda requisição — reduz latência e carga.

A resolução é determinística (keyword-based): zero tokens, zero custo.
"""

from __future__ import annotations

from src.core.models.contracts import AgentResponse
from src.core.models.agent import AgentMetadata


# ─── Mapeamento keyword → contextos necessários ─────────────────
# Cada regra: (keywords, contexts_to_fetch)
# Se QUALQUER keyword bate, todos os contexts daquela regra são incluídos.

_CONTEXT_RULES: list[tuple[list[str], list[str]]] = [
    # Saldo / Conta corrente
    (
        ["saldo", "conta corrente", "agência", "agencia",
         "balanço", "balanco", "disponível", "disponivel", "quanto tenho",
         "minha conta", "cheque especial"],
        ["account"],
    ),
    # Cartões de crédito
    (
        ["cartão", "cartao", "cartões", "cartoes", "fatura",
         "limite do cartão", "limite do cartao", "crédito corporativo",
         "credito corporativo", "vencimento do cartão", "vencimento do cartao"],
        ["cards"],
    ),
    # PIX (também inclui account para contexto de saldo)
    (
        ["pix", "transferir", "transferência", "transferencia",
         "chave pix", "enviar pix", "agendar pix"],
        ["pix", "account"],
    ),
    # Boletos / Pagamentos
    (
        ["boleto", "pagamento", "débito automático", "debito automatico",
         "cobrança", "cobranca", "pagar conta", "pagar boleto"],
        ["billing", "account"],
    ),
    # Perfil da empresa
    (
        ["perfil", "meus dados", "meu cadastro", "cnpj", "razão social",
         "razao social", "segmento", "dados da empresa", "meu perfil"],
        ["profile"],
    ),
    # Analytics / Visão geral (precisa de tudo)
    (
        ["resumo financeiro", "visão geral", "visao geral", "análise",
         "analise", "gastos", "despesas", "relatório", "relatorio"],
        ["analytics", "account", "cards", "billing", "transactions"],
    ),
    # Transações / Extrato / Movimentações
    (
        ["transações", "transacoes", "movimentações", "movimentacoes",
         "últimas transações", "ultimas transacoes", "histórico de transações",
         "historico de transacoes", "extrato"],
        ["transactions", "account"],
    ),
]

# Contextos válidos que o BFA sabe buscar
VALID_CONTEXTS = frozenset({"account", "cards", "pix", "billing", "profile", "analytics", "transactions"})


def resolve_required_contexts(query: str) -> list[str]:
    """
    Analisa a query e retorna quais contextos financeiros o BFA deve buscar.

    Retorna lista vazia se a query não precisa de dados financeiros
    (saudação, dúvida geral, onboarding, etc.).

    Exemplos:
        "Qual meu saldo?" → ["account"]
        "Me mostra meus cartões" → ["cards"]
        "Faz um PIX" → ["account", "pix"]
        "Oi, tudo bem?" → []
        "Como abrir conta?" → []
    """
    q = query.lower().strip()

    contexts: set[str] = set()

    for keywords, required in _CONTEXT_RULES:
        for kw in keywords:
            if kw in q:
                contexts.update(required)
                break  # Próxima regra (não precisa checar mais keywords desta)

    return sorted(contexts)


def needs_financial_context(query: str) -> bool:
    """Retorna True se a query precisa de dados financeiros do BFA."""
    return bool(resolve_required_contexts(query))


def build_context_request(query: str, customer_id: str) -> AgentResponse:
    """
    Monta resposta de 1ª chamada: diz ao BFA quais contextos buscar.

    Esta é uma resposta intermediária — o BFA NÃO exibe ao cliente.
    O BFA usa required_contexts para buscar no Supabase e faz a 2ª chamada.
    """
    contexts = resolve_required_contexts(query)

    return AgentResponse(
        customer_id=customer_id,
        answer="",  # Sem resposta visível — chamada intermediária
        context=None,
        intent="awaiting_context",
        confidence=1.0,
        suggested_actions=[],
        required_contexts=contexts,
        metadata=AgentMetadata(
            reasoning=[],
            sources=[],
            tokens_used=0,
            estimated_cost_usd=0.0,
        ),
    )
