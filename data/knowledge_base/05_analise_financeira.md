# Análise Financeira e Resumo

## Resumo Financeiro

O resumo financeiro oferece uma visão consolidada das finanças da empresa em um determinado período. É uma ferramenta essencial para o gestor acompanhar receitas, despesas, fluxo de caixa e tendências de gastos.

## Períodos de Análise

O cliente pode escolher os seguintes períodos para o resumo financeiro:

| Período | Descrição | Dias |
|---------|-----------|------|
| 7d | Últimos 7 dias | 7 |
| 30d ou 1month | Últimos 30 dias (padrão) | 30 |
| 90d ou 3months | Últimos 3 meses | 90 |
| 6months | Últimos 6 meses | 180 |
| 12m ou 1year | Últimos 12 meses | 365 |

Se nenhum período for informado, o padrão é os últimos 30 dias.

## Informações do Resumo

O resumo financeiro retorna as seguintes informações:

### Saldo Atual

O saldo exibido no resumo é o saldo real da conta corrente, atualizado em tempo real. Não é uma soma das transações — é o valor efetivo disponível na conta.

### Receitas (Income)

Soma de todos os valores positivos das transações no período. Inclui PIX recebidos, transferências recebidas, créditos e outras entradas.

### Despesas (Expenses)

Soma dos valores absolutos de todas as transações negativas no período. Inclui PIX enviados, compras no débito, pagamentos de boletos, transferências enviadas e outras saídas.

### Fluxo de Caixa Líquido

Calculado como: **receitas - despesas**

Um fluxo positivo indica que a empresa está recebendo mais do que gastando. Um fluxo negativo indica que os gastos superam as receitas.

## Análise por Categoria

O resumo inclui a distribuição de gastos por categoria, mostrando:

- Nome da categoria.
- Valor total gasto na categoria.
- Percentual em relação ao total de despesas.

A fórmula do percentual é: **(valor da categoria ÷ total de despesas) × 100**

Apenas categorias de despesas são mostradas. Categorias de receita não aparecem nesta análise.

As categorias possíveis incluem:

- PIX (transferências enviadas)
- Compras (débito e crédito)
- Contas (pagamentos de boletos)
- Cartão (pagamento de fatura)
- Recebimento (receitas)
- Outros

## Tendência Mensal

O resumo inclui uma tendência mensal que mostra a evolução das finanças mês a mês. Cada mês apresenta:

- Total de receitas do mês.
- Total de despesas do mês.
- Saldo líquido do mês.

Essa visão permite identificar padrões sazonais no fluxo de caixa da empresa.

## Orçamentos (Budgets)

O cliente pode definir orçamentos mensais por categoria de gasto para controlar suas finanças.

### Criação de Orçamento

Para criar um orçamento, o cliente deve informar:

- **Categoria**: categoria de gasto a ser monitorada (ex: alimentação, transporte, tecnologia).
- **Limite mensal (monthly_limit)**: valor máximo desejado para aquela categoria no mês. Deve ser maior que zero.
- **Percentual de alerta (alert_threshold_pct)**: percentual do limite que dispara um alerta. O padrão é 80%.

Exemplo: um orçamento de R$ 5.000 para "tecnologia" com alerta em 80% gerará um aviso quando os gastos atingirem R$ 4.000.

### Gerenciamento de Orçamentos

O cliente pode:

- Listar todos os orçamentos ativos.
- Criar novos orçamentos por categoria.
- Atualizar limites e alertas de orçamentos existentes.

Cada categoria só pode ter um orçamento ativo por vez.

## Resumo de Transações

Além do resumo financeiro, o cliente pode consultar um resumo específico de transações que inclui:

- Total de transações no período.
- Distribuição por tipo de transação.
- Saldo atualizado da conta.

Esse resumo também utiliza o saldo real da conta, não um saldo calculado.
