# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

A conta PJ é uma conta bancária digital voltada para empresas e empreendedores. Através dela, o cliente pode realizar todas as operações financeiras do seu negócio, incluindo PIX, pagamento de boletos, gestão de cartões de crédito corporativos e análise financeira.

## Tipos de Conta

O banco oferece os seguintes tipos de conta PJ:

- **Conta Corrente (checking)**: conta padrão para movimentações diárias do negócio.
- **Conta Poupança (savings)**: conta para reservas e aplicações da empresa.
- **Conta de Pagamento (payment)**: conta específica para recebimentos e pagamentos.
- **Conta Escrow (escrow)**: conta garantia para operações que exigem custódia de valores.

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
