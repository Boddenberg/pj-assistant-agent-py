# PIX — Transferências Instantâneas

## O que é o PIX

O PIX é o sistema de pagamentos instantâneos do Banco Central do Brasil. Permite transferências em tempo real, 24 horas por dia, 7 dias por semana, inclusive em feriados. No contexto PJ, o PIX é uma ferramenta essencial para pagamentos a fornecedores, recebimento de clientes e gestão de fluxo de caixa.

## Tipos de Chave PIX

O cliente PJ pode cadastrar os seguintes tipos de chave:

- **CNPJ**: o CNPJ da empresa, limitado a uma chave por CNPJ.
- **E-mail**: endereço de e-mail vinculado à empresa.
- **Telefone (phone)**: número de celular com código do país (+55).
- **Chave aleatória (random)**: código UUID gerado automaticamente pelo sistema.

Não é possível cadastrar chave do tipo CPF para contas PJ. O CPF é reservado para contas de pessoa física.

## Cadastro de Chave PIX

Para registrar uma nova chave PIX:

- O tipo da chave deve ser: cnpj, email, phone ou random.
- Para chaves do tipo random, o valor é gerado automaticamente (UUID).
- Para os demais tipos, o cliente deve informar o valor da chave.
- A chave é vinculada à conta principal do cliente.
- Cada valor de chave é único no sistema — não é possível ter duas chaves com o mesmo valor.

## Status de Chave PIX

- **Ativa (active)**: chave funcionando normalmente.
- **Pendente (pending)**: chave aguardando confirmação.
- **Inativa (inactive)**: chave desativada.
- **Portabilidade solicitada (portability_requested)**: chave em processo de transferência para outro banco.

## Consulta de Chave PIX

O cliente pode buscar uma chave PIX para verificar o destinatário antes de fazer uma transferência. A consulta retorna o nome e os dados do titular da chave.

## Exclusão de Chave PIX

O cliente pode excluir suas chaves PIX a qualquer momento. A exclusão pode ser feita pelo ID da chave ou pelo valor da chave.

## Transferência PIX por Saldo

Para realizar um PIX usando o saldo da conta:

1. O valor deve ser maior que zero.
2. A chave de destino é obrigatória.
3. Uma chave de idempotência é obrigatória para evitar duplicidade.
4. O sistema verifica se o saldo é suficiente para cobrir o valor.
5. Não é permitido fazer PIX para si mesmo (mesma conta ou chave própria).
6. O sistema verifica os limites de PIX configurados (diário e por transação).

Após a transferência, o valor é debitado imediatamente da conta do remetente. Se o destinatário for cliente do mesmo banco, o valor é creditado instantaneamente.

## Detecção Automática de Tipo de Chave

Se o cliente não informar o tipo da chave, o sistema detecta automaticamente:

- Contém "@" → e-mail.
- 36 caracteres com hífens → chave aleatória.
- 14 dígitos → CNPJ.
- 11 dígitos → CPF.
- Começa com "+" → telefone.
- 10 a 13 dígitos → telefone.

## PIX via Cartão de Crédito

O PIX também pode ser realizado usando o limite do cartão de crédito como fonte de pagamento. Essa modalidade é chamada de PIX Crédito.

### Regras do PIX Crédito

- O cartão deve ter a funcionalidade PIX Crédito habilitada (pix_credit_enabled).
- O cartão deve ter limite de PIX Crédito disponível.
- A operação pode ser parcelada.

### Taxas do PIX Crédito

O PIX via cartão de crédito possui uma taxa de 2% por parcela sobre o valor original.

A fórmula de cálculo é:

- **Valor total com taxas** = valor × (1 + 0,02 × (parcelas - 1))
- **Valor da taxa** = valor total com taxas - valor original
- **Valor da parcela** = valor total com taxas ÷ número de parcelas

Exemplos práticos:

| Valor PIX | Parcelas | Taxa por Parcela | Valor Total | Taxa Total | Valor da Parcela |
|-----------|----------|-----------------|-------------|------------|-----------------|
| R$ 100,00 | 1 | 2% | R$ 100,00 | R$ 0,00 | R$ 100,00 |
| R$ 100,00 | 2 | 2% | R$ 102,00 | R$ 2,00 | R$ 51,00 |
| R$ 100,00 | 3 | 2% | R$ 104,00 | R$ 4,00 | R$ 34,67 |
| R$ 100,00 | 6 | 2% | R$ 110,00 | R$ 10,00 | R$ 18,33 |
| R$ 1.000,00 | 12 | 2% | R$ 1.220,00 | R$ 220,00 | R$ 101,67 |

### Onde aparecem as taxas

- O valor do PIX que o destinatário recebe é sempre o valor original, sem taxas.
- As taxas são cobradas do remetente e aparecem somente na fatura do cartão de crédito.
- O comprovante de transferência mostra apenas o valor do PIX (sem taxas).
- No extrato da conta corrente, o PIX via cartão de crédito NÃO aparece — ele aparece apenas na fatura do cartão.

### Limites do PIX Crédito

- O sistema verifica se o limite de PIX Crédito do cartão é suficiente.
- A verificação é: pix_credit_used + valor_total_com_taxas ≤ pix_credit_limit.
- Se exceder, a operação é negada por limite excedido.

## Limites de PIX

O cliente possui limites configuráveis para operações PIX:

- **Limite por transação (single_pix)**: valor máximo por PIX individual.
- **Limite diário (daily_pix)**: valor máximo total de PIX em um dia.

Se o valor do PIX exceder qualquer um desses limites, a operação é recusada.

Os limites variam conforme o segmento do cliente:

| Segmento | Limite Diário | Limite por Transação |
|----------|--------------|---------------------|
| Startup | R$ 5.000 | R$ 2.000 |
| Small Business | R$ 20.000 | R$ 10.000 |
| Middle Market | R$ 100.000 a R$ 200.000 | R$ 50.000 a R$ 100.000 |
| Corporate | R$ 500.000 | R$ 200.000 |

## Comprovante de PIX

Após cada transferência PIX, um comprovante é gerado automaticamente contendo:

- Identificador único da transação (end_to_end_id).
- Dados do remetente (nome, documento, banco, conta).
- Dados do destinatário (nome, documento, chave PIX).
- Valor da transferência.
- Data e hora da execução.
- Fonte de pagamento (saldo ou cartão de crédito).
- Status da operação.

O comprovante do remetente tem direção "sent" e o do destinatário "received".

Para PIX via cartão de crédito, o comprovante do remetente inclui informações de parcelas e taxas, mas o comprovante do destinatário mostra apenas o valor recebido.

## Cancelamento de PIX

Apenas transferências com status "pendente" ou "agendada" podem ser canceladas. Transferências já concluídas não podem ser revertidas pelo sistema.

## PIX Agendado

O cliente pode agendar transferências PIX para datas futuras. Veja o documento sobre Transferências Agendadas para mais detalhes.
