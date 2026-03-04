Context: debito

# Compras no Débito

## Como funciona

O cliente pode realizar compras no débito usando o cartão vinculado à conta. O valor é debitado imediatamente do saldo disponível.

## Dados da compra

- **Valor** (obrigatório, maior que zero)
- **Nome do estabelecimento** (obrigatório)
- **Categoria** (opcional, padrão: "other")
- **Descrição** (opcional)

## Saldo insuficiente

Se o saldo disponível na conta for menor que o valor da compra, a compra NÃO é recusada com erro. Em vez disso, retorna com status `insufficient_funds`, indicando que não foi possível completar.

## Status

| Status | Significado |
|--------|-------------|
| `completed` | Compra concluída com sucesso |
| `insufficient_funds` | Saldo insuficiente para a compra |

## Resposta

Após a compra, o sistema retorna:
- ID da transação
- Status da operação
- Valor debitado
- Novo saldo da conta
- Data e hora da transação
