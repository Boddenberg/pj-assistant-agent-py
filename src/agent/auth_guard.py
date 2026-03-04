"""
Auth Guard — guardrail de autenticação para o agente.

Verifica se a combinação (is_authenticated, intent) é permitida
e gera respostas de redirecionamento quando necessário.

Regras de negócio:
  - NÃO autenticado → só pode falar sobre abertura de conta e dúvidas gerais
  - NÃO autenticado + pergunta sobre app (PIX, saldo, cartão...) → redireciona para onboarding
  - Autenticado → acesso completo ao app, NÃO redireciona para onboarding
"""

from __future__ import annotations

from src.core.models.contracts import AgentResponse
from src.core.models.agent import AgentMetadata


# ─── Keywords que indicam assunto de app (requer autenticação) ───

_APP_KEYWORDS: list[str] = [
    # Saldo / Conta
    "saldo", "extrato", "disponível", "disponivel",
    "quanto tenho", "minha conta",
    # PIX
    "pix", "transferir", "transferência", "transferencia",
    "chave pix", "enviar pix", "agendar pix",
    # Cartão
    "cartão", "cartao", "fatura", "limite do cartão",
    "limite do cartao", "vencimento",
    # Boleto / Pagamento
    "boleto", "pagar", "pagamento", "débito", "debito",
    # Perfil / Cadastro
    "meus dados", "meu cadastro", "alterar senha", "senha",
    "atualizar cadastro", "meu perfil",
    # Financeiro geral
    "crédito", "credito", "empréstimo", "emprestimo",
    "orçamento", "orcamento", "resumo financeiro",
]

# ─── Respostas de redirecionamento por tema ──────────────────────

_REDIRECT_RESPONSES: dict[str, str] = {
    "pix": (
        "Para usar o PIX, você precisa ter uma conta aberta no Itaú PJ. 😊\n\n"
        "Quer abrir sua conta agora? É rápido e 100% digital!"
    ),
    "cartao": (
        "Para consultar ou solicitar cartões, você precisa ter uma conta PJ ativa. 💳\n\n"
        "Que tal abrir sua conta? Posso te ajudar com isso agora!"
    ),
    "saldo": (
        "Para consultar saldo e extrato, é necessário ter uma conta aberta. 📊\n\n"
        "Posso te ajudar a abrir sua conta PJ agora mesmo!"
    ),
    "boleto": (
        "Para pagar boletos ou ver pagamentos, você precisa ter uma conta PJ. 🧾\n\n"
        "Vamos abrir sua conta? É rápido!"
    ),
    "default": (
        "Esse recurso está disponível para clientes com conta PJ aberta. 😊\n\n"
        "Quer abrir sua conta agora? Posso te guiar pelo processo!"
    ),
}


def requires_auth(query: str) -> bool:
    """
    Detecta se a query é sobre funcionalidades do app (requer login).

    Retorna True se a query contém keywords de funcionalidades
    que só estão disponíveis para clientes autenticados.
    """
    query_lower = query.lower()
    return any(kw in query_lower for kw in _APP_KEYWORDS)


def _detect_topic(query: str) -> str:
    """Classifica o tema da query para escolher a resposta de redirect."""
    q = query.lower()

    if any(kw in q for kw in ["pix", "transferir", "transferência", "transferencia"]):
        return "pix"
    if any(kw in q for kw in ["cartão", "cartao", "fatura", "limite"]):
        return "cartao"
    if any(kw in q for kw in ["saldo", "extrato", "disponível", "disponivel", "quanto tenho"]):
        return "saldo"
    if any(kw in q for kw in ["boleto", "pagar", "pagamento"]):
        return "boleto"

    return "default"


def build_auth_redirect(query: str, customer_id: str) -> AgentResponse:
    """
    Gera resposta de redirecionamento para cliente não autenticado.

    O cliente tentou usar uma funcionalidade do app sem ter conta.
    Responde de forma amigável e sugere abrir uma conta.
    """
    topic = _detect_topic(query)
    answer = _REDIRECT_RESPONSES[topic]

    return AgentResponse(
        customer_id=customer_id,
        answer=answer,
        context="onboarding",
        intent="open_account",
        confidence=1.0,
        suggested_actions=["Abrir conta PJ", "Saber mais sobre a conta", "Falar com atendente"],
        metadata=AgentMetadata(
            reasoning=[],
            sources=[],
            tokens_used=0,
            estimated_cost_usd=0.0,
        ),
    )
