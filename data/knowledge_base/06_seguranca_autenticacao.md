# Segurança e Autenticação

## Acesso à Conta PJ

O acesso à conta PJ é feito pelo representante legal da empresa usando seu CPF e uma senha numérica de 6 dígitos.

## Cadastro (Registro)

Para abrir uma conta PJ, o representante legal precisa fornecer:

- **CNPJ da empresa**: documento único da empresa. Cada CNPJ só pode ter uma conta.
- **CPF do representante**: documento do responsável legal.
- **Senha**: deve ter exatamente 6 dígitos numéricos (ex: 123456).

### Regras do Cadastro

- Não é possível cadastrar duas contas com o mesmo CNPJ. Se o CNPJ já estiver cadastrado, o sistema informa "CNPJ já cadastrado".
- A senha deve ter exatamente 6 dígitos.
- A senha deve conter apenas números — letras e caracteres especiais não são aceitos.
- CNPJ e CPF podem ser informados com ou sem máscara (pontos, barras e hífens são removidos automaticamente).

## Login

Para fazer login, o representante informa:

- **CPF**: documento do representante legal (com ou sem máscara).
- **Senha**: senha numérica de 6 dígitos.

### Proteção contra Tentativas Inválidas

O sistema possui proteção contra tentativas excessivas de login:

- Após **5 tentativas erradas de senha**, a conta é bloqueada por **30 minutos**.
- Durante o bloqueio, o sistema informa: "Conta temporariamente bloqueada. Tente novamente em X minutos".
- A cada tentativa errada (antes do bloqueio), o sistema informa quantas tentativas restam: "Credenciais inválidas. X tentativas restantes".
- Após um login bem-sucedido, o contador de tentativas é zerado.

### Conta Bloqueada

Se a conta estiver com status "bloqueada" (por decisão administrativa, não por tentativas), o sistema informa: "Conta bloqueada" e o login é negado.

## Tokens de Acesso

Após um login bem-sucedido, o sistema emite dois tokens:

### Token de Acesso (Access Token)

- Válido por **15 minutos**.
- Usado em todas as requisições que exigem autenticação.
- Deve ser enviado no cabeçalho HTTP como: `Authorization: Bearer {token}`.
- Contém o identificador do cliente e a data de expiração.

### Token de Atualização (Refresh Token)

- Válido por **7 dias**.
- Usado exclusivamente para obter um novo par de tokens quando o token de acesso expira.
- A cada renovação, o token antigo é invalidado e um novo par é emitido (rotação de tokens).

## Renovação de Token

Quando o token de acesso expira, o cliente pode usar o token de atualização para obter novos tokens sem precisar fazer login novamente:

- Se o token de atualização estiver válido, um novo par (acesso + atualização) é emitido.
- O token de atualização usado é invalidado (não pode ser reutilizado).
- Se o token de atualização estiver expirado, o cliente precisa fazer login novamente.

## Logout

O logout invalida todos os tokens de atualização do cliente. Após o logout, o cliente precisa fazer login novamente em todos os dispositivos.

## Recuperação de Senha

Se o cliente esqueceu a senha, pode solicitar a recuperação informando:

- **Documento**: CNPJ ou CPF.
- **Agência**: número da agência.
- **Conta**: número da conta.

### Processo de Recuperação

1. O sistema verifica se os dados conferem.
2. Um código de verificação de **6 dígitos** é gerado e enviado.
3. O código é válido por **10 minutos**.
4. O sistema retorna o e-mail mascarado para onde o código foi enviado (ex: jo\*\*@emp\*\*\*.com).

Por segurança, se os dados não forem encontrados, o sistema ainda retorna uma mensagem de sucesso (para não revelar se a conta existe).

### Confirmar Recuperação

Para confirmar a recuperação e definir uma nova senha:

- O cliente informa o código de verificação recebido.
- A nova senha deve seguir as mesmas regras: 6 dígitos numéricos.
- Após a troca, o código é marcado como usado.
- Todos os tokens de atualização são invalidados (o cliente precisa fazer login novamente em todos os dispositivos).

## Alteração de Senha

O cliente autenticado pode trocar sua senha informando:

- **Senha atual**: para confirmar a identidade.
- **Nova senha**: deve ter 6 dígitos numéricos.

Se a senha atual estiver incorreta, o sistema informa: "Senha atual incorreta".

Após a troca, todos os tokens de atualização são invalidados. O cliente precisa fazer login novamente em outros dispositivos.

## Proteção de Rotas

As seguintes operações exigem autenticação (token de acesso válido):

- Logout.
- Alteração de senha.
- Atualização de perfil.
- Atualização de dados do representante.

Se o token não for fornecido: "Token de autenticação não fornecido".
Se o formato for inválido: "Formato de token inválido".
Se o token estiver expirado ou inválido: "Token inválido ou expirado".

## Atualização de Dados do Perfil

O cliente autenticado pode atualizar:

- **Nome fantasia da empresa**.
- **E-mail de contato**.
- **Telefone do representante**.

Pelo menos um campo deve ser informado. Se nenhum campo for enviado, o sistema informa: "Nenhum campo para atualizar".

## Atualização de Dados do Representante

O representante legal pode atualizar:

- **Nome do representante**.
- **Telefone do representante**.

Pelo menos um campo deve ser informado.
