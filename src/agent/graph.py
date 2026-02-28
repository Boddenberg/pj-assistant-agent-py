"""
LangGraph Workflow — grafo de execução do agente.

Este é o CORAÇÃO do agente. Define o fluxo de execução como um grafo
dirigido onde cada nó é uma etapa do raciocínio.

=============================================================================
FLUXO DO GRAFO:

  ┌─────────┐
  │  START  │
  └────┬────┘
       │
       ▼
  ┌─────────┐     O Planner recebe o contexto do cliente e decide
  │ PLANNER │     quais tools chamar. Ele pode:
  └────┬────┘       a) Chamar tools (→ vai para TOOLS)
       │            b) Responder direto (→ vai para SYNTHESIZER)
       │
       ▼
  ┌──────────────┐
  │ TEM TOOLS?   │  ← Roteador condicional (should_continue)
  └──┬───────┬───┘
     │       │
     │Sim    │Não
     ▼       ▼
  ┌──────┐  ┌──────────────┐
  │TOOLS │  │ SYNTHESIZER  │  ← Gera resposta final
  └──┬───┘  └──────┬───────┘
     │             │
     ▼             ▼
  ┌──────────┐  ┌─────┐
  │ EXECUTOR │  │ END │
  └────┬─────┘  └─────┘
       │
       ▼
  ┌──────────────┐
  │ TEM TOOLS?   │  ← Pode precisar de mais tools (loop)
  └──┬───────┬───┘
     │       │
     │Sim    │Não
     ▼       ▼
  (TOOLS)  (SYNTHESIZER)

=============================================================================

Por que LangGraph?
  - Grafo explícito: cada passo é um nó testável e auditável
  - Loops condicionais: o agente pode chamar várias tools em sequência
  - Estado tipado: TypedDict garante consistência entre nós
  - Async nativo: funciona com FastAPI sem bloqueio
  - Produção-ready: checkpointing, streaming, human-in-the-loop

Nós do grafo:
  planner_node     → Analisa contexto e decide tools (LLM com bind_tools)
  tools (ToolNode) → Executa as tools chamadas pelo LLM (automático)
  executor_node    → Processa resultados e decide se precisa mais tools
  synthesizer_node → Gera resposta final consolidada (LLM sem tools)
"""

from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from src.core.config import settings
from src.core.models import AgentStep, StepType
from src.agent.state import AgentState
from src.agent.tools import AGENT_TOOLS
from src.agent.prompts import SYSTEM_PROMPT
from src.observability.logging import get_logger

logger = get_logger("graph")


# =============================================================================
# Factory do LLM — cria instância configurada do ChatOpenAI
# =============================================================================

def _build_llm() -> ChatOpenAI:
    """
    Cria uma instância do ChatOpenAI com as configurações do settings.

    Por que factory function?
      - Cada nó pode precisar de config diferente no futuro
      - Facilita mock nos testes
      - Centraliza a criação em um lugar só
    """
    return ChatOpenAI(
        model=settings.llm_model,               # gpt-4o-mini
        temperature=settings.llm_temperature,    # 0.1 (determinístico)
        api_key=settings.openai_api_key,
        max_tokens=settings.max_tokens_per_request,
    )


# =============================================================================
# Nó 1: PLANNER — decide o que fazer
# =============================================================================

