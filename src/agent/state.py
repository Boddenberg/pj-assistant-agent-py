"""
State do agente — estado compartilhado entre todos os nós do grafo.

O LangGraph usa um TypedDict para definir o estado que é passado
entre os nós do grafo. Cada nó pode ler e escrever nesse estado.

Por que TypedDict (e não dataclass ou Pydantic)?
  - É o formato que o LangGraph espera
  - Tipagem estática sem overhead de runtime
  - Annotated[..., add_messages] é a magia do LangGraph para
    acumular mensagens automaticamente (append, não replace)

Campos do estado:
  messages    → Histórico de mensagens (Human, AI, Tool)
  steps       → Registro de passos para rastreabilidade
  sources     → Fontes RAG utilizadas na resposta
  customer_id → ID do cliente (para logs e métricas)
  tokens_in   → Contador de tokens de entrada
  tokens_out  → Contador de tokens de saída
"""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from src.core.models import AgentStep


class AgentState(TypedDict):
    """
    Estado compartilhado no grafo LangGraph.

    IMPORTANTE: O campo `messages` usa `Annotated[..., add_messages]`.
    Isso significa que quando um nó retorna {"messages": [nova_msg]},
    o LangGraph FAZ APPEND (não substitui). Isso acumula o histórico
    automaticamente — não precisa gerenciar manualmente.
    """

    # Histórico de mensagens — acumulativo via add_messages.
    # Contém: HumanMessage (input), AIMessage (LLM), ToolMessage (resultado de tools)
    messages: Annotated[list[BaseMessage], add_messages]

    # Passos executados pelo agente — para justificativa estruturada.
    # Cada AgentStep tem: tipo (plan/retrieve/tool_call/synthesize), detalhe, duração.
    steps: list[AgentStep]

    # Fontes RAG usadas — para citação na resposta.
    # Ex: ["politica_credito.md", "faq_pj.md"]
    sources: list[str]

    # ID do cliente — propagado para logs e tracing.
    customer_id: str

    # Contadores de tokens — para métricas e estimativa de custo.
    tokens_in: int
    tokens_out: int
