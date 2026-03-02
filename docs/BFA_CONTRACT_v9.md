# Contrato BFA ↔ Agente Python — v9.0.0

> Documento de referência para implementação no BFA (Go).
> Última atualização: Março 2026.

---

## Visão Geral

O agente Python é a **camada conversacional** — interpreta linguagem natural, guia o cliente campo a campo e gera mensagens amigáveis (determinísticas, sem LLM).

O BFA (Go) é a **camada de negócio** — valida formatos, aplica regras de negócio, persiste dados e controla o fluxo.

**Mudanças em v9 (Breaking Changes):**
- ❌ Removido: `current_field` → substituído por `step` + `next_step`
- ✅ Adicionado: `step` e `validated` em cada turno do `history`
- ✅ Adicionado: `next_step` na response (BFA sabe o próximo campo)
- ✅ Adicionado: Limite de retries (MAX_RETRIES = 3)

---

## 1. Request — BFA → Agente (`POST /v1/chat`)

### Campos

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `query` | `string` | (obrigatório) | Mensagem do cliente |
| `customer_id` | `string` | `"anonymous"` | ID do cliente |
| `history` | `ChatMessage[]` | `[]` | Últimos turnos da conversa (enriquecidos) |
| `validation_error` | `string` | `""` | Erro do BFA ao validar último campo |
| `profile` | `object \| null` | `null` | Perfil do cliente (opcional) |
| `transactions` | `array` | `[]` | Transações (opcional) |

### ChatMessage (v9 — enriquecido)

| Campo | Tipo | Descrição |
|---|---|---|
| `query` | `string` | O que o cliente digitou |
| `answer` | `string` | O que o agente respondeu |
| `step` | `string \| null` | Step do onboarding (ex: `"cnpj"`, `"email"`). `null` se não é onboarding. |
| `validated` | `bool \| null` | Se o BFA validou com sucesso. `true`/`false`/`null`. |

### Payload: Onboarding em andamento

```json
{
  "customer_id": "cust-001",
  "query": "Empresa Teste LTDA",
  "history": [
    {
      "query": "Quero abrir minha conta PJ",
      "answer": "Que ótimo! Vou te guiar passo a passo. Me informe o CNPJ.",
      "step": null,
      "validated": null
    },
    {
      "query": "12.345.678/0001-99",
      "answer": "CNPJ recebido! ✅ Agora me diga a Razão Social.",
      "step": "cnpj",
      "validated": true
    }
  ],
  "validation_error": ""
}
```

### Payload: BFA rejeitou campo

```json
{
  "customer_id": "cust-001",
  "query": "12345",
  "history": [
    {
      "query": "Quero abrir conta",
      "answer": "Vamos lá! Me informe o CNPJ...",
      "step": null,
      "validated": null
    }
  ],
  "validation_error": "CNPJ inválido: deve conter 14 dígitos numéricos"
}
```

### Regras do BFA para montar o history

1. **Turno de welcome**: `step: null`, `validated: null`
2. **Campo validado com sucesso**: `step: "cnpj"`, `validated: true`
3. **Campo rejeitado pelo BFA**: `step: "cnpj"`, `validated: false`
4. **Conversa fora do onboarding**: `step: null`, `validated: null`

---

## 2. Response — Agente → BFA

### Campos (v9)

| Campo | Tipo | Descrição |
|---|---|---|
| `customer_id` | `string` | ID do cliente |
| `answer` | `string` | Texto para exibir ao cliente |
| `context` | `string \| null` | `"onboarding"` durante o cadastro, `null` fora |
| `intent` | `string \| null` | `"open_account"` durante onboarding |
| `confidence` | `float` | Sempre `1.0` no onboarding (determinístico) |
| `step` | `string \| null` | **Step que o cliente acabou de responder**. BFA usa para validar. `null` fora do onboarding. |
| `field_value` | `string \| null` | Valor cru que o cliente digitou. BFA valida. |
| `next_step` | `string \| null` | **Próximo step que será pedido**. BFA pode preparar a validação. |
| `suggested_actions` | `string[]` | Ações sugeridas |
| `metadata` | `object` | Tokens, custo, reasoning (0 tokens no onboarding) |
| `timestamp` | `string` | ISO 8601 |

### Payload: Onboarding (campo aceito)

```json
{
  "customer_id": "cust-001",
  "answer": "CNPJ recebido! ✅\n\nAgora me diga a Razão Social da empresa.",
  "context": "onboarding",
  "intent": "open_account",
  "confidence": 1.0,
  "step": "cnpj",
  "field_value": "12.345.678/0001-99",
  "next_step": "razaoSocial",
  "suggested_actions": ["Continuar cadastro", "Cancelar abertura"],
  "metadata": {
    "reasoning": [],
    "sources": [],
    "tokens_used": 0,
    "estimated_cost_usd": 0.0
  },
  "timestamp": "2026-03-01T12:00:00.000000"
}
```

