Context: onboarding

# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

Conta bancária digital para empresas. Permite PIX, pagamento de boletos, cartão de crédito corporativo e análise financeira — tudo pelo app.

## Tipos de Conta

- **checking** — conta corrente para movimentações diárias.
- **savings** — conta poupança para reservas da empresa.
- **payment** — conta de pagamento para recebimentos e pagamentos.
- **escrow** — conta garantia para custódia de valores.

## Abertura de Conta PJ — Fluxo de Onboarding

A abertura é 100% digital, gratuita, feita pelo chat. Cada CNPJ só pode ter um cadastro.

O fluxo é guiado campo a campo. O assistente pede UM campo por vez, na seguinte ordem:

1. **CNPJ** (`cnpj`)
2. **Razão Social** (`razao_social`)
3. **Nome Fantasia** (`nome_fantasia`)
4. **E-mail** (`email`)
5. **Nome do representante** (`representante_name`)
6. **CPF do representante** (`representante_cpf`)
7. **Telefone** (`representante_phone`)
8. **Data de nascimento** (`representante_birth_date`)
9. **Senha** (`password`) — 6 dígitos numéricos
10. **Confirmação de senha** (`password_confirmation`)

A validação de cada campo é feita pelo sistema externo (BFA).
Se o BFA rejeitar um campo, o assistente informa o erro e pede o mesmo campo novamente.
O assistente NÃO avança para o próximo campo até o BFA aceitar o campo atual.

## Status da Conta

- **active** — conta funcionando, todas as operações disponíveis.

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
