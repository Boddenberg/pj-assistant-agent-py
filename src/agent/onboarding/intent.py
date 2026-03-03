"""
Detecção de intenção de onboarding e restart.

Duas funções:
  is_onboarding_intent → Detecta se a conversa é sobre abertura de conta
  _is_restart_request  → Detecta se o cliente quer recomeçar o onboarding
"""

from __future__ import annotations


def _is_restart_request(query: str) -> bool:
    """
    Detecta se o cliente está pedindo para recomeçar o onboarding.

    Usado quando o fluxo anterior foi encerrado por max retries
    e o cliente digita "abrir conta" para recomeçar.
    """
    restart_keywords = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
        "recomeçar", "começar de novo", "reiniciar",
        "tentar de novo", "tentar novamente",
        "quero tentar", "vamos tentar",
    ]
    query_lower = query.lower().strip()
    return any(kw in query_lower for kw in restart_keywords)


def is_onboarding_intent(query: str, history: list[dict]) -> bool:
    """
    Detecta se a conversa é sobre abertura de conta.

    Verifica:
      1. Se algum turno no history tem step preenchido (já é onboarding)
      2. Se o histórico contém keywords de onboarding
      3. Se a query atual menciona abertura de conta
    """
    # Se algum turno já tem step → é onboarding em andamento
    for turn in history:
        if turn.get("step") is not None:
            return True

    # Keywords no histórico
    onboarding_keywords_in_history = [
        "abrir", "abertura", "conta pj", "conta PJ",
        "cnpj", "razão social", "razao social", "nome fantasia",
        "representante", "passo a passo", "dados da empresa",
    ]

    for turn in history:
        combined = (turn.get("query", "") + " " + turn.get("answer", "")).lower()
        if any(kw.lower() in combined for kw in onboarding_keywords_in_history):
            return True

    # Keywords na query atual
    onboarding_keywords_query = [
        "abrir conta", "abertura", "criar conta", "nova conta",
        "quero conta", "abrir uma conta", "abrir minha conta",
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in onboarding_keywords_query)
