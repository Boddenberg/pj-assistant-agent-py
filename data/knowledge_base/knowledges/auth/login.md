Context: auth

# Login e Autenticação

## Como fazer login

O cliente faz login informando:
- **CPF do representante** (normalizado para apenas dígitos)
- **Senha** (6 dígitos numéricos)

O sistema localiza o cliente pelo CPF do representante legal cadastrado no onboarding.

## Bloqueio por tentativas

- O cliente tem até **5 tentativas** de login com senha incorreta.
- Após 5 tentativas falhas consecutivas, a conta é **bloqueada por 30 minutos**.
- Durante o bloqueio, o sistema informa quanto tempo falta para desbloquear.
- Após o desbloqueio automático, o contador de tentativas é zerado.

## Conta bloqueada

Se o status da conta for "blocked", o login é negado independente da senha.

## Resposta do login

Após login bem-sucedido, o cliente recebe:
- Token de acesso (JWT)
- Token de atualização (refresh token)
- Tempo de expiração do token
- ID do cliente
- Nome do representante
- Nome da empresa
