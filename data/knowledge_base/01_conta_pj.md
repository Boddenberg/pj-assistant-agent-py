Context: onboarding

# Conta PJ — Pessoa Jurídica

## O que é a Conta PJ

Conta bancária digital para empresas. Permite PIX, pagamento de boletos, cartão de crédito corporativo e análise financeira — tudo pelo app.

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
