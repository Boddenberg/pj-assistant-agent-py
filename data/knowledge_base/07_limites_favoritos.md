# Limites, Favoritos e Notificações

## Limites de Transação

O cliente PJ possui limites configuráveis para diferentes tipos de operação. Os limites ajudam a controlar gastos e proteger a conta contra movimentações indevidas.

### Tipos de Limite

Os limites são definidos por tipo de transação:

- **PIX**: limites para transferências PIX.
- **TED**: limites para transferências TED.
- **DOC**: limites para transferências DOC.
- **Pagamento de boleto (bill_payment)**: limites para pagamento de contas.
- **Compra no débito (debit_purchase)**: limites para compras com cartão de débito.
- **Compra no crédito (credit_purchase)**: limites para compras com cartão de crédito.

### Controles por Limite

Cada tipo de transação possui os seguintes controles:

- **Limite diário (daily_limit)**: valor máximo permitido em um dia.
- **Uso diário (daily_used)**: quanto já foi utilizado no dia.
- **Limite mensal (monthly_limit)**: valor máximo permitido no mês.
- **Uso mensal (monthly_used)**: quanto já foi utilizado no mês.
- **Limite por transação (single_limit)**: valor máximo por operação individual.
- **Limite noturno por transação (nightly_single_limit)**: valor máximo por operação em horário noturno.
- **Limite noturno diário (nightly_daily_limit)**: valor máximo total em horário noturno.

### Limites por Segmento

Os limites variam conforme o porte da empresa:

| Segmento | PIX Diário | PIX por Transação | PIX Mensal |
|----------|-----------|-------------------|------------|
| Startup | R$ 5.000 | R$ 2.000 | R$ 50.000 |
| Small Business | R$ 20.000 | R$ 10.000 | R$ 400.000 |
| Middle Market | R$ 100.000 a R$ 200.000 | R$ 50.000 a R$ 100.000 | R$ 2.000.000 a R$ 4.000.000 |
| Corporate | R$ 500.000 | R$ 200.000 | R$ 10.000.000 |

### Alteração de Limites

O cliente pode solicitar a alteração dos limites de qualquer tipo de transação. A alteração é feita por tipo de operação.

## Contatos Favoritos

O cliente pode salvar destinatários frequentes como favoritos para agilizar futuras transferências e pagamentos.

### Dados do Favorito

Cada favorito contém:

- **Apelido (nickname)**: nome curto para identificar o favorito. Campo obrigatório.
- **Nome do destinatário (recipient_name)**: nome completo do beneficiário. Campo obrigatório.
- **Documento do destinatário (recipient_document)**: CPF ou CNPJ do beneficiário.
- **Tipo de destino (destination_type)**: pode ser PIX, TED, DOC ou outro.
- **Dados PIX**: tipo e valor da chave PIX.
- **Dados bancários**: banco, agência e conta do destinatário.
- **Contador de uso**: registra quantas vezes o favorito foi utilizado.
- **Último uso**: data da última vez que o favorito foi usado.

### Gerenciamento de Favoritos

O cliente pode:

- **Listar favoritos**: ver todos os destinatários salvos.
- **Criar favorito**: adicionar um novo destinatário à lista.
- **Excluir favorito**: remover um destinatário da lista.

## Notificações

O sistema envia notificações para manter o cliente informado sobre movimentações e eventos da conta.

### Canais de Notificação

As notificações podem ser enviadas por:

- **Push**: notificações no aplicativo móvel.
- **E-mail**: mensagens enviadas para o e-mail cadastrado.
- **SMS**: mensagens de texto no celular.
- **In-app**: notificações dentro do aplicativo bancário.

### Prioridade

As notificações têm diferentes níveis de prioridade:

- **Baixa (low)**: informações gerais e dicas.
- **Normal**: movimentações regulares e confirmações.
- **Alta (high)**: alertas de segurança e limites próximos.
- **Urgente (urgent)**: bloqueios, tentativas de fraude e ações imediatas necessárias.

### Gerenciamento de Notificações

O cliente pode:

- **Listar notificações**: ver todas as notificações recebidas.
- **Marcar como lida**: confirmar que visualizou uma notificação específica.

### Tipos de Notificação

O sistema gera notificações para diversos eventos, incluindo:

- Transferências PIX recebidas e enviadas.
- Pagamentos de boletos.
- Alertas de limite próximo.
- Alertas de orçamento atingido.
- Confirmações de operações.
- Alertas de segurança (tentativas de login, bloqueios).
- Vencimento de faturas.
- Atualizações cadastrais.
