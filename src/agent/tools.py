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
import time
from langchain_core.tools import tool

from src.core.models import CustomerProfile, Transaction
from src.rag.retriever import retrieve
from src.observability.logging import get_logger

logger = get_logger("tools")


# =============================================================================
# Tool 1: Análise de Transações
# =============================================================================

@tool
def analyze_transactions(transactions_json: str) -> str:
    """Analisa transações do cliente e retorna resumo financeiro com totais por categoria.

    Args:
        transactions_json: JSON string com lista de transações do cliente.
    """
    start = time.perf_counter()
    logger.info(
        "🔧 [TOOL] ANALYZE_TRANSACTIONS_START — Analisando transações",
        tool="analyze_transactions",
        input_length=len(transactions_json),
    )

    try:
        raw = json.loads(transactions_json)
        transactions = [Transaction(**t) for t in raw]
    except Exception as e:
        logger.error(
            "🔧 [TOOL] ANALYZE_TRANSACTIONS_ERROR — Falha ao parsear JSON",
            tool="analyze_transactions",
            error=str(e),
        )
        return "Erro: não foi possível processar as transações."

    if not transactions:
        logger.info(
            "🔧 [TOOL] ANALYZE_TRANSACTIONS_END — Nenhuma transação",
            tool="analyze_transactions",
            num_transactions=0,
        )
        return "Nenhuma transação disponível para análise."

    total = sum(t.amount for t in transactions)

    by_category: dict[str, float] = {}
    for t in transactions:
        by_category[t.category] = by_category.get(t.category, 0) + t.amount

    top_categories = sorted(
        by_category.items(),
        key=lambda x: abs(x[1]),
        reverse=True,
    )[:5]

    lines = [
        f"Total movimentado: R$ {total:,.2f}",
        f"Quantidade de transações: {len(transactions)}",
        "Top categorias:",
    ]
    for cat, val in top_categories:
        lines.append(f"  - {cat}: R$ {val:,.2f}")

    result = "\n".join(lines)
    duration = (time.perf_counter() - start) * 1000

    logger.info(
        "🔧 [TOOL] ANALYZE_TRANSACTIONS_END — Análise concluída",
        tool="analyze_transactions",
        num_transactions=len(transactions),
        total_amount=round(total, 2),
        num_categories=len(by_category),
        top_categories=[cat for cat, _ in top_categories],
        duration_ms=round(duration, 2),
    )

    return result


# =============================================================================
# Tool 2: Busca na Base de Conhecimento (RAG)
# =============================================================================

@tool
def search_knowledge_base(query: str) -> str:
    """Busca informações relevantes na base de conhecimento sobre políticas, produtos e orientações financeiras do Itaú PJ.

    Args:
        query: Pergunta ou tema para buscar na base de conhecimento.
    """
    start = time.perf_counter()
    logger.info(
        "🔧 [TOOL] SEARCH_KB_START — Buscando na base de conhecimento (RAG)",
        tool="search_knowledge_base",
        query=query,
        query_length=len(query),
    )

    results = retrieve(query)

    duration = (time.perf_counter() - start) * 1000

    if not results:
        logger.info(
            "🔧 [TOOL] SEARCH_KB_END — Nenhum resultado encontrado",
            tool="search_knowledge_base",
            query=query,
            num_results=0,
            duration_ms=round(duration, 2),
        )
        return "Nenhum documento relevante encontrado na base de conhecimento."

    parts = []
    for r in results:
        parts.append(f"[relevância={r['score']}] {r['content']}")

    sources = [r.get("source", "unknown") for r in results]
    scores = [r["score"] for r in results]

    logger.info(
        "🔧 [TOOL] SEARCH_KB_END — Resultados encontrados",
        tool="search_knowledge_base",
        query=query,
        num_results=len(results),
        sources=sources,
        relevance_scores=scores,
        best_score=max(scores) if scores else 0,
        duration_ms=round(duration, 2),
    )

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
    start = time.perf_counter()
    logger.info(
        "🔧 [TOOL] ASSESS_CREDIT_START — Avaliando perfil de crédito",
        tool="assess_credit_profile",
        input_length=len(profile_json),
    )

    try:
        profile = CustomerProfile(**json.loads(profile_json))
    except Exception as e:
        logger.error(
            "🔧 [TOOL] ASSESS_CREDIT_ERROR — Falha ao parsear JSON do perfil",
            tool="assess_credit_profile",
            error=str(e),
        )
        return "Erro: não foi possível processar o perfil."

    if profile.credit_score >= 700:
        risk = "baixo"
    elif profile.credit_score >= 500:
        risk = "médio"
    else:
        risk = "alto"

    result = (
        f"Empresa: {profile.company_name}\n"
        f"Segmento: {profile.segment}\n"
        f"Faixa de faturamento: {profile.revenue_range}\n"
        f"Score de crédito: {profile.credit_score} (risco {risk})\n"
        f"Cliente desde: {profile.account_since}"
    )

    duration = (time.perf_counter() - start) * 1000

    logger.info(
        "🔧 [TOOL] ASSESS_CREDIT_END — Avaliação de crédito concluída",
        tool="assess_credit_profile",
        company_name=profile.company_name,
        segment=profile.segment,
        credit_score=profile.credit_score,
        risk_level=risk,
        duration_ms=round(duration, 2),
    )

    return result


# =============================================================================
# Lista de tools disponíveis — importada pelo grafo
# =============================================================================
# O grafo usa essa lista para:
#   1. Informar ao LLM quais tools existem (bind_tools)
#   2. Criar o ToolNode que executa as tools chamadas pelo LLM
AGENT_TOOLS = [analyze_transactions, search_knowledge_base, assess_credit_profile]
