Context: conta

# Limites de Transação

## O que são

O sistema define limites individuais para cada tipo de transação, controlando o valor máximo por operação e por dia.

## Tipos de limite

Cada tipo de transação possui:
- **Limite por transação** (single_limit): valor máximo por operação individual
- **Limite diário** (daily_limit): valor máximo por dia
- **Limite mensal** (monthly_limit): valor máximo por mês
- **Limite noturno por transação** (nightly_single_limit): limite individual no período noturno
- **Limite noturno diário** (nightly_daily_limit): limite diário no período noturno

## Acompanhamento

O sistema rastreia:
- Quanto do limite diário já foi utilizado (daily_used)
- Quanto do limite mensal já foi utilizado (monthly_used)

## Tipos de transação com limite

Os limites se aplicam a:
- PIX
- TED
- DOC
- Pagamento de boletos
- Compras no débito

O cliente pode consultar e alterar seus limites pelo app.
