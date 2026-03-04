Context: pix

# Chaves PIX

## Tipos de chave

O cliente pode cadastrar chaves PIX dos seguintes tipos:

| Tipo | Descrição | Exemplo |
|------|-----------|---------|
| `cnpj` | CNPJ da empresa | 12.345.678/0001-90 |
| `email` | E-mail | contato@empresa.com.br |
| `phone` | Telefone | +5511999998888 |
| `random` | Chave aleatória | UUID gerado automaticamente |

**Observação:** Chave do tipo CPF NÃO pode ser registrada como chave PIX da conta PJ (apenas CNPJ).

## Cadastrar chave

- Para chaves do tipo `random`, o valor é gerado automaticamente pelo sistema.
- Para os demais tipos, o cliente informa o valor.
- Cada chave é vinculada à conta do cliente.

## Excluir chave

O cliente pode excluir suas próprias chaves PIX a qualquer momento.

## Detecção automática de tipo

Se o cliente informar uma chave sem especificar o tipo, o sistema detecta automaticamente:
- Contém `@` → e-mail
- 14 dígitos → CNPJ
- Começa com `+` → telefone
- 36 caracteres com hifens → chave aleatória (UUID)
