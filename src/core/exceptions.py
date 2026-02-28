"""
Exceções de domínio do agente.

Hierarquia simples:
  AgentError (base)
  ├── InputValidationError    → entrada inválida (400)
  ├── ToolExecutionError      → tool falhou (500)
  ├── RAGRetrievalError       → RAG falhou (500)
  └── CostLimitExceededError  → custo excedeu limite (429)

Cada exceção mapeia para um HTTP status code no routes.py.
Isso mantém a camada de domínio desacoplada do framework HTTP.
"""


class AgentError(Exception):
    """Erro base do agente. Todas as exceções de domínio herdam daqui."""


class InputValidationError(AgentError):
    """
    Entrada inválida ou potencialmente maliciosa.

    Disparada quando:
      - Input está vazio
      - Input excede tamanho máximo
      - Input contém padrão de prompt injection
    """


class ToolExecutionError(AgentError):
    """
    Falha ao executar uma tool do agente.

    Disparada quando:
      - Tool retorna erro inesperado
      - Timeout na execução da tool
      - Dados de entrada da tool são inválidos
    """


class RAGRetrievalError(AgentError):
    """
    Falha ao recuperar contexto da base vetorial.

    Disparada quando:
      - ChromaDB não está acessível
      - Embedding model falha
      - Busca retorna erro
    """


class CostLimitExceededError(AgentError):
    """
    Custo estimado excedeu o limite por request.

    Disparada quando:
      - Total de tokens × preço > max_cost_per_request_usd
      - Protege contra loops infinitos ou queries muito caras
    """
