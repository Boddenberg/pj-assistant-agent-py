"""
Modelos de domínio — contratos de entrada e saída do agente.

Todos os dados que trafegam no sistema têm um modelo Pydantic.
Isso garante:
  - Validação automática (se o BFA mandar lixo, falha cedo)
  - Serialização/deserialização JSON consistente
  - Documentação via OpenAPI (FastAPI gera docs automaticamente)

Fluxo dos dados:
  BFA (Go) → AgentRequest → [Agente] → AgentResponse → BFA (Go)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


# =============================================================================
# Modelos do Cliente — vêm do BFA (Profile API + Transactions API)
# =============================================================================

class CustomerProfile(BaseModel):
    """
    Perfil do cliente PJ — enviado pelo BFA após consultar a Profile API.

    Esses dados são usados pelo agente para:
      - Avaliar risco de crédito (credit_score)
      - Personalizar recomendações (segment, revenue_range)
      - Contextualizar o histórico (account_since)
    """
    customer_id: str                # ID único do cliente no sistema
    company_name: str               # Razão social da empresa
    segment: str = ""               # Segmento: "Médias Empresas", "Grandes Empresas", etc.
    revenue_range: str = ""         # Faixa de faturamento: "R$ 1M - R$ 10M"
    account_since: str = ""         # Data de abertura da conta
    credit_score: int = 0           # Score de crédito (0-1000)


class Transaction(BaseModel):
    """
    Transação financeira — enviada pelo BFA após consultar a Transactions API.

    Cada transação representa uma movimentação na conta do cliente.
    Valores negativos = saídas (pagamentos). Positivos = entradas (recebimentos).
    """
    id: str                         # ID único da transação
    date: str                       # Data da transação (ISO 8601)
    amount: float                   # Valor em reais (negativo = saída)
    category: str                   # Categoria: "Fornecedores", "Vendas", "Folha", etc.
    description: str = ""           # Descrição livre da transação


# =============================================================================
# Modelos do Agente — controle interno do workflow
# =============================================================================

class StepType(str, Enum):
    """
    Tipos de passos que o agente pode executar.

    Cada passo é registrado para rastreabilidade (reasoning).
    O BFA e o front podem exibir esses passos ao usuário.
    """
    PLAN = "plan"                   # Planejamento: decidir o que fazer
    RETRIEVE = "retrieve"           # Busca RAG: consultar base de conhecimento
    TOOL_CALL = "tool_call"         # Execução de tool: analisar dados
    SYNTHESIZE = "synthesize"       # Síntese: gerar resposta final


class AgentStep(BaseModel):
    """
    Registro de um passo executado pelo agente.

    Esses registros formam o "reasoning" — a justificativa estruturada
    de como o agente chegou à resposta. Útil para:
      - Auditoria (por que o agente disse X?)
      - Debug (qual passo demorou mais?)
      - Transparência (mostrar ao cliente o raciocínio)
    """
    step: StepType                  # Tipo do passo
    detail: str                     # Descrição do que foi feito
    duration_ms: float = 0.0        # Tempo gasto nesse passo (ms)


# =============================================================================
# Contratos de Entrada/Saída — interface com o BFA
# =============================================================================

class ChatMessage(BaseModel):
    """
    Mensagem do histórico de conversa — enviada pelo BFA.

    O BFA mantém as últimas 5 interações do cliente na sessão
    e envia neste formato para dar continuidade à conversa.
    Cada par query/answer representa um turno completo.
    """
    query: str                                          # Pergunta do cliente naquele turno
    answer: str                                         # Resposta do agente naquele turno


class AgentRequest(BaseModel):
    """
    Payload de entrada do agente.

    Aceita vários formatos:

      Mínimo (só query):
        { "query": "Como abrir uma conta PJ?" }

      Com histórico (BFA envia últimos 5 turnos):
        {
          "query": "E quais documentos preciso?",
          "history": [
            { "query": "Quero abrir conta", "answer": "Para abrir..." }
          ]
        }

      Completo (BFA envia tudo):
        {
          "customer_id": "cust-001",
          "profile": { ... },
          "transactions": [ ... ],
          "history": [ ... ],
          "query": "Qual minha situação financeira?"
        }

    Quando customer_id/profile não são enviados, o agente responde
    com base apenas na query + knowledge base (sem dados do cliente).
    """
    query: str                                          # Pergunta do cliente (obrigatório)
    customer_id: str = "anonymous"                       # ID do cliente (opcional)
    profile: CustomerProfile | None = None               # Perfil (opcional)
    transactions: list[Transaction] = Field(             # Transações (opcional)
        default_factory=list,
    )
    history: list[ChatMessage] = Field(                  # Histórico de conversa (até 5 turnos)
        default_factory=list,
    )
    validation_error: str = ""                            # Erro do BFA ao validar último campo


class AgentMetadata(BaseModel):
    """
    Metadados de observabilidade — NÃO usados para decisão do BFA.

    Servem para monitoramento, debug e auditoria.
    O BFA pode logar/encaminhar para dashboards, mas não usa para routing.
    """
    reasoning: list[AgentStep] = Field(default_factory=list)   # Passos executados
    sources: list[str] = Field(default_factory=list)           # Fontes RAG consultadas
    tokens_used: int = 0                                       # Total tokens consumidos
    estimated_cost_usd: float = 0.0                            # Custo estimado USD


class AgentResponse(BaseModel):
    """
    Resposta que o agente devolve ao BFA (Go).

    Campos de DECISÃO (o BFA usa para routing/strategy):
      - context     → strategy pattern: qual fluxo executar (onboarding, etc.)
      - intent      → intenção classificada do cliente (open_account, check_balance, etc.)
      - confidence  → confiança da resposta (0.0-1.0). Abaixo de 0.5 = escalar para humano
      - suggested_actions → sugestões para o front renderizar como opções ao cliente

    Campos de APRESENTAÇÃO (BFA repassa ao front):
      - answer      → texto para exibir ao cliente no chat

    Campos de OBSERVABILIDADE (dashboards, auditoria):
      - metadata    → tokens, custo, reasoning, sources
    """
    customer_id: str                                           # ID do cliente
    answer: str                                                # Resposta textual para o cliente
    context: str | None = None                                 # Strategy pattern do BFA
    intent: str | None = None                                  # Intenção classificada
    confidence: float = 1.0                                    # Confiança (0.0-1.0)
    suggested_actions: list[str] = Field(default_factory=list)  # Sugestões para o front
    current_field: str | None = None                           # Campo de onboarding atual (BFA valida)
    field_value: str | None = None                             # Valor cru do campo (BFA valida)
    metadata: AgentMetadata = Field(default_factory=AgentMetadata)  # Observabilidade
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
    )
