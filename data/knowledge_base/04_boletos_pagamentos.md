# Boletos e Pagamento de Contas

## O que são Boletos

O boleto bancário é um dos principais meios de pagamento para empresas no Brasil. A conta PJ permite validar, pagar e acompanhar o histórico de boletos e contas de consumo (água, luz, telefone, impostos).

## Tipos de Boleto

O sistema aceita os seguintes tipos:

- **Boleto bancário (bank_slip)**: boleto emitido por bancos para cobrança de valores. Identificado por código de barras de 47 dígitos.
- **Conta de concessionária (utility)**: contas de serviços públicos como água, energia, gás e telefone. Identificado por código de barras de 48 dígitos.
- **Guia de impostos (tax_slip)**: guias para pagamento de tributos municipais, estaduais ou federais.
- **Guia governamental (government)**: guias de taxas e serviços governamentais.

## Formas de Entrada do Código de Barras

O cliente pode informar o código de barras de quatro formas:

- **Digitação manual (typed)**: digitar os números do código de barras.
- **Colar código (pasted)**: colar a linha digitável copiada de outro lugar.
- **Câmera/Scanner (camera_scan)**: escanear o código de barras com a câmera.
- **Upload de arquivo (file_upload)**: enviar imagem ou PDF do boleto.

## Validação de Boleto

Antes de pagar, o cliente pode validar um boleto para verificar suas informações. A validação funciona da seguinte forma:

### Boleto bancário (47 dígitos)

- Os 3 primeiros dígitos identificam o banco emissor.
- O valor é extraído das posições 37 a 47 do código (em centavos, dividido por 100).
- A data de vencimento é calculada a partir de uma data base (07/10/1997) somada ao fator de vencimento (posições 33 a 37).

### Conta de concessionária (48 dígitos)

- O primeiro dígito identifica o segmento (8 indica serviço público).
- O valor é extraído das posições 4 a 15 do código (em centavos, dividido por 100).

### Código de barras (44 dígitos)

- Formato bruto do código de barras de boleto bancário.
- Os 3 primeiros dígitos identificam o banco.

Se o código não tiver 44, 47 ou 48 dígitos, é considerado inválido.

## Pagamento de Boleto

Para pagar um boleto, o cliente deve informar:

1. **Código de barras ou linha digitável**: obrigatório.
2. **Conta de origem (account_id)**: obrigatória.
3. **Chave de idempotência**: obrigatória para evitar pagamentos duplicados.
4. **Valor**: opcional — se não informado, usa o valor extraído do código de barras.

### Validações do Pagamento

- O código de barras deve ser válido (passa pela mesma validação descrita acima).
- O saldo da conta deve ser suficiente para cobrir o valor do boleto.
- O valor não pode exceder o limite de pagamento de boletos configurado (single_bill).

### Processamento

Após a validação:

1. O valor é debitado do saldo da conta.
2. A transação é registrada no extrato como "pagamento de boleto" (bill_payment), na categoria "contas".
3. O status do pagamento muda para "concluído" (completed).

## Status do Pagamento

Um pagamento de boleto pode ter os seguintes estados:

- **Pendente de validação (pending_validation)**: boleto sendo verificado.
- **Validado (validated)**: boleto verificado, pronto para pagamento.
- **Pendente (pending)**: pagamento em processamento inicial.
- **Processando (processing)**: pagamento sendo processado.
- **Agendado (scheduled)**: pagamento programado para data futura.
- **Concluído (completed)**: pagamento realizado com sucesso.
- **Falhou (failed)**: pagamento não concluído por erro.
- **Cancelado (cancelled)**: pagamento cancelado pelo cliente.
- **Expirado (expired)**: boleto com prazo de pagamento vencido.

## Cancelamento de Pagamento

Apenas pagamentos com status "pendente", "agendado" ou "validado" podem ser cancelados. Pagamentos já concluídos não podem ser revertidos.

## Histórico de Boletos

O cliente pode consultar o histórico de todos os pagamentos de boletos realizados, incluindo:

- Valor pago.
- Data do pagamento.
- Status atual.
- Tipo do boleto.
- Código de barras.
- Banco emissor (para boletos bancários).
