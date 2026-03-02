# Contrato BFA ↔ Agente Python — v8.0.0

> Documento de referência para implementação no BFA (Go).
> Última atualização: Março 2026.

---

## Visão Geral

O agente Python é a **camada conversacional** — interpreta linguagem natural, guia o cliente campo a campo e gera mensagens amigáveis.

O BFA (Go) é a **camada de negócio** — valida formatos, aplica regras de negócio, persiste dados e controla o fluxo.

O agente **nunca valida dados**. Ele recebe o que o cliente digitou, devolve o valor cru, e o BFA decide se aceita ou rejeita.

---

## 1. Request — BFA → Agente (`POST /v1/chat`)

### Campos novos (v8.0.0)

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `validation_error` | `string` | `""` | Mensagem de erro quando o BFA rejeitou o último campo. Se vazio, o agente avança normalmente. |

### Payload completo

```json
{
  "customer_id": "cust-001",
  "query": "12.345.678/0001-99",
  "history": [
    {
      "query": "Quero abrir minha conta PJ",
      "answer": "Que ótimo! Vou te guiar passo a passo. Me informe o CNPJ da empresa."
    }
  ],
  "validation_error": "",
  "profile": null,
  "transactions": []
}
```

### Quando preencher `validation_error`

```json
// BFA rejeitou o CNPJ → reenviar com erro
{
  "query": "12345",
  "history": [
    { "query": "Quero abrir conta", "answer": "Vamos lá! Me informe o CNPJ..." },
    { "query": "12345", "answer": "CNPJ recebido! ✅ Agora me diga a Razão Social..." }
  ],
  "validation_error": "CNPJ inválido: deve conter 14 dígitos numéricos no formato XX.XXX.XXX/XXXX-XX"
}
```

> **Importante:** Quando o BFA rejeita um campo, ele deve reenviar a **mesma query** do cliente com o `validation_error` preenchido. O agente vai pedir o mesmo campo novamente com a mensagem de erro humanizada.

---

## 2. Response — Agente → BFA

### Campos novos (v8.0.0)

| Campo | Tipo | Valores possíveis | Descrição |
|---|---|---|---|
| `current_field` | `string \| null` | Nome do campo, `"welcome"`, `"completed"`, ou `null` | Identifica qual campo do onboarding está sendo tratado. `null` = não é onboarding. |
| `field_value` | `string \| null` | Texto livre ou `null` | Valor cru que o cliente digitou. BFA deve validar. `null` = não é onboarding. |

### Payload completo (durante onboarding)

```json
{
  "customer_id": "cust-001",
  "answer": "CNPJ recebido! ✅\n\nAgora me diga a Razão Social da empresa (nome oficial no contrato social).",
  "context": "onboarding",
  "intent": "open_account",
  "confidence": 1.0,
  "current_field": "cnpj",
  "field_value": "12.345.678/0001-99",
  "suggested_actions": [],
  "metadata": {
    "reasoning": [...],
    "sources": [...],
    "tokens_used": 450,
    "estimated_cost_usd": 0.0003
  },
  "timestamp": "2026-03-01T12:00:00.000000"
}
```

### Payload (fora do onboarding)

```json
{
  "customer_id": "cust-001",
  "answer": "Seu saldo atual é R$ 15.430,00.",
  "context": null,
  "intent": "check_balance",
  "confidence": 0.95,
  "current_field": null,
  "field_value": null,
  "suggested_actions": ["Ver extrato", "Fazer PIX"],
  "metadata": { ... },
  "timestamp": "2026-03-01T12:00:00.000000"
}
```

---

## 3. Sequência de Campos (ordem fixa)

O agente pede **um campo por vez**, sempre nesta ordem:

