Context: cartoes

# Fatura do Cartão de Crédito

## Estrutura da fatura

Cada fatura é mensal e contém:
- **Mês de referência** (ex.: 2026-03)
- **Data de fechamento** — dia em que a fatura fecha
- **Data de vencimento** — dia em que a fatura deve ser paga
- **Valor total** — soma de todas as transações do período
- **Pagamento mínimo** — 15% do valor total da fatura
- **Juros** — valor de juros (se houver atraso)
- **Status** da fatura

## Status da fatura

| Status | Significado |
|--------|-------------|
| `open` | Fatura aberta, ainda acumulando compras |
| `closed` | Fatura fechada, aguardando pagamento |
| `paid` | Fatura paga integralmente |
| `partially_paid` | Fatura paga parcialmente |

## Geração automática

Se o cliente consultar uma fatura de um mês que ainda não existe no sistema, ela é gerada automaticamente a partir das transações do cartão naquele período.

## Pagar a fatura

O cliente pode pagar a fatura de três formas:
- **Total** — paga o valor integral da fatura
- **Mínimo** — paga 15% do valor total
- **Personalizado** — paga um valor escolhido pelo cliente (deve ser maior que zero)

O pagamento é debitado do saldo da conta corrente. Após o pagamento, o limite disponível do cartão é restaurado pelo valor pago.

Se o pagamento for do valor mínimo ou de um valor menor que o total, a fatura fica com status `partially_paid`. Se for do valor total, fica `paid`.
