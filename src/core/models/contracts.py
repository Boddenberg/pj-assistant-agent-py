"""
Contratos de entrada e saída — interface com o BFA (Go).

Todos os dados que trafegam entre BFA ↔ Agente são definidos aqui.
Isso garante:
  - Validação automática (se o BFA mandar lixo, falha cedo)
  - Serialização/deserialização JSON consistente
  - Documentação via OpenAPI (FastAPI gera docs automaticamente)

Fluxo dos dados:
  BFA (Go) → AgentRequest → [Agente] → AgentResponse → BFA (Go)
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from src.core.models.customer import CustomerProfile, Transaction
from src.core.models.agent import AgentMetadata


class ChatMessage(BaseModel):
    """
    Mensagem do histórico de conversa — enviada pelo BFA.

    O BFA mantém as últimas interações do cliente na sessão
    e envia neste formato para dar continuidade à conversa.

    Campos base:
      - query:     O que o cliente digitou naquele turno
      - answer:    O que o agente respondeu

    Campos de onboarding (preenchidos pelo BFA):
      - step:      Qual step/campo aquele turno representava (ex: "cnpj", "email")
                   None se não é onboarding
      - validated: Se o BFA validou aquele campo com sucesso
                   None se não é onboarding
    """
    query: str                                          # Pergunta do cliente naquele turno
    answer: str                                         # Resposta do agente naquele turno
    step: str | None = None                             # Step do onboarding (ex: "cnpj")
    validated: bool | None = None                       # BFA validou? True/False/None


class CollectedField(BaseModel):
    """
    Campo já coletado e validado em sessão anterior — enviado pelo BFA na retomada.

    Usado quando o cliente interrompeu o onboarding e volta a continuar.
    O BFA envia os campos já persistidos para que o agente retome de onde parou,
    sem re-coletar dados que já foram validados.

    Também serve para qualquer fluxo conversacional campo-a-campo que precise
    de retomada (ex: atualização cadastral, solicitação de crédito).
    """
    key: str                                            # Nome do campo (ex: "cnpj", "email")
    value: str                                          # Valor validado (ex: "19439335000139")
    validated: bool = True                              # Se foi validado pelo BFA


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

      Com retomada de dados (BFA envia campos já coletados):
        {
          "query": "Quero continuar abrindo minha conta",
          "collected_data": [
            { "key": "cnpj", "value": "19439335000139", "validated": true },
            { "key": "razaoSocial", "value": "Toquinho Ltda", "validated": true }
          ]
        }

      Completo (BFA envia tudo):
        {
          "customer_id": "cust-001",
          "profile": { ... },
          "transactions": [ ... ],
          "history": [ ... ],
          "collected_data": [ ... ],
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
    collected_data: list[CollectedField] = Field(        # Campos já coletados (retomada)
        default_factory=list,
    )
    validation_error: str = ""                            # Erro do BFA ao validar último campo


class AgentResponse(BaseModel):
    """
    Resposta que o agente devolve ao BFA (Go).

    Campos de DECISÃO (o BFA usa para routing/strategy):
      - context     → strategy pattern: qual fluxo executar (onboarding, etc.)
      - intent      → intenção classificada do cliente (open_account, check_balance, etc.)
      - confidence  → confiança da resposta (0.0-1.0). Abaixo de 0.5 = escalar para humano
      - suggested_actions → sugestões para o front renderizar como opções ao cliente

    Campos de ONBOARDING (BFA usa para saber o que validar):
      - step        → step atual que o cliente respondeu (ex: "cnpj"). BFA usa pra
                      cair no método de validação correto. null = não é onboarding.
      - field_value → valor cru que o cliente digitou. BFA valida.
      - next_step   → próximo step que será pedido. BFA pode preparar o método.

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
    step: str | None = None                                    # Step atual do onboarding (BFA valida)
    field_value: str | None = None                             # Valor cru do campo (BFA valida)
    next_step: str | None = None                               # Próximo step a ser pedido
    is_restart: bool = False                                   # True se cliente pediu para recomeçar (BFA deve limpar sessão)
    max_retries_exceeded: bool = False                           # True se excedeu tentativas (BFA NÃO deve adicionar ao history)
    metadata: AgentMetadata = Field(default_factory=AgentMetadata)  # Observabilidade
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
    )
