Context: pix

# PIX via Cartão de Crédito

## O que é

O cliente pode fazer transferências PIX usando o limite do cartão de crédito, em vez do saldo da conta. O valor é cobrado na fatura do cartão, com possibilidade de parcelamento.

## Como funciona

1. O cliente informa que quer pagar o PIX com cartão de crédito
2. O sistema verifica se o cartão tem a função PIX no crédito habilitada
3. O valor é calculado com taxa e parcelamento

## Taxa

- Taxa fixa de **2% por parcela**
- Fórmula: `valor_total = valor × (1 + 0,02 × (parcelas - 1))`

### Exemplos

| Valor | Parcelas | Taxa | Total |
|-------|----------|------|-------|
| R$ 1.000 | 1x | 0% | R$ 1.000,00 |
| R$ 1.000 | 2x | 2% | R$ 1.020,00 |
| R$ 1.000 | 3x | 4% | R$ 1.040,00 |
| R$ 1.000 | 6x | 10% | R$ 1.100,00 |
| R$ 1.000 | 12x | 22% | R$ 1.220,00 |

## Máximo de parcelas

Até **12 parcelas**.

## Requisitos

- O cartão precisa ter PIX no crédito habilitado (`pix_credit_enabled = true`)
- O limite de PIX no crédito disponível deve ser suficiente: `pix_credit_used + valor_total ≤ pix_credit_limit`

## Observação importante

O PIX via cartão de crédito NÃO aparece no extrato da conta corrente. Ele é registrado exclusivamente como transação do cartão de crédito e aparece na fatura.
