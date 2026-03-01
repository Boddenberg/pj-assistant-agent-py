Context: onboarding

# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

Conta bancária digital para empresas. Permite PIX, pagamento de boletos, cartão de crédito corporativo e análise financeira — tudo pelo app.

## Tipos de Conta

- **checking** — conta corrente para movimentações diárias.
- **savings** — conta poupança para reservas da empresa.
- **payment** — conta de pagamento para recebimentos e pagamentos.
- **escrow** — conta garantia para custódia de valores.

## Abertura de Conta PJ — Dados necessários para abrir conta
Para abrir conta PJ pelo app (context: onboarding), são necessários exatamente 9 campos: CNPJ (cnpj), Razão Social (razaoSocial), Nome Fantasia (nomeFantasia), E-mail (email), Nome do representante (representanteName), CPF do representante (representanteCpf), Telefone (representantePhone), Data de nascimento (representanteBirthDate) e Senha (password) numérica de 6 dígitos. Somente esses 9 campos — nenhum outro documento é exigido, não é necessário contrato social, documentos dos sócios nem comprovante de endereço. Após cadastro o sistema valida CNPJ (não pode já estar cadastrado) e senha (6 dígitos numéricos), conta é criada com agência e número gerados, cliente recebe customerId, agencia e conta, status inicia active. Abertura gratuita, 100% digital. Cada CNPJ só pode ter um cadastro. Login: CPF do representante + senha 6 dígitos; após 5 tentativas erradas conta bloqueada por 30 min.

## Status da Conta

- **active** — conta funcionando, todas as operações disponíveis.
- **blocked** — conta temporariamente bloqueada.
- **closed** — conta encerrada definitivamente.

## Dados da Conta

- **Agência (`branch`)** — número da agência.
- **Número da conta (`account_number`)** — identificador da conta.
- **Dígito (`digit`)** — dígito verificador.
- **Saldo (`balance`)** — valor total na conta (BRL).
- **Saldo disponível (`available_balance`)** — valor disponível para uso imediato.
- **Limite de cheque especial (`overdraft_limit`)** — crédito emergencial.

## Perfil do Cliente PJ

Dados armazenados no perfil:

- **CNPJ (`document`)** — identificador da empresa.
- **Razão social (`company_name`)** — nome oficial.
- **Nome fantasia (`name`)** — nome comercial.
- **E-mail (`email`)** — contato da empresa.
- **Segmento (`segment`)** — porte da empresa: `startup`, `small_business`, `middle_market`, `corporate`.
- **Faturamento mensal (`monthly_revenue`)** — receita mensal.
- **Score de crédito (`credit_score`)** — pontuação de crédito.
- **Tempo de relacionamento (`relationship_since`)** — data de início no banco.

## Representante

Pessoa física que opera a conta:

- **Nome (`representante_name`)** — nome completo.
- **CPF (`representante_cpf`)** — usado para login.
- **Telefone (`representante_phone`)** — contato.
- **Data de nascimento (`representante_birth_date`)**.

## Atualização de Cadastro

Dados que o cliente pode alterar (requer autenticação):

**Perfil da empresa:**
- Nome fantasia (`nomeFantasia`)
- E-mail (`email`)
- Telefone do representante (`representantePhone`)

**Dados do representante:**
- Nome (`representanteName`)
- Telefone (`representantePhone`)

## Segmentos

| Segmento | Descrição |
|---|---|
| startup | Empresas em fase inicial |
| small_business | Pequenos negócios |
| middle_market | Médio porte |
| corporate | Grandes empresas |

## Consultas Disponíveis

- **Lista de contas** — todas as contas vinculadas ao CNPJ.
- **Detalhes da conta** — informações de uma conta específica.
- **Saldo** — saldo atual e disponível.
- **Extrato** — transações com filtros por tipo, categoria e limite de resultados.

## Tipos de Transação no Extrato

- **pix_sent** — PIX enviado.
- **pix_received** — PIX recebido.
- **debit_purchase** — compra no débito.
- **credit_purchase** — compra no crédito.
- **transfer_in** — transferência recebida.
- **transfer_out** — transferência enviada.
- **bill_payment** — pagamento de boleto.
- **credit** — entrada de valores.
- **debit** — saída de valores.

Máximo de 500 transações por consulta. Paginação padrão: 20 resultados, máximo 100.
