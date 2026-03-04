"""
Modelos de domínio — contratos de entrada e saída do agente.

Módulos internos:
  customer.py  → CustomerProfile, Transaction
  agent.py     → StepType, AgentStep, AgentMetadata
  contracts.py → ChatMessage, CollectedField, AgentRequest, AgentResponse
"""

# Re-export público — mantém backwards compatibility.
# Quem importa `from src.core.models import X` continua funcionando.

from src.core.models.customer import (  # noqa: F401
    CustomerProfile,
    Transaction,
)

from src.core.models.agent import (  # noqa: F401
    StepType,
    AgentStep,
    AgentMetadata,
)

from src.core.models.contracts import (  # noqa: F401
    ChatMessage,
    CollectedField,
    AgentRequest,
    AgentResponse,
)

from src.core.models.financial import (  # noqa: F401
    FinancialContext,
    AccountContext,
    CardsContext,
    CardInfo,
    CardInvoice,
    PixContext,
    PixKey,
    PixTransfer,
    PixScheduledTransfer,
    BillingContext,
    BillPayment,
    DebitPurchase,
    CompanyProfile,
    TransactionItem,
    TransactionsContext,
)

from src.core.models.evaluation import (  # noqa: F401
    Verdict,
    ConversationTurn,
    EvaluationRequest,
    EvaluationResponse,
    EvaluationMetadata,
    CriterionResult,
)
