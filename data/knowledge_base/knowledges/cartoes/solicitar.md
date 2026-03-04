Context: cartoes

# Solicitar Cartão de Crédito

## Como solicitar

O cliente escolhe um produto do catálogo e informa o limite desejado. O sistema valida e emite o cartão imediatamente (aprovação automática).

## Dados necessários

- **Produto** (ex.: itau-pj-gold)
- **Limite solicitado** — deve estar dentro do mínimo e máximo do produto, e dentro do limite de crédito disponível na conta
- **Dia de vencimento da fatura** (opcional, padrão: dia 20)

## Regras de aprovação

- A conta precisa ter limite de crédito pré-aprovado (credit_limit > 0).
- O limite solicitado não pode ser maior que o limite de crédito disponível.
- O limite solicitado deve respeitar o mínimo e máximo do produto escolhido.
- O limite de crédito disponível da conta é reduzido pelo valor do limite aprovado.

## Valores padrão

Se o cliente não informar:
- Bandeira: Visa
- Tipo: corporativo
- Dia de fechamento da fatura: dia 10
- Dia de vencimento: dia 20
- Limite: R$ 10.000

## Prazo de entrega

- Cartão corporativo (físico): 7 dias úteis
- Cartão virtual: emissão instantânea (0 dias)

## Resposta

Após aprovação, o cliente recebe:
- Número do pedido
- Status: "approved"
- Últimos 4 dígitos do cartão
- Limite aprovado
- Prazo estimado de entrega
