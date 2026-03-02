Context: onboarding

# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

Conta bancária digital para empresas. Permite PIX, pagamento de boletos, cartão de crédito corporativo e análise financeira — tudo pelo app.

## Tipos de Conta

- **checking** — conta corrente para movimentações diárias.
- **savings** — conta poupança para reservas da empresa.
- **payment** — conta de pagamento para recebimentos e pagamentos.
- **escrow** — conta garantia para custódia de valores.

## Abertura de Conta PJ — Fluxo de Onboarding em 4 Etapas

A abertura é 100% digital, gratuita, feita pelo chat. Cada CNPJ só pode ter um cadastro. São 9 campos divididos em 4 etapas obrigatórias:

### ETAPA 1 — Dados da Empresa
Campos obrigatórios nesta etapa:
1. **CNPJ** (`cnpj`) — formato: XX.XXX.XXX/XXXX-XX (14 dígitos). Validar formato.
2. **Razão Social** (`razaoSocial`) — nome oficial da empresa. Mínimo 3 caracteres.
3. **Nome Fantasia** (`nomeFantasia`) — nome comercial. Mínimo 2 caracteres.
4. **E-mail** (`email`) — e-mail corporativo. Deve conter @ e domínio válido.

Regras da Etapa 1:
- Todos os 4 campos são obrigatórios para avançar.
- O cliente pode enviar todos de uma vez ou um por um.
- Se algum dado estiver inválido, pedir correção SEM avançar.
- Quando os 4 campos forem válidos, confirmar os dados e pedir os da Etapa 2.

### ETAPA 2 — Dados do Representante Legal
Campos obrigatórios nesta etapa:
1. **Nome do representante** (`representanteName`) — nome completo. Mínimo 5 caracteres.
2. **CPF do representante** (`representanteCpf`) — formato: XXX.XXX.XXX-XX (11 dígitos). Validar formato.
3. **Telefone** (`representantePhone`) — formato: (XX) XXXXX-XXXX ou (XX) XXXX-XXXX. Mínimo 10 dígitos.
4. **Data de nascimento** (`representanteBirthDate`) — formato: DD/MM/AAAA. O representante deve ter 18+ anos.

Regras da Etapa 2:
- Só pedir esses dados APÓS a Etapa 1 estar completa.
- O cliente pode enviar todos de uma vez ou um por um.
- Se algum dado estiver inválido, pedir correção SEM avançar.
- Quando os 4 campos forem válidos, confirmar os dados e pedir a Etapa 3.

### ETAPA 3 — Criação de Senha
Campos obrigatórios nesta etapa:
1. **Senha** (`password`) — numérica, exatamente 6 dígitos. Não aceitar letras nem caracteres especiais.

Regras da Etapa 3:
- Só pedir a senha APÓS a Etapa 2 estar completa.
- A senha deve ter EXATAMENTE 6 dígitos numéricos.
- Se inválida, explicar os requisitos e pedir novamente.
- Quando válida, pedir confirmação na Etapa 4.

### ETAPA 4 — Confirmação de Senha
Campos obrigatórios nesta etapa:
1. **Confirmação de senha** (`passwordConfirmation`) — deve ser IDÊNTICA à senha da Etapa 3.

Regras da Etapa 4:
- Só pedir APÓS a Etapa 3 estar completa.
- Comparar com a senha da Etapa 3 (disponível no histórico da conversa).
- Se não coincidir, informar e pedir para digitar novamente.
- Quando coincidir, confirmar que todos os dados foram coletados e o cadastro será processado.

### Regras Gerais do Fluxo de Onboarding
- NUNCA pular etapas. A ordem é sempre: Etapa 1 → Etapa 2 → Etapa 3 → Etapa 4.
- NUNCA pedir dados de uma etapa posterior antes de completar a atual.
- Se o cliente enviar dados fora de ordem, redirecionar para a etapa atual.
- Usar o histórico da conversa para saber quais dados já foram coletados.
- Ao confirmar dados de cada etapa, listar o que foi recebido de forma organizada.
- Ser conversacional e encorajador ("Ótimo!", "Perfeito!", "Quase lá!").

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
