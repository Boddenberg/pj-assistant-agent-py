# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

A conta PJ é uma conta bancária digital voltada para empresas e empreendedores. Através dela, o cliente pode realizar todas as operações financeiras do seu negócio, incluindo PIX, pagamento de boletos, gestão de cartões de crédito corporativos e análise financeira.

## Tipos de Conta

O banco oferece os seguintes tipos de conta PJ:

- **Conta Corrente (checking)**: conta padrão para movimentações diárias do negócio.
- **Conta Poupança (savings)**: conta para reservas e aplicações da empresa.
- **Conta de Pagamento (payment)**: conta específica para recebimentos e pagamentos.
- **Conta Escrow (escrow)**: conta garantia para operações que exigem custódia de valores.

## Abertura de Conta PJ — Fluxo de Onboarding

**Context para o BFA: `onboarding`**

Quando o cliente demonstra intenção de abrir uma conta PJ, o agente deve:
1. Informar os requisitos e o processo de forma conversacional.
2. Retornar o context `onboarding` na resposta para que o BFA acione o fluxo adequado via strategy.

### Quem pode abrir

- Empresas com CNPJ ativo na Receita Federal.
- Todos os tipos empresariais: MEI, ME, EPP, LTDA, S/A, EIRELI.
- O representante legal precisa ser maior de 18 anos e ter CPF regular.

### Documentos necessários

| Documento | Detalhe |
|---|---|
| CNPJ | Cadastro ativo e regular na Receita Federal |
| Contrato Social ou Requerimento de Empresário | Documento de constituição da empresa |
| Documento do representante legal | RG ou CNH válidos |
| CPF do representante legal | Regular na Receita Federal |
| Comprovante de endereço da empresa | Emitido nos últimos 90 dias |

Para MEI, basta o Certificado de Condição de Microempreendedor Individual (CCMEI).

### Etapas do onboarding

1. **Coleta de dados**: cliente informa CNPJ, dados do representante legal e da empresa.
2. **Validação documental**: verificação automática do CNPJ na Receita Federal e do CPF do representante.
3. **Análise de compliance**: checagem em listas restritivas (PEP, sanções, OFAC).
4. **Escolha do tipo de conta**: cliente seleciona o tipo de conta desejado (checking, savings, payment, escrow).
5. **Criação da conta**: conta criada com status `pending_activation`.
6. **Ativação**: após confirmação por e-mail ou token, a conta passa para status `active`.

### Prazo de abertura

- **Análise automática (maioria dos casos)**: conta criada em até 24 horas úteis.
- **Análise manual (casos com pendência documental)**: até 5 dias úteis.
- O cliente recebe notificação por e-mail e push no app sobre o status.

### Taxas de abertura

- A abertura de conta PJ é **gratuita** — não há cobrança de tarifa para abrir.
- Cada tipo de conta pode ter tarifas de manutenção mensal, que são informadas no ato da abertura.

### Perguntas frequentes sobre abertura

- **"Quanto custa abrir uma conta PJ?"** → Gratuito. Sem taxa de abertura.
- **"Quanto tempo demora?"** → Até 24h úteis na maioria dos casos.
- **"Preciso ir à agência?"** → Não. O processo é 100% digital pelo app.
- **"MEI pode abrir?"** → Sim. Basta ter o CCMEI.
- **"Posso ter mais de uma conta PJ?"** → Sim. Cada CNPJ pode ter múltiplas contas de tipos diferentes.
- **"O que acontece depois de abrir?"** → A conta fica em `pending_activation`. Após confirmação, vira `active`.

## Status da Conta

A conta pode estar em um dos seguintes estados:

- **Ativa (active)**: conta funcionando normalmente, todas as operações disponíveis.
- **Bloqueada (blocked)**: conta temporariamente impedida de realizar operações.
- **Encerrada (closed)**: conta definitivamente fechada.
- **Pendente de ativação (pending_activation)**: conta recém-criada aguardando ativação.

## Dados da Conta

Cada conta possui as seguintes informações:

- **Agência (branch)**: número da agência bancária.
- **Número da conta (account_number)**: identificador numérico da conta.
- **Dígito (digit)**: dígito verificador da conta.
- **Código do banco (bank_code)**: código identificador do banco.
- **Saldo (balance)**: valor total disponível na conta em reais (BRL).
- **Saldo disponível (available_balance)**: valor que pode ser utilizado imediatamente.
- **Limite de cheque especial (overdraft_limit)**: crédito emergencial vinculado à conta.

## Perfil do Cliente PJ

O cadastro do cliente PJ contém:

- **CNPJ (document)**: cadastro nacional da pessoa jurídica, identificador único da empresa.
- **Razão social (company_name)**: nome oficial registrado da empresa.
- **Nome fantasia (name)**: nome comercial da empresa.
- **E-mail**: e-mail de contato da empresa.
- **Segmento**: classificação do porte da empresa (startup, small_business, middle_market, corporate).
- **Faturamento mensal (monthly_revenue)**: receita mensal declarada.
- **Score de crédito (credit_score)**: pontuação de crédito da empresa.
- **Tempo de relacionamento (relationship_since)**: data de início do relacionamento com o banco.

## Representante Legal

Toda conta PJ possui um representante legal com os seguintes dados:

- **Nome do representante (representante_name)**: nome completo da pessoa física responsável.
- **CPF do representante (representante_cpf)**: documento do representante, usado para login.
- **Telefone (representante_phone)**: telefone de contato.
- **Data de nascimento (representante_birth_date)**: data de nascimento do representante.

## Atualização de Cadastro

O cliente pode atualizar os seguintes dados do perfil:

- Nome fantasia da empresa.
- E-mail de contato.
- Telefone do representante.

Para atualizar dados do representante legal:

- Nome do representante.
- Telefone do representante.

Essas atualizações requerem autenticação prévia com token válido.

## Segmentos de Cliente

O banco atende diferentes portes de empresa, cada um com limites e condições específicas:

| Segmento | Descrição |
|----------|-----------|
| Startup | Empresas em fase inicial com limites menores |
| Small Business | Pequenos negócios e comércio local |
| Middle Market | Empresas de médio porte |
| Corporate | Grandes empresas e corporações |

## Consultas Disponíveis

O cliente pode consultar:

- **Lista de contas**: visualizar todas as contas vinculadas ao seu CNPJ.
- **Detalhes da conta**: informações completas de uma conta específica.
- **Saldo**: consultar saldo atual e saldo disponível da conta.
- **Extrato**: listar transações realizadas com filtros por tipo, categoria e limite de resultados.

## Tipos de Transação no Extrato

O extrato da conta mostra os seguintes tipos de movimentação:

- **PIX enviado (pix_sent)**: transferência PIX realizada pelo cliente.
- **PIX recebido (pix_received)**: transferência PIX recebida.
- **Compra no débito (debit_purchase)**: compra realizada com cartão de débito.
- **Compra no crédito (credit_purchase)**: compra realizada com cartão de crédito.
- **Transferência recebida (transfer_in)**: transferência bancária recebida.
- **Transferência enviada (transfer_out)**: transferência bancária enviada.
- **Pagamento de boleto (bill_payment)**: pagamento de contas e boletos.
- **Crédito (credit)**: entrada de valores diversos.
- **Débito (debit)**: saída de valores diversos.

O extrato pode retornar até 500 transações por consulta. A paginação padrão é de 20 resultados por página, com máximo de 100.
