Context: auth

# Recuperação e Alteração de Senha

## Esqueci minha senha

O processo de recuperação tem duas etapas:

### Etapa 1 — Solicitar código de verificação
O cliente informa:
- **CNPJ** (documento da empresa)
- **Agência**
- **Conta**

O sistema gera um código de verificação de 6 dígitos, válido por **10 minutos**.

### Etapa 2 — Confirmar e redefinir
O cliente informa:
- **Código de verificação** recebido
- **Nova senha** (6 dígitos numéricos)

Após a redefinição, todos os tokens de acesso e refresh tokens são revogados. O cliente precisa fazer login novamente.

## Alterar senha (logado)

O cliente autenticado pode alterar a senha informando:
- **Senha atual**
- **Nova senha** (6 dígitos numéricos)

A senha atual é verificada antes de aceitar a alteração. Após a alteração, todos os tokens são revogados.

## Regras da senha

- Deve conter exatamente 6 dígitos.
- Apenas números (0-9).
- Não aceita letras ou caracteres especiais.