| # | `current_field` | Label | Validação no BFA |
|---|---|---|---|
| 0 | `welcome` | — | Nenhuma. Agente deu boas-vindas, próximo será `cnpj`. |
| 1 | `cnpj` | CNPJ | 14 dígitos numéricos. Formato: `XX.XXX.XXX/XXXX-XX`. CNPJ único no sistema. |
| 2 | `razaoSocial` | Razão Social | Mínimo 3 caracteres. |
| 3 | `nomeFantasia` | Nome Fantasia | Mínimo 2 caracteres. |
| 4 | `email` | E-mail | Deve conter `@` e domínio válido. |
| 5 | `representanteName` | Nome do representante | Nome completo, mínimo 5 caracteres. |
| 6 | `representanteCpf` | CPF do representante | 11 dígitos numéricos. Formato: `XXX.XXX.XXX-XX`. |
| 7 | `representantePhone` | Telefone | Formato: `(XX) XXXXX-XXXX` ou `(XX) XXXX-XXXX`. Mínimo 10 dígitos. |
| 8 | `representanteBirthDate` | Data de nascimento | Formato: `DD/MM/AAAA`. Representante deve ter 18+ anos. |
| 9 | `password` | Senha | Exatamente 6 dígitos numéricos. Sem letras ou caracteres especiais. |
| 10 | `passwordConfirmation` | Confirmação de senha | Deve ser idêntica ao `password` (campo #9). |
| 11 | `completed` | — | Todos os campos coletados. Finalizar cadastro. |

---

## 4. Fluxo no BFA (pseudocódigo Go)

```go
func handleAgentResponse(resp AgentResponse, session *Session) {
    // Não é onboarding → tratar normalmente
    if resp.CurrentField == nil {
        sendToClient(resp.Answer)
        return
    }

    field := *resp.CurrentField
    value := *resp.FieldValue

    switch field {
    case "welcome":
        // Agente deu boas-vindas, nada a validar
        // Guardar que o onboarding iniciou
        session.OnboardingStarted = true
        sendToClient(resp.Answer)

    case "completed":
        // Todos os campos coletados → finalizar cadastro
        err := finalizeAccount(session.OnboardingData)
        if err != nil {
            sendToClient("Erro ao finalizar cadastro: " + err.Error())
        } else {
            sendToClient(resp.Answer)
        }

    default:
        // Campo de dados → validar
        err := validateField(field, value)
        if err != nil {
            // REJEITADO → reenviar ao agente com validation_error
            agentReq := AgentRequest{
                CustomerID:      session.CustomerID,
                Query:           session.LastQuery,       // mesma query
                History:         session.History,         // histórico atual
                ValidationError: err.Error(),             // erro descritivo
            }
            newResp := callAgent(agentReq)
            handleAgentResponse(newResp, session)
        } else {
            // ACEITO → persistir e mandar resposta ao cliente
            session.OnboardingData[field] = value
            session.History = append(session.History, ChatMessage{
                Query:  session.LastQuery,
                Answer: resp.Answer,
            })
            sendToClient(resp.Answer)
        }
    }
}
```

---

## 5. Validação por Campo (referência)

```go
func validateField(field, value string) error {
    switch field {
    case "cnpj":
        digits := onlyDigits(value)
        if len(digits) != 14 {
            return fmt.Errorf("CNPJ inválido: deve conter 14 dígitos numéricos")
        }
        if cnpjExists(digits) {
            return fmt.Errorf("CNPJ já cadastrado no sistema")
        }

    case "razaoSocial":
        if len(strings.TrimSpace(value)) < 3 {
            return fmt.Errorf("Razão Social deve ter no mínimo 3 caracteres")
        }

    case "nomeFantasia":
        if len(strings.TrimSpace(value)) < 2 {
            return fmt.Errorf("Nome Fantasia deve ter no mínimo 2 caracteres")
        }

    case "email":
        if !isValidEmail(value) {
            return fmt.Errorf("E-mail inválido: deve conter @ e um domínio válido")
        }

    case "representanteName":
        if len(strings.TrimSpace(value)) < 5 {
            return fmt.Errorf("Nome do representante deve ter no mínimo 5 caracteres")
        }

    case "representanteCpf":
        digits := onlyDigits(value)
        if len(digits) != 11 {
            return fmt.Errorf("CPF inválido: deve conter 11 dígitos numéricos")
        }

    case "representantePhone":
        digits := onlyDigits(value)
        if len(digits) < 10 {
            return fmt.Errorf("Telefone inválido: deve conter no mínimo 10 dígitos")
        }

    case "representanteBirthDate":
        date, err := time.Parse("02/01/2006", value)
        if err != nil {
            return fmt.Errorf("Data inválida: use o formato DD/MM/AAAA")
        }
        age := calculateAge(date)
        if age < 18 {
            return fmt.Errorf("Representante deve ter no mínimo 18 anos")
        }

    case "password":
        if !regexp.MustCompile(`^\d{6}$`).MatchString(value) {
            return fmt.Errorf("Senha deve ter exatamente 6 dígitos numéricos")
        }

    case "passwordConfirmation":
        if value != session.OnboardingData["password"] {
            return fmt.Errorf("As senhas não coincidem. Digite a mesma senha de 6 dígitos")
        }
    }
    return nil
}
```

---

## 6. Diagrama de Sequência

```
Cliente          BFA (Go)              Agente (Python)
  │                 │                       │
  │ "Quero abrir    │                       │
  │  conta PJ"      │                       │
  │────────────────>│                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "Quero abrir" │
  │                 │  history: []          │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  current_field:welcome │
  │                 │  field_value: "Quero.."│
  │                 │  answer: "Ótimo! 😊   │
  │                 │   Me informe o CNPJ"  │
  │                 │<──────────────────────│
  │                 │                       │
  │ "Boas-vindas +  │                       │
  │  peça o CNPJ"   │                       │
  │<────────────────│                       │
  │                 │                       │
  │ "12345"         │                       │
  │────────────────>│                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "12345"       │
  │                 │  history: [turno 0]   │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  current_field: cnpj  │
  │                 │  field_value: "12345" │
  │                 │<──────────────────────│
  │                 │                       │
  │                 │  validateField("cnpj",│
  │                 │    "12345") → ERRO    │
  │                 │                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "12345"       │
  │                 │  validation_error:    │
  │                 │   "CNPJ inválido..."  │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  current_field: cnpj  │
  │                 │  answer: "O CNPJ      │
  │                 │   informado não é     │
  │                 │   válido. Precisa ter │
  │                 │   14 dígitos..."      │
  │                 │<──────────────────────│
  │                 │                       │
  │ "CNPJ inválido, │                       │
  │  tente de novo" │                       │
  │<────────────────│                       │
  │                 │                       │
  │ "12.345.678/    │                       │
  │  0001-99"       │                       │
  │────────────────>│                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "12.345..."   │
  │                 │  history: [t0, t1]    │
  │                 │  validation_error: "" │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  current_field: cnpj  │
  │                 │  field_value:         │
  │                 │   "12.345.678/0001-99"│
  │                 │  answer: "CNPJ        │
  │                 │   recebido! ✅ Agora  │
  │                 │   a Razão Social..."  │
  │                 │<──────────────────────│
  │                 │                       │
  │                 │  validateField("cnpj",│
  │                 │   "12.345...") → OK   │
  │                 │  persistir CNPJ       │
  │                 │                       │
  │ "CNPJ ok!       │                       │
  │  Razão Social?" │                       │
  │<────────────────│                       │
  │                 │                       │
  │  ... (repete para cada campo) ...       │
  │                 │                       │
```

---

## 7. Checklist de Implementação no BFA

- [ ] Adicionar campo `validation_error` (string) no request para o agente
- [ ] Ler `current_field` e `field_value` da response do agente
- [ ] Implementar `validateField(field, value)` com as 10 regras
- [ ] Tratar `current_field == "welcome"` (iniciar sessão de onboarding)
- [ ] Tratar `current_field == "completed"` (finalizar cadastro)
- [ ] Tratar `current_field == null` (não é onboarding, fluxo normal)
- [ ] Se validação falhar: reenviar ao agente com `validation_error` preenchido
- [ ] Se validação passar: persistir campo e enviar `answer` ao cliente
- [ ] Manter `history` atualizado (até 5 turnos) em cada request
- [ ] Guardar `password` na sessão para comparar com `passwordConfirmation`
