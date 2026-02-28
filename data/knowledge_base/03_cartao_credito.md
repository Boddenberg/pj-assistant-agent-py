# Cartão de Crédito Corporativo

## O que é o Cartão de Crédito PJ

O cartão de crédito corporativo é um meio de pagamento vinculado à conta PJ que permite compras a crédito, pagamento de fornecedores e até transferências PIX usando o limite de crédito. É uma ferramenta fundamental para gestão do fluxo de caixa empresarial.

## Solicitar um Cartão

Para solicitar um novo cartão de crédito, o cliente deve informar a conta vinculada. O sistema oferece as seguintes opções:

### Bandeiras Disponíveis

- Visa (padrão)
- Mastercard
- Elo
- Amex

### Tipos de Cartão

- **Corporativo (corporate)**: cartão principal da empresa, padrão na solicitação.
- **Virtual**: cartão digital para compras online, sem cartão físico.
- **Adicional**: cartão extra vinculado ao mesmo limite para colaboradores.

### Configurações Padrão

Ao solicitar um cartão, os seguintes valores padrão são aplicados:

- Limite de crédito solicitado: R$ 10.000,00.
- Dia de fechamento da fatura (billing_day): dia 10.
- Dia de vencimento da fatura (due_day): dia 20.
- Limite diário de transações: R$ 10.000,00.
- Limite por transação individual: R$ 5.000,00.
- PIX Crédito: desabilitado por padrão.
- Limite PIX Crédito: R$ 0,00 (deve ser configurado posteriormente).

O dia de fechamento e o dia de vencimento podem ser escolhidos entre os dias 1 e 28.

## Status do Cartão

O cartão pode estar nos seguintes estados:

- **Pendente de ativação (pending_activation)**: cartão recém-emitido, precisa ser ativado.
- **Ativo (active)**: cartão funcionando normalmente.
- **Bloqueado (blocked)**: cartão temporariamente bloqueado, pode ser desbloqueado.
- **Cancelado (cancelled)**: cartão definitivamente cancelado, não pode ser reativado.
- **Expirado (expired)**: cartão com data de validade vencida.

### Regras de Mudança de Status

- **Ativar**: somente cartões com status "pendente de ativação" podem ser ativados.
- **Bloquear**: somente cartões "ativos" podem ser bloqueados. Um motivo para o bloqueio é registrado.
- **Desbloquear**: somente cartões "bloqueados" podem ser desbloqueados, voltando ao status "ativo".
- **Cancelar**: qualquer cartão pode ser cancelado, exceto os que já estão cancelados. O cancelamento é irreversível.

## Limite de Crédito

O cartão possui os seguintes controles de limite:

- **Limite total (credit_limit)**: valor máximo de crédito disponível no cartão.
- **Limite utilizado (used_limit)**: valor já consumido do limite.
- **Limite disponível (available_limit)**: diferença entre limite total e utilizado.

A fórmula é: **limite disponível = limite total - limite utilizado**

Quando o cliente paga a fatura, o limite utilizado é reduzido e o limite disponível é restaurado proporcionalmente.

## Funcionalidades do Cartão

Cada cartão possui controles individuais que podem ser ativados ou desativados:

- **Pagamento por aproximação (contactless)**: compras sem inserir o cartão.
- **Compras internacionais**: habilita transações em moeda estrangeira.
- **Compras online**: habilita transações em e-commerce.
- **PIX Crédito**: permite usar o limite do cartão para fazer transferências PIX.

## Fatura do Cartão

### Ciclo de Faturamento

Cada cartão possui um ciclo de faturamento mensal definido por:

- **Data de abertura (open_date)**: primeiro dia do mês de referência.
- **Data de fechamento (close_date)**: dia de fechamento configurado no cartão (billing_day).
- **Data de vencimento (due_date)**: dia de vencimento configurado no cartão (due_day).

### Composição da Fatura

A fatura é composta pela soma de todas as transações do cartão no mês de referência. Os tipos de transação que podem aparecer na fatura são:

- **Compras (purchase)**: compras realizadas com o cartão.
- **PIX Crédito (pix_credit)**: transferências PIX feitas via cartão de crédito, incluindo taxas.
- **Anuidade (annual_fee)**: taxa anual do cartão.
- **Juros (interest)**: juros por pagamento parcial ou atraso.
- **Seguro (insurance)**: seguro vinculado ao cartão.
- **Estorno (refund)**: devoluções de valores.
- **Contestação (chargeback)**: contestações de compras.
- **Pagamento (payment)**: pagamentos realizados na fatura.

### Categorias de Gastos no Cartão

As transações do cartão são classificadas nas seguintes categorias:

- Alimentação (food)
- Transporte (transport)
- Combustível (fuel)
- Material de escritório (office_supplies)
- Tecnologia (technology)
- Viagens (travel)
- Assinaturas (subscription)
- Marketing (marketing)
- Utilidades (utilities)
- Seguros (insurance)
- Manutenção (maintenance)
- Serviços profissionais (professional_services)
- Impostos (tax)
- PIX Crédito (pix_credit)
- Outros (other)

### Status da Fatura

- **Aberta (open)**: fatura em andamento, novas transações sendo registradas.
- **Fechada (closed)**: fatura fechada, aguardando pagamento.
- **Paga (paid)**: fatura integralmente paga.
- **Parcialmente paga (partially_paid)**: fatura com pagamento parcial realizado.
- **Vencida (overdue)**: fatura com vencimento ultrapassado sem pagamento total.

### Cálculo do Pagamento Mínimo

O pagamento mínimo da fatura é 15% do valor total da fatura.

Fórmula: **pagamento mínimo = valor total da fatura × 0,15**

Exemplo: para uma fatura de R$ 1.000,00, o pagamento mínimo é R$ 150,00.

## Pagamento da Fatura

O cliente pode pagar a fatura de três formas:

### Pagamento Total

Paga o valor integral da fatura. O status da fatura muda para "paga" e o limite utilizado é totalmente restaurado.

### Pagamento Mínimo

Paga apenas 15% do valor total. O status da fatura muda para "parcialmente paga". O restante será cobrado na próxima fatura com juros.

### Pagamento Personalizado

O cliente escolhe um valor específico para pagar. Se o valor for igual ou maior que o total da fatura, é considerado pagamento total. Se for menor, é considerado pagamento parcial.

### Regras do Pagamento

- O valor é debitado do saldo da conta corrente.
- O limite do cartão é restaurado proporcionalmente ao valor pago.
- A transação aparece no extrato como "Pagamento fatura cartão •••• XXXX" (onde XXXX são os últimos 4 dígitos).
- O sistema busca a fatura mais recente com status "aberta" ou "fechada".

## Consultar Limite de Crédito

O cliente pode consultar seu limite de crédito. O sistema retorna o maior limite entre todos os cartões vinculados ao cliente.

## Compras no Cartão de Débito

O cartão de débito permite compras que são debitadas imediatamente do saldo da conta. Se o saldo for insuficiente, a compra é registrada com status de saldo insuficiente mas não gera erro — a operação retorna normalmente informando o status.
