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

    Recebe:
      - Mensagens com contexto do cliente (perfil, transações, query)

    Faz:
      - Chama o LLM com bind_tools (LLM sabe quais tools existem)
      - LLM decide: chamar tools ou responder direto

    Retorna:
      - AIMessage com tool_calls (se decidiu usar tools)
      - AIMessage com content (se decidiu responder direto)

    O roteador (should_continue) decide o próximo passo baseado no retorno.
    """
    start = time.perf_counter()

    # Criar LLM com as tools disponíveis
    # bind_tools diz ao LLM: "você pode chamar estas funções"
    llm = _build_llm().bind_tools(AGENT_TOOLS)

    # Montar mensagens: System Prompt + histórico de mensagens do estado
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])

    # Chamar o LLM — ele vai analisar o contexto e decidir os próximos passos
    response = llm.invoke(messages)

    # Calcular duração para métricas
    duration = (time.perf_counter() - start) * 1000

    # Extrair contagem de tokens (se disponível)
    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

    # Registrar o passo para rastreabilidade
    step = AgentStep(
        step=StepType.PLAN,
        detail="Planejamento: análise do contexto e decisão de ferramentas",
        duration_ms=round(duration, 2),
    )

    # Retornar atualizações do estado
    # O LangGraph faz merge automático (messages acumula, tokens soma)
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

    Fluxo:
      1. Tools foram executadas → ToolMessages estão no estado
      2. LLM recebe o histórico completo (incluindo resultados das tools)
      3. LLM decide:
         a) Chamar MAIS tools (→ loop de volta para TOOLS)
         b) Sintetizar resposta (→ vai para SYNTHESIZER)

    Por que separar Planner e Executor?
      - Planner: decide com base no contexto original
      - Executor: decide com base nos RESULTADOS das tools
      - São decisões diferentes que podem ter prompts diferentes no futuro
    """
    start = time.perf_counter()

    # LLM com tools — pode decidir chamar mais tools
    llm = _build_llm().bind_tools(AGENT_TOOLS)

    # Histórico completo: system + human + ai (tool_calls) + tool (resultados)
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(state["messages"])

    # LLM analisa os resultados das tools e decide próximo passo
    response = llm.invoke(messages)

    duration = (time.perf_counter() - start) * 1000

    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

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

    Recebe:
      - Todo o histórico: contexto original + resultados de tools

    Faz:
      - Chama LLM SEM tools (apenas geração de texto)
      - Pede uma resposta final estruturada
      - Formato: Resumo + Análise + Recomendações

    Por que sem tools?
      - Neste ponto, já temos todas as informações necessárias
      - O LLM só precisa consolidar e formatar
      - Remover tools evita que o LLM "invente" mais chamadas desnecessárias
    """
    start = time.perf_counter()

    # LLM sem tools — apenas geração de texto
    llm = _build_llm()

    # Instrução de síntese — guia o LLM a consolidar tudo
    synth_instruction = (
        "Com base em toda a análise realizada nos passos anteriores, "
        "gere uma resposta final consolidada para o cliente. "
        "Inclua: resumo da situação, análise e recomendações personalizadas. "
        "Seja claro, objetivo e acionável."
    )

    # Montar mensagens: system + histórico + instrução de síntese
    messages = (
        [SystemMessage(content=SYSTEM_PROMPT)]
        + list(state["messages"])
        + [HumanMessage(content=synth_instruction)]
    )

    response = llm.invoke(messages)

    duration = (time.perf_counter() - start) * 1000

    tokens_in = response.usage_metadata.get("input_tokens", 0) if response.usage_metadata else 0
    tokens_out = response.usage_metadata.get("output_tokens", 0) if response.usage_metadata else 0

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

    Lógica simples:
      - Se a última mensagem do LLM tem tool_calls → ir para TOOLS
      - Se não tem tool_calls → ir para SYNTHESIZER

    Essa função é usada como conditional_edge no grafo.
    O LangGraph chama ela após cada nó e usa o retorno para
    decidir qual aresta seguir.
    """
    last_message = state["messages"][-1]

    # AIMessage com tool_calls → LLM quer chamar tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Sem tool_calls → LLM terminou, hora de sintetizar
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
