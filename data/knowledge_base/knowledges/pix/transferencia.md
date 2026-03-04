Context: pix

# Transferência PIX

## Como funciona

O PIX é instantâneo e pode ser feito 24 horas por dia, 7 dias por semana.

Para fazer um PIX, o cliente precisa informar:
- **Chave PIX do destinatário** (CNPJ, e-mail, telefone ou chave aleatória)
- **Valor** (deve ser maior que zero)
- **Descrição** (opcional)

## Fontes de pagamento

O PIX pode ser pago de duas formas:

### 1. Saldo da conta (padrão)
- O valor é debitado diretamente do saldo disponível.
- O cliente precisa ter saldo suficiente.

### 2. Cartão de crédito
- O valor é cobrado no cartão de crédito do cliente.
- O cartão precisa ter a função PIX no crédito habilitada (pix_credit_enabled).
- Taxa de 2% por parcela.
- Pode ser parcelado em até 12 vezes.
- Fórmula do valor total: `valor × (1 + 0,02 × (parcelas - 1))`
- Exemplo: PIX de R$ 1.000 em 3x = R$ 1.000 × (1 + 0,02 × 2) = R$ 1.040,00
- O valor aparece na fatura do cartão, NÃO no extrato da conta.

## Restrições

- Não é possível fazer PIX para si mesmo (mesma chave do cliente).
- Respeita o limite de transação individual (single PIX limit).
- Respeita o limite diário de PIX.

## Resultado

O PIX é processado instantaneamente. Após a execução, o status da transferência é `completed`.
