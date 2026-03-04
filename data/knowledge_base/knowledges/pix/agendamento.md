Context: pix

# PIX Agendado (Scheduled Transfers)

## O que é

O cliente pode agendar transferências PIX para datas futuras, com opção de recorrência.

## Dados necessários

- **Valor** (maior que zero)
- **Data agendada** (formato YYYY-MM-DD, deve ser hoje ou no futuro)
- **Nome do destinatário**
- **Dados bancários do destinatário** (banco, agência, conta)
- **Tipo de transferência**: pix, ted, doc ou internal
- **Tipo de recorrência**: once (única), daily (diária), weekly (semanal), biweekly (quinzenal), monthly (mensal)
- **Data fim da recorrência** (opcional)
- **Número máximo de recorrências** (opcional)

## Status

| Status | Significado |
|--------|-------------|
| `scheduled` | Agendado e ativo |
| `cancelled` | Cancelado pelo cliente |

## Regras

- O cancelamento só é possível quando o status é `scheduled`.
- Após cada execução, o sistema atualiza a data da próxima execução conforme o tipo de recorrência.