### Payload: Welcome

```json
{
  "step": "welcome",
  "field_value": "Quero abrir conta",
  "next_step": "welcome",
  "answer": "Que ótimo que quer abrir sua conta PJ! 😊\nVou te guiar passo a passo..."
}
```

### Payload: Completed

```json
{
  "step": "passwordConfirmation",
  "field_value": "123456",
  "next_step": "completed",
  "answer": "Todos os dados foram recebidos! ✅🎉\n..."
}
```

### Payload: Fora do onboarding

```json
{
  "customer_id": "cust-001",
  "answer": "Seu saldo atual é R$ 15.430,00.",
  "context": null,
  "intent": "check_balance",
  "confidence": 0.95,
  "step": null,
  "field_value": null,
  "next_step": null,
  "suggested_actions": ["Ver extrato", "Fazer PIX"],
  "metadata": { "tokens_used": 450 },
  "timestamp": "2026-03-01T12:00:00.000000"
}
```

---

## 3. Sequência de Steps (ordem fixa)

| # | `step` | Label | Validação no BFA |
|---|---|---|---|
| 0 | `welcome` | — | Nenhuma. Agente deu boas-vindas. |
| 1 | `cnpj` | CNPJ | 14 dígitos. Formato: `XX.XXX.XXX/XXXX-XX`. Único no sistema. |
| 2 | `razaoSocial` | Razão Social | Mínimo 3 caracteres. |
| 3 | `nomeFantasia` | Nome Fantasia | Mínimo 2 caracteres. |
| 4 | `email` | E-mail | Deve conter `@` e domínio válido. |
| 5 | `representanteName` | Nome do representante | Nome completo, mínimo 5 caracteres. |
| 6 | `representanteCpf` | CPF do representante | 11 dígitos. Formato: `XXX.XXX.XXX-XX`. |
| 7 | `representantePhone` | Telefone | `(XX) XXXXX-XXXX`. Mínimo 10 dígitos. |
| 8 | `representanteBirthDate` | Data de nascimento | `DD/MM/AAAA`. Representante deve ter 18+ anos. |
| 9 | `password` | Senha | Exatamente 6 dígitos numéricos. |
| 10 | `passwordConfirmation` | Confirmação de senha | Idêntica ao `password`. |
| 11 | `completed` | — | Todos os campos coletados. |

---

## 4. Fluxo no BFA (pseudocódigo Go v9)

```go
func handleAgentResponse(resp AgentResponse, session *Session) {
    // Não é onboarding → tratar normalmente
    if resp.Step == nil {
        sendToClient(resp.Answer)
        return
    }

    step := *resp.Step
    value := resp.FieldValue

    switch step {
    case "welcome":
        // Agente deu boas-vindas
        session.OnboardingStarted = true
        // Adicionar turno ao history SEM step (welcome)
        session.History = append(session.History, ChatMessage{
            Query:     session.LastQuery,
            Answer:    resp.Answer,
            Step:      nil,
            Validated: nil,
        })
        sendToClient(resp.Answer)

    case "completed":
        // Todos os campos coletados → finalizar cadastro
        err := finalizeAccount(session.OnboardingData)
        if err != nil {
            sendToClient("Erro ao finalizar: " + err.Error())
        } else {
            sendToClient(resp.Answer)
        }

    default:
        // Campo de dados → validar
        err := validateField(step, *value)
        if err != nil {
            // REJEITADO → adicionar ao history com validated=false
            session.History = append(session.History, ChatMessage{
                Query:     session.LastQuery,
                Answer:    resp.Answer,
                Step:      &step,
                Validated: boolPtr(false),
            })

            // Reenviar ao agente com validation_error
            agentReq := AgentRequest{
                CustomerID:      session.CustomerID,
                Query:           session.LastQuery,
                History:         session.History,
                ValidationError: err.Error(),
            }
            newResp := callAgent(agentReq)
            handleAgentResponse(newResp, session)

        } else {
            // ACEITO → persistir + adicionar ao history com validated=true
            session.OnboardingData[step] = *value
            session.History = append(session.History, ChatMessage{
                Query:     session.LastQuery,
                Answer:    resp.Answer,
                Step:      &step,
                Validated: boolPtr(true),
            })
            sendToClient(resp.Answer)
        }
    }
}
```

### Como o BFA usa `next_step`

