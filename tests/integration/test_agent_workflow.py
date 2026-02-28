"""
Testes do workflow do agente — verifica estrutura do grafo LangGraph.

Testa a estrutura do grafo SEM chamar o LLM:
  1. O grafo compila sem erros?
  2. A função de roteamento (should_continue) funciona?
  3. Com tool_calls → vai para "tools"?
  4. Sem tool_calls → vai para "synthesize"?

Por que NÃO testamos execução real do grafo?
  - Precisaria de API key OpenAI (custo + flaky)
  - Em CI, usamos mocks do LLM
  - Aqui focamos na LÓGICA do grafo, não na resposta do LLM

Diagrama do grafo testado:
  START → planner →─┬─ has tool_calls? → tools → executor ─┐
                     │                                       │
                     └─ no tool_calls? → synthesizer → END   │
                     ┌───────────────────────────────────────┘
                     └─ has tool_calls? → tools (loop)
                        no tool_calls? → synthesizer → END
"""

import pytest
from src.agent.graph import build_graph, should_continue
from src.agent.state import AgentState


class TestAgentGraph:
    """Testes estruturais do grafo LangGraph."""

    def test_graph_compiles(self):
        """Grafo deve compilar sem erros.

        build_graph() faz:
          1. Cria StateGraph com AgentState
          2. Adiciona 4 nodes (planner, tools, executor, synthesizer)
          3. Adiciona edges + conditional edges
          4. Compila → retorna CompiledStateGraph

        Se qualquer node/edge estiver mal configurado,
        a compilação falha com erro descritivo.
        """
        graph = build_graph()
        assert graph is not None

    def test_should_continue_no_tool_calls(self):
        """Sem tool_calls na última mensagem → deve sintetizar resposta.

        Cenário: O LLM respondeu diretamente sem precisar de tools.
        Ex: pergunta simples que não precisa de dados.
        """
        from langchain_core.messages import AIMessage

        # AIMessage SEM tool_calls → resposta direta do LLM
        msg = AIMessage(content="Resposta direta")

        # Monta o state mínimo do LangGraph
        state: AgentState = {
            "messages": [msg],
            "steps": [],
            "sources": [],
            "customer_id": "x",
            "tokens_in": 0,
            "tokens_out": 0,
        }

        # Deve ir para "synthesize" (não precisa de tools)
        result = should_continue(state)
        assert result == "synthesize"

    def test_should_continue_with_tool_calls(self):
        """Com tool_calls na última mensagem → deve executar tools.

        Cenário: O LLM decidiu que precisa analisar transações
        antes de responder. Ele gerou um tool_call.
        """
        from langchain_core.messages import AIMessage

        # AIMessage COM tool_calls → LLM quer chamar uma tool
        msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "analyze_transactions",
                "args": {"transactions_json": "[]"},
                "id": "1",
            }],
        )

        state: AgentState = {
            "messages": [msg],
            "steps": [],
            "sources": [],
            "customer_id": "x",
            "tokens_in": 0,
            "tokens_out": 0,
        }

        # Deve ir para "tools" (executar a tool chamada pelo LLM)
        result = should_continue(state)
        assert result == "tools"
