"""
Runner — fachada para invocar o workflow do agente.

Este módulo é a "porta de entrada" do agente.
A API (routes.py) chama run_agent() e recebe AssistantResponse.

Responsabilidades:
  1. Montar o contexto inicial (mensagem com dados do cliente)
  2. Invocar o grafo LangGraph
  3. Extrair resposta e métricas do estado final
  4. Empacotar tudo em AssistantResponse

Por que uma fachada?
  - Desacopla a API do grafo interno
  - Facilita testes (mock do runner, não do grafo inteiro)
  - Centraliza a montagem do contexto
  - Permite trocar o grafo sem mudar a API
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from src.core.models import AssistantRequest, AssistantResponse
from src.agent.graph import agent_graph
from src.agent.prompts import PLANNER_PROMPT
from src.observability.metrics import estimate_cost


async def run_agent(request: AssistantRequest) -> AssistantResponse:
    """
    Executa o workflow completo do agente para uma requisição do BFA.

    Fluxo:
      1. Monta mensagem inicial com contexto do cliente
      2. Cria estado inicial do grafo
      3. Invoca o grafo (ainvoke = async invoke)
      4. Extrai resposta final da última mensagem
      5. Calcula métricas (tokens, custo)
      6. Retorna AssistantResponse

    Args:
        request: Dados do cliente vindos do BFA (perfil + transações + query).

    Returns:
        AssistantResponse com resposta, reasoning, métricas.
    """

    # ─── Passo 1: Montar o contexto inicial ────────────────────────
    # O PLANNER_PROMPT é um template que recebe dados do cliente.
    # Isso dá ao LLM todas as informações para planejar.
    context = PLANNER_PROMPT.format(
        profile=request.profile.model_dump_json(),
        has_transactions=bool(request.transactions),
        query=request.query,
    )

    # Se há transações, incluir como JSON no contexto.
    # O LLM vai usar isso quando chamar analyze_transactions.
    if request.transactions:
        txn_data = json.dumps(
            [t.model_dump() for t in request.transactions],
            ensure_ascii=False,  # Manter acentos
        )
        context += f"\n\nDados de transações (JSON):\n{txn_data}"

    # Incluir perfil como JSON para a tool assess_credit_profile
    context += f"\n\nPerfil do cliente (JSON):\n{request.profile.model_dump_json()}"

    # ─── Passo 2: Criar estado inicial do grafo ────────────────────
    # O LangGraph precisa de um estado inicial com todos os campos.
    initial_state = {
        "messages": [HumanMessage(content=context)],  # Mensagem inicial
        "steps": [],            # Sem passos ainda
        "sources": [],          # Sem fontes RAG ainda
        "customer_id": request.customer_id,
        "tokens_in": 0,         # Contadores zerados
        "tokens_out": 0,
    }

    # ─── Passo 3: Executar o grafo ─────────────────────────────────
    # ainvoke = async invoke. Não bloqueia o event loop do FastAPI.
    # O grafo roda: planner → tools → executor → synthesizer → END
    result = await agent_graph.ainvoke(initial_state)

    # ─── Passo 4: Extrair resposta ─────────────────────────────────
    # A última mensagem do estado é a resposta do synthesizer (AIMessage)
    final_message = result["messages"][-1]
    answer = final_message.content if hasattr(final_message, "content") else str(final_message)

    # ─── Passo 5: Calcular métricas ───────────────────────────────
    tokens_in = result.get("tokens_in", 0)
    tokens_out = result.get("tokens_out", 0)
    total_tokens = tokens_in + tokens_out

    # ─── Passo 6: Empacotar resposta ──────────────────────────────
    return AssistantResponse(
        customer_id=request.customer_id,
        answer=answer,
        reasoning=result.get("steps", []),          # Passos do agente
        sources=result.get("sources", []),          # Fontes RAG
        tokens_used=total_tokens,
        estimated_cost_usd=estimate_cost(tokens_in, tokens_out),
    )
