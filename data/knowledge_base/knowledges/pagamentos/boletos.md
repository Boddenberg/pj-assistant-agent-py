Context: boletos

# Pagamento de Boletos

## Como funciona

O cliente pode pagar boletos bancários e contas de consumo (concessionárias) diretamente pelo app.

## Métodos de entrada do código de barras

- **Digitado** (typed) — cliente digita o código manualmente
- **Colado** (pasted) — cliente cola de outro lugar
- **Câmera** (camera_scan) — leitura por câmera do celular
- **Arquivo** (file_upload) — upload de imagem do boleto

## Validação do código de barras

Antes de pagar, o sistema valida o código:

### Boleto bancário (bank_slip)
- Linha digitável com 47 dígitos
- Ou código de barras com 44 dígitos
- O sistema extrai automaticamente: banco emissor, valor e data de vencimento

### Conta de consumo / concessionária (utility)
- Linha digitável com 48 dígitos
- O sistema extrai automaticamente o valor

## Dados extraídos após validação

- Tipo do boleto (boleto bancário ou concessionária)
- Código de barras e linha digitável
- Valor
- Data de vencimento
- Nome do beneficiário
- Banco emissor
- Desconto, juros e multa (se aplicável)
- Valor total a pagar

## Restrições

- O saldo disponível na conta deve ser suficiente para cobrir o valor do boleto.
- Respeita o limite de transação individual para pagamento de boletos.

## Status do pagamento

| Status | Significado |
|--------|-------------|
| `pending` | Pagamento registrado e processado |
| `scheduled` | Agendado para data futura (quando o cliente informa uma data agendada) |
