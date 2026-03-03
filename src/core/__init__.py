# =============================================================================
# Core — Camada de domínio: configuração, modelos e exceções.
# Não depende de nenhuma outra camada. Tudo aqui é "puro".
#
#   config.py      → Configuração centralizada (pydantic-settings)
#   exceptions.py  → Exceções de domínio (hierarquia AgentError)
#   models/        → Modelos Pydantic (subpackage)
#     customer.py    → CustomerProfile, Transaction
#     agent.py       → StepType, AgentStep, AgentMetadata
#     contracts.py   → ChatMessage, CollectedField, AgentRequest, AgentResponse
# =============================================================================
