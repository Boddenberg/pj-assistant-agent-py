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
import time

from langchain_core.messages import HumanMessage

from src.core.models import AssistantRequest, AssistantResponse
from src.agent.graph import agent_graph
from src.agent.prompts import PLANNER_PROMPT
from src.observability.metrics import estimate_cost
from src.observability.logging import get_logger

logger = get_logger("runner")


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
    context_start = time.perf_counter()

    # Se tem perfil, usa os dados. Se não, indica que não tem.
    profile_json = request.profile.model_dump_json() if request.profile else "Não disponível"

    context = PLANNER_PROMPT.format(
        profile=profile_json,
        has_transactions=bool(request.transactions),
        query=request.query,
    )

    if request.transactions:
        txn_data = json.dumps(
            [t.model_dump() for t in request.transactions],
            ensure_ascii=False,
        )
        context += f"\n\nDados de transações (JSON):\n{txn_data}"

    if request.profile:
        context += f"\n\nPerfil do cliente (JSON):\n{profile_json}"

    context_duration = (time.perf_counter() - context_start) * 1000

    logger.info(
        "📋 [RUNNER 1/4] CONTEXT_BUILT — Contexto do agente montado",
        customer_id=request.customer_id,
        context_length_chars=len(context),
        has_transactions=bool(request.transactions),
        num_transactions=len(request.transactions),
        context_build_ms=round(context_duration, 2),
    )

    # ─── Passo 2: Criar estado inicial do grafo ────────────────────
    initial_state = {
        "messages": [HumanMessage(content=context)],
        "steps": [],
        "sources": [],
        "customer_id": request.customer_id,
        "tokens_in": 0,
        "tokens_out": 0,
    }

    logger.info(
        "🚀 [RUNNER 2/4] GRAPH_INVOKING — Invocando grafo LangGraph",
        customer_id=request.customer_id,
        initial_messages_count=len(initial_state["messages"]),
    )

    # ── Log completo do INPUT do LangGraph ─────────────────────────
    logger.debug(
        "📨 [LANGGRAPH INPUT] — Conteúdo completo enviado ao grafo",
        customer_id=request.customer_id,
        input_message=context,
    )

    # ─── Passo 3: Executar o grafo ─────────────────────────────────
    graph_start = time.perf_counter()
    result = await agent_graph.ainvoke(initial_state)
    graph_duration = (time.perf_counter() - graph_start) * 1000

    logger.info(
        "🏁 [RUNNER 3/4] GRAPH_COMPLETED — Grafo LangGraph finalizado",
        customer_id=request.customer_id,
        graph_duration_ms=round(graph_duration, 2),
        total_messages=len(result.get("messages", [])),
        total_steps=len(result.get("steps", [])),
        total_sources=len(result.get("sources", [])),
        tokens_in=result.get("tokens_in", 0),
        tokens_out=result.get("tokens_out", 0),
    )

    # ── Log completo do OUTPUT do LangGraph ────────────────────────
    output_messages = []
    for i, msg in enumerate(result.get("messages", [])):
        msg_type = type(msg).__name__
        msg_content = msg.content if hasattr(msg, "content") else str(msg)
        msg_info = {
            "index": i,
            "type": msg_type,
            "content_preview": msg_content[:300] + ("..." if len(msg_content) > 300 else ""),
            "content_length": len(msg_content),
        }
        # Se for AIMessage com tool_calls, logar quais tools foram chamadas
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            msg_info["tool_calls"] = [
                {"name": tc["name"], "args_preview": str(tc.get("args", {}))[:200]}
                for tc in msg.tool_calls
            ]
        # Se for ToolMessage, logar o nome da tool
        if hasattr(msg, "name") and msg_type == "ToolMessage":
            msg_info["tool_name"] = msg.name
        output_messages.append(msg_info)

    logger.debug(
        "📩 [LANGGRAPH OUTPUT] — Conteúdo completo retornado pelo grafo",
        customer_id=request.customer_id,
        total_messages=len(output_messages),
        messages=output_messages,
    )

    # ─── Passo 4: Extrair resposta ─────────────────────────────────
    final_message = result["messages"][-1]
    answer = final_message.content if hasattr(final_message, "content") else str(final_message)

    tokens_in = result.get("tokens_in", 0)
    tokens_out = result.get("tokens_out", 0)
    total_tokens = tokens_in + tokens_out
    cost = estimate_cost(tokens_in, tokens_out)

    logger.info(
        "📦 [RUNNER 4/4] RESPONSE_PACKED — Resposta empacotada para a API",
        customer_id=request.customer_id,
        answer_length=len(answer),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        reasoning_steps=[s.step.value for s in result.get("steps", [])],
        sources=result.get("sources", []),
    )

    # ─── Passo 5: Empacotar resposta ──────────────────────────────
    return AssistantResponse(
        customer_id=request.customer_id,
        answer=answer,
        reasoning=result.get("steps", []),
        sources=result.get("sources", []),
        tokens_used=total_tokens,
        estimated_cost_usd=cost,
    )
