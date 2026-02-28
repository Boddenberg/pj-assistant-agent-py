"""
Tools do agente — funções que o LLM pode chamar durante o workflow.

O que são tools?
  São funções Python que o LLM pode decidir invocar.
  O LLM recebe a descrição de cada tool (docstring) e decide
  quais chamar com base no contexto e na pergunta do cliente.

Como funciona o tool calling?
  1. LLM recebe: system prompt + contexto + lista de tools disponíveis
  2. LLM decide: "preciso chamar analyze_transactions com esses argumentos"
  3. LangGraph executa a tool e retorna o resultado ao LLM
  4. LLM pode chamar mais tools ou gerar a resposta final

Tools implementadas:
  1. analyze_transactions    → Análise financeira das transações
  2. search_knowledge_base   → Busca RAG na base de conhecimento
  3. assess_credit_profile   → Avaliação do perfil de crédito

IMPORTANTE: As docstrings são enviadas ao LLM. Elas precisam ser
claras e descritivas — o LLM usa isso para decidir quando chamar.
"""

from __future__ import annotations

import json
from langchain_core.tools import tool

from src.core.models import CustomerProfile, Transaction
from src.rag.retriever import retrieve


# =============================================================================
# Tool 1: Análise de Transações
# =============================================================================

@tool
def analyze_transactions(transactions_json: str) -> str:
    """Analisa transações do cliente e retorna resumo financeiro com totais por categoria.

    Args:
        transactions_json: JSON string com lista de transações do cliente.
    """
    # ─── Passo 1: Parsear o JSON das transações ─────────────────────
    # O LLM envia as transações como JSON string.
    # Precisamos converter para objetos Transaction para processar.
    try:
        raw = json.loads(transactions_json)
        transactions = [Transaction(**t) for t in raw]
    except Exception:
        return "Erro: não foi possível processar as transações."

    # Sem transações → retorna mensagem clara
    if not transactions:
        return "Nenhuma transação disponível para análise."

    # ─── Passo 2: Calcular métricas ────────────────────────────────
    # Total movimentado (entradas + saídas)
    total = sum(t.amount for t in transactions)

    # Agrupar por categoria e somar valores
    by_category: dict[str, float] = {}
    for t in transactions:
        by_category[t.category] = by_category.get(t.category, 0) + t.amount

    # Ordenar por valor absoluto (maiores movimentações primeiro)
    top_categories = sorted(
        by_category.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5]

    # ─── Passo 3: Montar resposta legível ──────────────────────────
    lines = [
        f"Total movimentado: R$ {total:,.2f}",
        f"Quantidade de transações: {len(transactions)}",
        "Top categorias:",
    ]
    for cat, val in top_categories:
        lines.append(f"  - {cat}: R$ {val:,.2f}")

    return "\n".join(lines)


# =============================================================================
# Tool 2: Busca na Base de Conhecimento (RAG)
# =============================================================================

@tool
def search_knowledge_base(query: str) -> str:
    """Busca informações relevantes na base de conhecimento sobre políticas, produtos e orientações financeiras do Itaú PJ.

    Args:
        query: Pergunta ou tema para buscar na base de conhecimento.
    """
    # Chamar o retriever que faz busca semântica no ChromaDB
    results = retrieve(query)

    # Sem resultados → mensagem clara para o LLM não alucinar
    if not results:
        return "Nenhum documento relevante encontrado na base de conhecimento."

    # Formatar resultados com score de relevância
    # O LLM recebe isso como contexto para gerar a resposta
    parts = []
    for r in results:
        parts.append(f"[relevância={r['score']}] {r['content']}")

    return "\n---\n".join(parts)


# =============================================================================
# Tool 3: Avaliação do Perfil de Crédito
# =============================================================================

@tool
def assess_credit_profile(profile_json: str) -> str:
    """Avalia o perfil de crédito do cliente PJ com base nos dados cadastrais e retorna nível de risco.

    Args:
        profile_json: JSON string com dados do perfil do cliente.
    """
    # ─── Parsear o JSON do perfil ──────────────────────────────────
    try:
        profile = CustomerProfile(**json.loads(profile_json))
    except Exception:
        return "Erro: não foi possível processar o perfil."

    # ─── Classificar risco ─────────────────────────────────────────
    # Faixas de risco baseadas no credit_score:
    #   700+ → baixo (acesso a todas as linhas, melhores taxas)
    #   500-699 → médio (acesso com garantias adicionais)
    #   <500 → alto (análise caso a caso)
    if profile.credit_score >= 700:
        risk = "baixo"
    elif profile.credit_score >= 500:
        risk = "médio"
    else:
        risk = "alto"

    # ─── Montar resposta estruturada ───────────────────────────────
    return (
        f"Empresa: {profile.company_name}\n"
        f"Segmento: {profile.segment}\n"
        f"Faixa de faturamento: {profile.revenue_range}\n"
        f"Score de crédito: {profile.credit_score} (risco {risk})\n"
        f"Cliente desde: {profile.account_since}"
    )


# =============================================================================
# Lista de tools disponíveis — importada pelo grafo
# =============================================================================
# O grafo usa essa lista para:
#   1. Informar ao LLM quais tools existem (bind_tools)
#   2. Criar o ToolNode que executa as tools chamadas pelo LLM
AGENT_TOOLS = [analyze_transactions, search_knowledge_base, assess_credit_profile]
