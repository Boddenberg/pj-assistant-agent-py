"""
Runner — fachada para invocar o workflow do agente.

Este módulo é a "porta de entrada" do agente.
A API (routes.py) chama run_agent() e recebe AgentResponse.

Responsabilidades:
  1. Montar o contexto inicial (mensagem com dados do cliente)
  2. Invocar o grafo LangGraph
  3. Extrair resposta e métricas do estado final
  4. Empacotar tudo em AgentResponse

Por que uma fachada?
  - Desacopla a API do grafo interno
  - Facilita testes (mock do runner, não do grafo inteiro)
  - Centraliza a montagem do contexto
  - Permite trocar o grafo sem mudar a API
"""

from __future__ import annotations

import json
import re
import time

from langchain_core.messages import AIMessage, HumanMessage

from src.core.models import AgentRequest, AgentResponse
from src.agent.graph import agent_graph
from src.agent.prompts import PLANNER_PROMPT
from src.agent.onboarding import (
    determine_current_field,
    build_onboarding_context,
    is_onboarding_intent,
    FIELD_LABELS,
    FIELD_PROMPTS,
)
from src.observability.metrics import estimate_cost
from src.observability.logging import get_logger

logger = get_logger("runner")


async def run_agent(request: AgentRequest, original_query: str | None = None) -> AgentResponse:
    """
    Executa o workflow completo do agente para uma requisição do BFA.

    Args:
        request: Dados do cliente vindos do BFA (perfil + transações + query).
                 A query pode estar sanitizada (PII mascarado).
        original_query: Query original antes da máscara PII.
                        Usada pelo onboarding para validar dados reais
                        (CNPJ, CPF, email) que o cliente está fornecendo.

    Returns:
        AgentResponse com resposta, reasoning, métricas.
    """

    # Query para onboarding: original (sem máscara) quando disponível.
    # O onboarding PRECISA do dado real para validar CNPJ, CPF, etc.
    # A máscara PII é só para o texto enviado ao LLM.
    onboarding_query = original_query or request.query

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

    # ─── Onboarding: fluxo campo-a-campo ───────────────────────────
    # Se a conversa é sobre abertura de conta, determina qual campo
    # pedir agora e injeta instrução determinística no prompt.
    # O agente só conversa — validação fica no BFA (Go).
    history_dicts = [
        {
            "query": turn.query,
            "answer": turn.answer,
            "step": turn.step,
            "validated": turn.validated,
        }
        for turn in request.history
    ]

    onboarding_state = None
    if is_onboarding_intent(onboarding_query, history_dicts):
        onboarding_state = determine_current_field(
            history_dicts,
            onboarding_query,
            validation_error=getattr(request, "validation_error", "") or "",
        )

        logger.info(
            "📋 [RUNNER] ONBOARDING_STATE_DETERMINED",
            customer_id=request.customer_id,
            step=onboarding_state.step.value,
            next_step=onboarding_state.next_step.value,
            collected_count=len(onboarding_state.collected),
            has_validation_error=onboarding_state.has_validation_error,
            is_complete=onboarding_state.is_complete,
            retry_count=onboarding_state.retry_count,
            max_retries_exceeded=onboarding_state.max_retries_exceeded,
        )

        # Injetar contexto de onboarding no prompt para o LLM
        onboarding_context = build_onboarding_context(onboarding_state)
        context += f"\n\n{onboarding_context}"

    # Construir instrução de onboarding explícita para o synthesizer
    onboarding_synth_hint = ""
    if onboarding_state and not onboarding_state.is_complete:
        label = FIELD_LABELS.get(onboarding_state.next_step, onboarding_state.next_step.value)
        prompt_text = FIELD_PROMPTS.get(onboarding_state.next_step, "")
        onboarding_synth_hint = (
            f"⚠️ ONBOARDING ATIVO — NÃO mude o campo pedido.\n"
            f"O campo a pedir agora é: **{label}**\n"
            f"Mensagem sugerida: \"{prompt_text}\"\n"
            f"→ Peça SOMENTE **{label}**. NÃO peça nenhum outro campo."
        )
    elif onboarding_state and onboarding_state.is_complete:
        onboarding_synth_hint = (
            "⚠️ ONBOARDING COMPLETO — Parabenize o cliente e mostre o resumo dos dados coletados."
        )

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
    # Montar mensagens: histórico de conversa + query atual.
    # O BFA envia até 5 turnos anteriores (history).
    # Cada turno vira HumanMessage + AIMessage no LangGraph,
    # dando ao LLM o contexto da conversa para não repetir perguntas.
    messages: list[HumanMessage | AIMessage] = []

    if request.history:
        for turn in request.history:
            messages.append(HumanMessage(content=turn.query))
            messages.append(AIMessage(content=turn.answer))

    # Query atual do cliente (com contexto do planner)
    messages.append(HumanMessage(content=context))

    initial_state = {
        "messages": messages,
        "steps": [],
        "sources": [],
        "customer_id": request.customer_id,
        "tokens_in": 0,
        "tokens_out": 0,
        "onboarding_synth_instruction": onboarding_synth_hint,
    }

    logger.info(
        "🚀 [RUNNER 2/4] GRAPH_INVOKING — Invocando grafo LangGraph",
        customer_id=request.customer_id,
        initial_messages_count=len(initial_state["messages"]),
        history_turns=len(request.history),
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

    # ─── Passo 4: Extrair resposta e context ───────────────────────
    final_message = result["messages"][-1]
    raw_answer = final_message.content if hasattr(final_message, "content") else str(final_message)

    # Extrair metadados estruturados da resposta do LLM.
    # O LLM inclui [META:{json}] na última linha — contém context, intent,
    # confidence e suggested_actions para o BFA tomar decisões.
    # Regex captura o JSON e remove a tag da resposta visível ao cliente.
    meta_match = re.search(r"\[META:(\{.*?\})\]", raw_answer, re.DOTALL)
    context = None
    intent = None
    confidence = 1.0
    suggested_actions: list[str] = []

    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            context = meta.get("context")
            intent = meta.get("intent")
            confidence = float(meta.get("confidence", 1.0))
            suggested_actions = meta.get("suggested_actions", [])
        except (json.JSONDecodeError, ValueError):
            logger.warning(
                "⚠️ [RUNNER] META_PARSE_FAILED — não foi possível parsear [META:...]",
                customer_id=request.customer_id,
                raw_meta=meta_match.group(1),
            )

    # Fallback: tentar formato antigo [CONTEXT:xxx] para compatibilidade
    if not context and not meta_match:
        context_match = re.search(r"\[CONTEXT:(\w+)\]", raw_answer)
        if context_match:
            context = context_match.group(1)

    # Limpar tags META/CONTEXT da resposta visível ao cliente
    answer = re.sub(r"\s*\[META:\{.*?\}\]\s*", "", raw_answer, flags=re.DOTALL).strip()
    answer = re.sub(r"\s*\[CONTEXT:\w+\]\s*", "", answer).strip()

    tokens_in = result.get("tokens_in", 0)
    tokens_out = result.get("tokens_out", 0)
    total_tokens = tokens_in + tokens_out
    cost = estimate_cost(tokens_in, tokens_out)

    logger.info(
        "📦 [RUNNER 4/4] RESPONSE_PACKED — Resposta empacotada para a API",
        customer_id=request.customer_id,
        answer_length=len(answer),
        context=context,
        intent=intent,
        confidence=confidence,
        suggested_actions=suggested_actions,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        reasoning_steps=[s.step.value for s in result.get("steps", [])],
        sources=result.get("sources", []),
    )

    # ─── Passo 5: Empacotar resposta ──────────────────────────────
    from src.core.models import AgentMetadata

    # Se for onboarding, enriquecer resposta com campos de controle
    if onboarding_state:
        context = "onboarding"
        intent = "open_account"
        suggested_actions = ["Continuar cadastro", "Cancelar abertura"]

    return AgentResponse(
        customer_id=request.customer_id,
        answer=answer,
        context=context,
        intent=intent,
        confidence=confidence,
        suggested_actions=suggested_actions,
        step=onboarding_state.step.value if onboarding_state else None,
        field_value=onboarding_state.field_value if onboarding_state else None,
        next_step=onboarding_state.next_step.value if onboarding_state else None,
        metadata=AgentMetadata(
            reasoning=result.get("steps", []),
            sources=result.get("sources", []),
            tokens_used=total_tokens,
            estimated_cost_usd=cost,
        ),
    )
