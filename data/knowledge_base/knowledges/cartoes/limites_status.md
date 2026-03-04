Context: cartoes

# Cartão de Crédito — Limites e Status

## Limites do cartão

Cada cartão tem os seguintes limites:
- **Limite total** (credit_limit): valor máximo de crédito do cartão.
- **Limite disponível** (available_limit): quanto ainda pode ser gasto.
- **Limite utilizado** (used_limit): quanto já foi gasto.
- **Limite diário** (daily_limit): limite máximo por dia.
- **Limite por transação** (single_transaction_limit): limite máximo por compra individual.

## PIX no crédito

Alguns cartões permitem fazer PIX usando o limite do cartão:
- **PIX crédito habilitado** (pix_credit_enabled): se o cartão permite essa função.
- **Limite PIX crédito** (pix_credit_limit): limite específico para PIX no crédito.
- **PIX crédito utilizado** (pix_credit_used): quanto já foi usado para PIX no crédito.

## Status do cartão

| Status | Significado |
|--------|-------------|
| `pending_activation` | Cartão emitido, aguardando ativação |
| `active` | Cartão ativo e funcionando |
| `blocked` | Cartão bloqueado temporariamente |
| `cancelled` | Cartão cancelado definitivamente |

## Transições de status

- **Ativar**: somente de `pending_activation` para `active`
- **Bloquear**: somente de `active` para `blocked`
- **Desbloquear**: somente de `blocked` para `active`
- **Cancelar**: de qualquer status (exceto já cancelado) para `cancelled`

## Controles

O cartão possui indicadores de controle definidos na emissão:
- Pagamento por aproximação (contactless)
- Compras internacionais
- Compras online