def planner_node(state: AgentState) -> dict:
    """
    Nó planejador — analisa o contexto do cliente e decide quais tools chamar.
    """
    start = time.perf_counter()
    customer_id = state.get("customer_id", "unknown")

    logger.info(
        "🧠 [GRAPH] PLANNER_START — Nó Planner iniciado",
        customer_id=customer_id,
        messages_count=len(state["messages"]),
        node="planner",
    )

    llm = _build_llm().bind_tools(AGENT_TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = llm.invoke(messages)

    duration = (time.perf_counter() - start) * 1000
    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

    # Detectar quais tools o LLM decidiu chamar
    tool_calls = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_calls = [tc["name"] for tc in response.tool_calls]

    logger.info(
        "🧠 [GRAPH] PLANNER_END — Nó Planner finalizado",
        customer_id=customer_id,
        node="planner",
        duration_ms=round(duration, 2),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        decided_tools=tool_calls if tool_calls else "nenhuma (resposta direta)",
        num_tool_calls=len(tool_calls),
        will_route_to="tools" if tool_calls else "synthesizer",
    )

    step = AgentStep(
        step=StepType.PLAN,
        detail="Planejamento: análise do contexto e decisão de ferramentas",
        duration_ms=round(duration, 2),
    )

    return {
        "messages": [response],
        "steps": state.get("steps", []) + [step],
        "tokens_in": state.get("tokens_in", 0) + tokens_in,
        "tokens_out": state.get("tokens_out", 0) + tokens_out,
    }


# =============================================================================
# Nó 2: EXECUTOR — processa resultado de tools e decide próximo passo
# =============================================================================

def executor_node(state: AgentState) -> dict:
    """
    Nó executor — recebe resultados das tools e decide se precisa de mais.
    """
    start = time.perf_counter()
    customer_id = state.get("customer_id", "unknown")

    # Identificar quais ToolMessages chegaram (resultados das tools)
    from langchain_core.messages import ToolMessage
    tool_results = [
        msg.name for msg in state["messages"]
        if isinstance(msg, ToolMessage)
    ]

    logger.info(
        "⚙️  [GRAPH] EXECUTOR_START — Nó Executor iniciado (analisando resultados de tools)",
        customer_id=customer_id,
        node="executor",
        messages_count=len(state["messages"]),
        tool_results_received=tool_results,
    )

    llm = _build_llm().bind_tools(AGENT_TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])
    response = llm.invoke(messages)

    duration = (time.perf_counter() - start) * 1000
    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

    # Detectar se vai chamar mais tools ou sintetizar
    more_tools = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        more_tools = [tc["name"] for tc in response.tool_calls]

    logger.info(
        "⚙️  [GRAPH] EXECUTOR_END — Nó Executor finalizado",
        customer_id=customer_id,
        node="executor",
        duration_ms=round(duration, 2),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        needs_more_tools=bool(more_tools),
        next_tools=more_tools if more_tools else "nenhuma",
        will_route_to="tools" if more_tools else "synthesizer",
    )

    step = AgentStep(
        step=StepType.TOOL_CALL,
        detail="Processamento de resultados das ferramentas",
        duration_ms=round(duration, 2),
    )

    return {
        "messages": [response],
        "steps": state.get("steps", []) + [step],
        "tokens_in": state.get("tokens_in", 0) + tokens_in,
        "tokens_out": state.get("tokens_out", 0) + tokens_out,
    }


# =============================================================================
# Nó 3: SYNTHESIZER — gera resposta final
# =============================================================================

def synthesizer_node(state: AgentState) -> dict:
    """
    Nó sintetizador — consolida todas as análises em resposta final.
    """
    start = time.perf_counter()
    customer_id = state.get("customer_id", "unknown")

    logger.info(
        "✍️  [GRAPH] SYNTHESIZER_START — Nó Synthesizer iniciado (gerando resposta final)",
        customer_id=customer_id,
        node="synthesizer",
        messages_count=len(state["messages"]),
        steps_so_far=len(state.get("steps", [])),
        accumulated_tokens_in=state.get("tokens_in", 0),
        accumulated_tokens_out=state.get("tokens_out", 0),
    )

    llm = _build_llm()

    synth_instruction = (
        "Agora gere a resposta final para o cliente no chat do app. "
        "Lembre-se: é um CHAT, não um email. Seja direto, conversacional e curto. "
        "Não use formato de relatório. Não assine a mensagem. "
        "Vá direto ao ponto com os dados que você já analisou."
    )

    messages = (
        [SystemMessage(content=SYSTEM_PROMPT)]
        + list(state["messages"])
        + [HumanMessage(content=synth_instruction)]
    )

    response = llm.invoke(messages)

    duration = (time.perf_counter() - start) * 1000
    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

    answer_preview = response.content[:150] if hasattr(response, "content") else "N/A"

    logger.info(
        "✍️  [GRAPH] SYNTHESIZER_END — Nó Synthesizer finalizado (resposta gerada)",
        customer_id=customer_id,
        node="synthesizer",
        duration_ms=round(duration, 2),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        answer_length=len(response.content) if hasattr(response, "content") else 0,
        answer_preview=answer_preview + "..." if len(answer_preview) >= 150 else answer_preview,
    )

    step = AgentStep(
        step=StepType.SYNTHESIZE,
        detail="Síntese: resposta final consolidada",
        duration_ms=round(duration, 2),
    )

    return {
        "messages": [response],
        "steps": state.get("steps", []) + [step],
        "tokens_in": state.get("tokens_in", 0) + tokens_in,
        "tokens_out": state.get("tokens_out", 0) + tokens_out,
    }


