# Transferências Agendadas

## O que são Transferências Agendadas

O cliente PJ pode programar transferências para datas futuras. Isso é útil para pagamentos recorrentes a fornecedores, salários, aluguéis e outras obrigações com data específica.

## Tipos de Transferência

As seguintes modalidades podem ser agendadas:

- **PIX**: transferência instantânea agendada.
- **TED**: transferência eletrônica disponível.
- **DOC**: documento de ordem de crédito.
- **Interna (internal)**: transferência entre contas do mesmo banco.

## Tipos de Agendamento

O cliente pode escolher a recorrência do agendamento:

- **Única (once)**: execução em uma data específica, sem repetição.
- **Diária (daily)**: execução todos os dias úteis.
- **Semanal (weekly)**: execução uma vez por semana.
- **Quinzenal (biweekly)**: execução a cada duas semanas.
- **Mensal (monthly)**: execução uma vez por mês.

## Regras para Agendamento

Para criar uma transferência agendada, o cliente deve informar:

- **Valor**: deve ser maior que zero.
- **Data agendada (scheduled_date)**: formato AAAA-MM-DD. Deve ser a data de hoje ou uma data futura. Datas passadas não são aceitas.
- **Chave de idempotência**: obrigatória para evitar agendamentos duplicados.
- **Conta de origem**: a conta deve existir e pertencer ao cliente.

## Status da Transferência Agendada

- **Agendada (scheduled)**: transferência programada, aguardando a data de execução.
- **Processando (processing)**: transferência sendo executada.
- **Concluída (completed)**: transferência realizada com sucesso.
- **Falhou (failed)**: transferência não concluída por erro (ex: saldo insuficiente no momento da execução).
- **Cancelada (cancelled)**: transferência cancelada pelo cliente.
- **Pausada (paused)**: transferência temporariamente suspensa.

## Cancelamento

O cliente pode cancelar transferências agendadas que ainda não foram executadas:

- Apenas transferências com status "agendada" ou "pausada" podem ser canceladas.
- Transferências já executadas (concluídas ou em processamento) não podem ser canceladas.

## Pausa

O cliente pode pausar transferências recorrentes:

- Apenas transferências com status "agendada" podem ser pausadas.
- A pausa muda o status para "pausada" e a transferência não será executada até ser retomada.

## Consulta de Agendamentos

O cliente pode listar todas as transferências agendadas, incluindo:

- Tipo de transferência (PIX, TED, DOC, interna).
- Valor.
- Data agendada.
- Tipo de recorrência.
- Status atual.
- Dados do destinatário.

## PIX Agendado

O PIX agendado combina as regras de transferência PIX com as regras de agendamento:

- O valor e o destinatário são validados no momento do agendamento.
- O saldo é verificado somente no momento da execução.
- Se o saldo for insuficiente na data de execução, a transferência falha.
- Os limites de PIX são verificados no momento da execução, não no agendamento.
