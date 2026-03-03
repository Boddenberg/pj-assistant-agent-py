# =============================================================================
# Agent — Agente de IA Generativa com LangGraph
# =============================================================================
# Esta camada contém toda a lógica do agente inteligente:
#
#   state.py       → Estado compartilhado entre os nós do grafo
#   prompts.py     → Prompts versionados (system + planner)
#   tools.py       → Ferramentas que o agente pode usar
#   graph.py       → Grafo de execução LangGraph (o "cérebro")
#   runner.py      → Fachada para invocar o agente
#   onboarding/    → Fluxo de abertura de conta (subpackage)
#     fields.py        → Enum, sequência, prompts, labels, hints
#     validators.py    → Validação de formato inline
#     state_machine.py → State machine (campo atual/próximo)
#     responses.py     → Gerador de resposta determinística
#     intent.py        → Detecção de intenção de onboarding
#
# Fluxo simplificado:
#   BFA chama runner.run_agent()
#     → runner monta o contexto inicial
#     → graph.agent_graph processa (planner → tools → synthesizer)
#     → runner empacota a resposta
#     → BFA recebe AgentResponse
# =============================================================================
