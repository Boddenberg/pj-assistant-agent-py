"""
Modelos do cliente — dados que vêm do BFA (Profile API + Transactions API).

Estes modelos representam o contexto financeiro do cliente PJ
que o BFA envia ao agente para personalizar as respostas.
"""

from __future__ import annotations

from pydantic import BaseModel


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