# =============================================================================
# Roteador condicional — decide para onde ir após planner/executor
# =============================================================================

def should_continue(state: AgentState) -> str:
    """
    Decide se o agente deve continuar chamando tools ou sintetizar.
    """
    last_message = state["messages"][-1]
    customer_id = state.get("customer_id", "unknown")

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tools_requested = [tc["name"] for tc in last_message.tool_calls]
        logger.info(
            "🔀 [GRAPH] ROUTER → tools — LLM quer chamar ferramentas",
            customer_id=customer_id,
            decision="tools",
            tools_requested=tools_requested,
        )
        return "tools"

    logger.info(
        "🔀 [GRAPH] ROUTER → synthesizer — LLM pronto para sintetizar",
        customer_id=customer_id,
        decision="synthesize",
    )
    return "synthesize"


# =============================================================================
# Build do Grafo — monta e compila o workflow LangGraph
# =============================================================================

def build_graph() -> StateGraph:
    """
    Constrói e compila o grafo de execução do agente.

    Estrutura:
      1. Registrar nós (funções)
      2. Registrar arestas (conexões entre nós)
      3. Compilar (validar e otimizar)

    O grafo compilado é um objeto invocável:
      result = await graph.ainvoke(initial_state)

    Returns:
        Grafo compilado pronto para uso.
    """

    # ─── ToolNode ──────────────────────────────────────────────────
    # ToolNode é um nó pré-construído do LangGraph que:
    #   1. Lê os tool_calls da última AIMessage
    #   2. Executa cada tool chamada
    #   3. Retorna os resultados como ToolMessages
    # Não precisamos implementar a execução de tools manualmente.
    tool_node = ToolNode(AGENT_TOOLS)

    # ─── Criar o grafo com o tipo de estado ────────────────────────
    graph = StateGraph(AgentState)

    # ─── Registrar nós ─────────────────────────────────────────────
    graph.add_node("planner", planner_node)         # Nó 1: Planejar
    graph.add_node("executor", executor_node)       # Nó 2: Executar
    graph.add_node("tools", tool_node)              # Nó 3: Tools (automático)
    graph.add_node("synthesizer", synthesizer_node)  # Nó 4: Sintetizar

    # ─── Registrar arestas ─────────────────────────────────────────

    # Entry point: sempre começa pelo planner
    graph.set_entry_point("planner")

    # Planner → (tools OU synthesizer) — depende se há tool_calls
    graph.add_conditional_edges(
        "planner",                  # Após o planner...
        should_continue,            # ...chamar should_continue()...
        {                           # ...e seguir baseado no retorno:
            "tools": "tools",           # "tools" → nó tools
            "synthesize": "synthesizer",  # "synthesize" → nó synthesizer
        },
    )

    # Tools → executor (sempre)
    # Após executar as tools, o executor analisa os resultados
    graph.add_edge("tools", "executor")

    # Executor → (tools OU synthesizer) — pode precisar de mais tools
    graph.add_conditional_edges(
        "executor",
        should_continue,
        {
            "tools": "tools",           # Mais tools necessárias → loop
            "synthesize": "synthesizer",  # Suficiente → sintetizar
        },
    )

    # Synthesizer → END (sempre)
    # Após sintetizar, o grafo termina
    graph.add_edge("synthesizer", END)

    # ─── Compilar ──────────────────────────────────────────────────
    # compile() valida o grafo e retorna um objeto invocável
    return graph.compile()


# =============================================================================
# Singleton — grafo compilado uma vez no import
# =============================================================================
# Compilar o grafo é rápido e sem efeitos colaterais.
# Manter como singleton evita recriar a cada request.
agent_graph = build_graph()