```go
// next_step diz ao BFA o que vem a seguir
// Útil para pré-carregar validações ou preparar UI

if resp.NextStep != nil {
    switch *resp.NextStep {
    case "completed":
        // Preparar finalização do cadastro
        prepareAccountCreation(session)
    case "representanteCpf":
        // Próximo campo é CPF — pré-carregar validador de CPF
        preloadCPFValidator()
    }
}
```

---

## 5. Limite de Retries

O agente suporta até **3 tentativas** por campo (MAX_RETRIES = 3).

Se o cliente errar 3+ vezes seguidas no mesmo campo, o agente:
- Encerra o onboarding com mensagem amigável
- Sugere recomeçar quando tiver os dados em mãos

**Como funciona:**
- O agente conta os turnos com `validated: false` para o mesmo step
- Se `validation_error` é enviado e já houve MAX_RETRIES falhas, o agente retorna mensagem de desistência
- Quando um campo é validado com sucesso, o contador reseta

**O BFA não precisa controlar retries** — o agente faz isso automaticamente.

---

## 6. Validação por Campo (referência)

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
            return fmt.Errorf("As senhas não coincidem")
        }
    }
    return nil
}
```

---

## 7. Diagrama de Sequência (v9)

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
  │                 │  step: "welcome"      │
  │                 │  next_step: "welcome" │
  │                 │  answer: "Ótimo! 😊"  │
  │                 │<──────────────────────│
  │                 │                       │
  │                 │  history.add({        │
  │                 │    step: null,        │
  │                 │    validated: null     │
  │                 │  })                   │
  │                 │                       │
  │ "Peça o CNPJ"   │                       │
  │<────────────────│                       │
  │                 │                       │
  │ "12345"         │                       │
  │────────────────>│                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "12345"       │
  │                 │  history: [welcome]   │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  ⚠️ inline validation │
  │                 │  step: "cnpj"         │
  │                 │  next_step: "cnpj"    │
  │                 │  answer: "⚠️ CNPJ     │
  │                 │   inválido..."        │
  │                 │<──────────────────────│
  │                 │                       │
  │                 │  history.add({        │
  │                 │    step: "cnpj",      │
  │                 │    validated: false    │
  │                 │  })                   │
  │                 │                       │
  │ "CNPJ inválido" │                       │
  │<────────────────│                       │
  │                 │                       │
  │ "12.345.678/    │                       │
  │  0001-99"       │                       │
  │────────────────>│                       │
  │                 │  POST /v1/chat        │
  │                 │  query: "12.345..."   │
  │                 │  history: [           │
  │                 │    {step:null},       │
  │                 │    {step:"cnpj",      │
  │                 │     validated:false}   │
  │                 │  ]                    │
  │                 │──────────────────────>│
  │                 │                       │
  │                 │  step: "cnpj"         │
  │                 │  next_step: "razao.." │
  │                 │  field_value:         │
  │                 │   "12.345.678/0001-99"│
  │                 │  answer: "CNPJ ok! ✅ │
  │                 │   Razão Social?"      │
  │                 │<──────────────────────│
  │                 │                       │
  │                 │  validateField("cnpj",│
  │                 │   "12.345...") → OK   │
  │                 │                       │
  │                 │  history.add({        │
  │                 │    step: "cnpj",      │
  │                 │    validated: true     │
  │                 │  })                   │
  │                 │                       │
  │ "CNPJ ok!       │                       │
  │  Razão Social?" │                       │
  │<────────────────│                       │
  │                 │                       │
  │  ... (repete para cada campo) ...       │
```

---

## 8. Checklist de Implementação no BFA (v9)

### Mudanças em relação à v8

- [ ] **Renomear** `current_field` → `step` na response
- [ ] **Adicionar** leitura do campo `next_step` na response
- [ ] **Enriquecer history**: cada turno agora precisa de `step` e `validated`
- [ ] **Remover** lógica antiga de contagem de turnos

### Implementação completa

- [ ] Adicionar campo `validation_error` (string) no request
- [ ] Ler `step`, `field_value` e `next_step` da response
- [ ] Implementar `validateField(step, value)` com as 10 regras
- [ ] Tratar `step == "welcome"` → iniciar sessão, history com `step: null`
- [ ] Tratar `step == "completed"` → finalizar cadastro
- [ ] Tratar `step == null` → fluxo normal (não onboarding)
- [ ] Se validação falhar:
  - Adicionar turno ao history com `step: "<campo>"`, `validated: false`
  - Reenviar ao agente com `validation_error`
- [ ] Se validação passar:
  - Persistir campo
  - Adicionar turno ao history com `step: "<campo>"`, `validated: true`
  - Enviar `answer` ao cliente
- [ ] Manter `history` atualizado (até 5 turnos)
- [ ] Guardar `password` na sessão para comparar com `passwordConfirmation`
- [ ] O agente controla retries automaticamente (MAX_RETRIES = 3)
