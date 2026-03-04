Context: pix

# Comprovante PIX

## O que é

Após cada transferência PIX concluída, é gerado automaticamente um comprovante digital (receipt).

## Dados do comprovante

O comprovante contém:
- Valor da transferência
- Valor original (se houve taxa de cartão de crédito)
- Taxa cobrada (se PIX via cartão)
- Valor total (com taxa)
- Número de parcelas (se PIX via cartão)
- Dados do remetente: nome, documento (CNPJ), banco, agência, conta
- Dados do destinatário: nome, documento, banco, agência, conta, chave PIX
- Código End-to-End (identificador único da transação)
- Forma de pagamento (saldo ou cartão de crédito)
- Data e hora da execução

## Direção

Cada comprovante tem uma direção:
- `sent` — PIX enviado pelo cliente
- `received` — PIX recebido pelo cliente

Quando um PIX é realizado, comprovantes são gerados para ambos os lados (remetente e destinatário).
