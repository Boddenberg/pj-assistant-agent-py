# Guia de Implementação — Fluxo de Abertura de Conta PJ

> Como o BFA (Go) deve se comunicar com o Agente Python para completar o onboarding.
>
> Endpoint: `POST /v1/chat`
> Última atualização: Março 2026

---

## Resumo

O onboarding é um fluxo de **10 campos coletados um a um**. O agente cuida da conversa, o BFA cuida da validação e persistência.

```
Cliente ──► BFA (Go) ──► Agente Python ──► BFA (Go) ──► Cliente
                │                              │
                │  monta request               │  valida campo
                │  com history enriquecido     │  persiste dado
                │                              │  atualiza history
```

---

## 1. Sequência dos 10 campos

| # | `step` (string) | O que pedir | Validação no BFA |
|---|---|---|---|
| 1 | `cnpj` | CNPJ da empresa | 14 dígitos, CNPJ único no sistema |
| 2 | `razaoSocial` | Razão Social | Mínimo 3 caracteres |
| 3 | `nomeFantasia` | Nome Fantasia | Mínimo 2 caracteres |
| 4 | `email` | E-mail corporativo | Conter `@` e .com |
| 5 | `representanteName` | Nome do representante | Mínimo 3 caracteres |
| 6 | `representanteCpf` | CPF do representante | 11 dígitos |
| 7 | `representantePhone` | Telefone | Mínimo 10 dígitos |
| 8 | `representanteBirthDate` | Data de nascimento | DD/MM/AAAA, 18+ anos |
| 9 | `password` | Senha | Exatamente 6 dígitos numéricos |
| 10 | `passwordConfirmation` | Confirmação de senha | Idêntica ao `password` |

---

## 2. Estrutura do Request (`POST /v1/chat`)

```json
{
  "customer_id": "string",
  "query": "string",
  "history": [
    {
      "query": "string",
      "answer": "string",
      "step": "string | null",
      "validated": "bool | null"
    }
  ],
  "validation_error": "string (vazio se não há erro)"
}
```

### Campos importantes

| Campo | Obrigatório | Descrição |
|---|---|---|
| `query` | ✅ | Texto que o cliente digitou agora |
| `customer_id` | Não (default: `"anonymous"`) | ID do cliente |
| `history` | Não (default: `[]`) | Turnos anteriores da conversa |
| `validation_error` | Não (default: `""`) | Mensagem de erro se o BFA rejeitou o último campo |

---

## 3. Estrutura do Response

```json
{
  "customer_id": "string",
  "answer": "string",
  "context": "string | null",
  "intent": "string | null",
  "confidence": 1.0,
  "step": "string | null",
  "field_value": "string | null",
  "next_step": "string | null",
  "has_validation_error": false,
  "retry_count": 0,
  "is_restart": false,
  "max_retries_exceeded": false,
  "suggested_actions": ["string"],
  "metadata": { ... },
  "timestamp": "string"
}
```

### Campos que o BFA precisa ler

| Campo | Quando | O que fazer |
|---|---|---|
| `step` | `!= null` | É onboarding. Usar esse valor para saber QUAL campo validar |
| `field_value` | `!= null` | Valor cru que o cliente digitou. Validar no BFA |
| `next_step` | `!= null` | Próximo campo que será pedido (informativo) |
| `has_validation_error` | `== true` | ⚠️ **CRÍTICO**: Agente JÁ rejeitou o campo (formato inválido). NÃO validar no BFA. Adicionar ao history com `validated: false`. Enviar `answer` direto ao cliente. |
| `retry_count` | `> 0` | Quantas tentativas consecutivas falharam neste campo |
| `answer` | Sempre | Texto para exibir ao cliente |
| `context` | `== "onboarding"` | Indica que estamos no fluxo de abertura |
| `step` | `== null` | NÃO é onboarding — tratar como conversa normal |

---

## 4. Fluxo Passo a Passo (o que o BFA faz)

### 4.1 — Cliente pede para abrir conta (primeira mensagem)

**BFA envia:**
```json
{
  "customer_id": "cust-001",
  "query": "Quero abrir minha conta PJ",
  "history": [],
  "validation_error": ""
}
```

**Agente responde:**
```json
{
  "answer": "Que ótimo que quer abrir sua conta PJ! 😊\nVou te guiar passo a passo...\nPara começar, me informe o CNPJ da empresa.",
  "context": "onboarding",
  "step": "welcome",
  "field_value": "Quero abrir minha conta PJ",
  "next_step": "welcome"
}
```

**BFA deve:**
1. Guardar o turno no history com `step: null`, `validated: null` (welcome não é campo de dados)
2. Enviar `answer` ao cliente

```go
session.History = append(session.History, ChatMessage{
    Query:     "Quero abrir minha conta PJ",
    Answer:    resp.Answer,
    Step:      nil,   // welcome não tem step
    Validated: nil,
})
```

---

### 4.2 — Cliente envia o CNPJ

**BFA envia:**
```json
{
  "customer_id": "cust-001",
  "query": "12.345.678/0001-99",
  "history": [
    {
      "query": "Quero abrir minha conta PJ",
      "answer": "Que ótimo que quer abrir sua conta PJ! 😊...",
      "step": null,
      "validated": null
    }
  ],
  "validation_error": ""
}
```

**Agente responde:**
```json
{
  "step": "cnpj",
  "field_value": "12.345.678/0001-99",
  "next_step": "razaoSocial",
  "answer": "CNPJ recebido! ✅\n\nAgora me diga a Razão Social da empresa."
}
```

**BFA deve:**
1. Ler `step` → `"cnpj"`
2. Ler `field_value` → `"12.345.678/0001-99"`
3. **Validar** o CNPJ (14 dígitos, único no sistema)
4. Se **válido** → persistir + adicionar ao history com `validated: true`
5. Se **inválido** → adicionar ao history com `validated: false` e reenviar com `validation_error`

#### Caso VÁLIDO:

```go
session.OnboardingData["cnpj"] = "12.345.678/0001-99"
session.History = append(session.History, ChatMessage{
    Query:     "12.345.678/0001-99",
    Answer:    resp.Answer,
    Step:      stringPtr("cnpj"),
    Validated: boolPtr(true),
})
// Enviar resp.Answer ao cliente
sendToClient(resp.Answer)
```

#### Caso INVÁLIDO (ex: CNPJ já existe):

```go
session.History = append(session.History, ChatMessage{
    Query:     "12.345.678/0001-99",
    Answer:    resp.Answer,
    Step:      stringPtr("cnpj"),
    Validated: boolPtr(false),
})

// Reenviar ao agente com validation_error
newReq := AgentRequest{
    CustomerID:      "cust-001",
    Query:           "12.345.678/0001-99",
    History:         session.History,
    ValidationError: "CNPJ já cadastrado no sistema",
}
newResp := callAgent(newReq)
// Tratar newResp da mesma forma (loop)
```

---

### 4.3 — Agente rejeita formato inline

O agente faz uma **pré-validação de formato** antes mesmo de devolver ao BFA. Se o cliente digitar "abc" como CNPJ, o agente já rejeita sem precisar do BFA.

Nesse caso, a response volta com:
```json
{
  "step": "cnpj",
  "field_value": "abc",
  "next_step": "cnpj",
  "answer": "⚠️ O dado informado para CNPJ não está válido.\nMotivo: CNPJ inválido..."
}
```

**Como identificar:** `step == next_step` (não avançou). O BFA ainda assim deve adicionar ao history com `validated: false`.

---

### 4.4 — Fluxo continua campo a campo

O padrão se repete para cada campo. A cada turno:

1. BFA monta request com `query` + `history` atualizado
2. Agente responde com `step` + `field_value` + `next_step`
3. BFA valida `field_value` usando `step` para saber qual validação aplicar
4. Se válido → `validated: true` no history, enviar answer ao cliente
5. Se inválido → `validated: false` no history, reenviar com `validation_error`

---

### 4.5 — Último campo (confirmação de senha)

**Agente responde:**
```json
{
  "step": "passwordConfirmation",
  "field_value": "123456",
  "next_step": "completed",
  "answer": "Todos os dados foram recebidos! ✅🎉\n\nConfira o resumo do cadastro:\n- CNPJ: 12.345.678/0001-99\n- Razão Social: Empresa LTDA\n..."
}
```

**BFA deve:**
1. Validar que `field_value` == senha anterior (`password`)
2. Se `next_step == "completed"` → **finalizar o cadastro**
3. Persistir conta, gerar agência/número, etc.

---

### 4.6 — Limite de retries

O agente controla retries internamente. Se o cliente errar o mesmo campo **3 vezes seguidas**, o agente responde:

```json
{
  "step": "cnpj",
  "next_step": "cnpj",
  "answer": "Não conseguimos validar o CNPJ após algumas tentativas. 😕\nQuando estiver com os dados em mãos, estaremos por aqui! É só digitar \"abrir conta\" para recomeçar."
}
```

O BFA pode encerrar a sessão de onboarding quando receber essa resposta. Identificar por: palavras como "tentativas" + `step == next_step` após 3+ turnos com `validated: false`.

---

## 5. Regras para montar o `history`

| Situação | `step` | `validated` |
|---|---|---|
| Welcome (primeira mensagem) | `null` | `null` |
| Campo validado com sucesso pelo BFA | `"cnpj"` (o step) | `true` |
| Campo rejeitado pelo BFA | `"cnpj"` (o step) | `false` |
| Campo rejeitado inline pelo agente | `"cnpj"` (o step) | `false` |
| Conversa fora do onboarding | `null` | `null` |

**Importante:** O agente usa `step` + `validated` do history para saber onde parou. Se o BFA não preencher esses campos corretamente, o agente perde a posição no fluxo.

---

## 6. Exemplo Completo — Fluxo Feliz (10 turnos)

```
TURNO 1: Cliente: "Quero abrir conta"
         Agente:  step=welcome → BFA salva history com step=null

TURNO 2: Cliente: "12.345.678/0001-99"
         Agente:  step=cnpj, next_step=razaoSocial
         BFA:     valida CNPJ ✅ → history com step=cnpj, validated=true

TURNO 3: Cliente: "Empresa Teste LTDA"
         Agente:  step=razaoSocial, next_step=nomeFantasia
         BFA:     valida ✅ → history com step=razaoSocial, validated=true

TURNO 4: Cliente: "Empresa Teste"
         Agente:  step=nomeFantasia, next_step=email
         BFA:     valida ✅ → history com step=nomeFantasia, validated=true

TURNO 5: Cliente: "contato@empresa.com"
         Agente:  step=email, next_step=representanteName
         BFA:     valida ✅ → history com step=email, validated=true

TURNO 6: Cliente: "João da Silva Santos"
         Agente:  step=representanteName, next_step=representanteCpf
         BFA:     valida ✅ → history com step=representanteName, validated=true

TURNO 7: Cliente: "123.456.789-00"
         Agente:  step=representanteCpf, next_step=representantePhone
         BFA:     valida ✅ → history com step=representanteCpf, validated=true

TURNO 8: Cliente: "(11) 99999-8888"
         Agente:  step=representantePhone, next_step=representanteBirthDate
         BFA:     valida ✅ → history com step=representantePhone, validated=true

TURNO 9: Cliente: "15/03/1990"
         Agente:  step=representanteBirthDate, next_step=password
         BFA:     valida ✅ → history com step=representanteBirthDate, validated=true

TURNO 10: Cliente: "123456"
          Agente:  step=password, next_step=passwordConfirmation
          BFA:     valida ✅ → history com step=password, validated=true

TURNO 11: Cliente: "123456"
          Agente:  step=passwordConfirmation, next_step=completed
          BFA:     valida (== password) ✅ → FINALIZAR CADASTRO 🎉
```

---

## 7. Exemplo com Erro — BFA Rejeita CNPJ

```
TURNO 1: Cliente: "Quero abrir conta"
         Agente:  step=welcome
         BFA:     history com step=null, validated=null

TURNO 2: Cliente: "12.345.678/0001-99"
         Agente:  step=cnpj, field_value="12.345.678/0001-99"
         BFA:     validateCNPJ → CNPJ já existe no sistema!
                  history com step=cnpj, validated=false
                  
         BFA reenvia ao agente:
         {
           "query": "12.345.678/0001-99",
           "history": [
             { step: null, validated: null },
             { step: "cnpj", validated: false }
           ],
           "validation_error": "CNPJ já cadastrado no sistema"
         }

         Agente responde:
         step=cnpj, next_step=cnpj (não avançou)
         answer="⚠️ O dado informado para CNPJ não está válido. Motivo: CNPJ já cadastrado..."
         
         BFA envia answer ao cliente

TURNO 3: Cliente: "98.765.432/0001-10" (outro CNPJ)
         Agente:  step=cnpj, field_value="98.765.432/0001-10", next_step=razaoSocial
         BFA:     validateCNPJ → OK ✅
                  history com step=cnpj, validated=true
                  Fluxo continua normalmente
```

---

## 8. Pseudocódigo Go — Lógica Completa

```go
func handleChatTurn(clientMessage string, session *Session) {
    // 1. Montar request
    req := AgentRequest{
        CustomerID:      session.CustomerID,
        Query:           clientMessage,
        History:         session.History,
        ValidationError: "", // vazio na primeira vez
    }

    // 2. Chamar agente
    resp := callAgent(req)  // POST /v1/chat

    // 3. Não é onboarding → enviar direto
    if resp.Step == nil {
        sendToClient(resp.Answer)
        return
    }

    step := *resp.Step

    // 4. Welcome → salvar no history sem step
    if step == "welcome" {
        session.History = append(session.History, ChatMessage{
            Query:     clientMessage,
            Answer:    resp.Answer,
            Step:      nil,
            Validated: nil,
        })
        sendToClient(resp.Answer)
        return
    }

    // 5. Agente já rejeitou formato inline (step == next_step e não avançou)
    //    Ou o campo é "completed"
    if resp.NextStep != nil && *resp.NextStep == step {
        // Agente rejeitou inline — salvar como validated=false
        session.History = append(session.History, ChatMessage{
            Query:     clientMessage,
            Answer:    resp.Answer,
            Step:      &step,
            Validated: boolPtr(false),
        })
        sendToClient(resp.Answer)
        return
    }

    // 6. Completed → finalizar cadastro
    if resp.NextStep != nil && *resp.NextStep == "completed" {
        // Validar último campo (passwordConfirmation)
        err := validateField(step, *resp.FieldValue, session)
        if err != nil {
            rejectAndRetry(clientMessage, step, err.Error(), resp, session)
            return
        }
        session.OnboardingData[step] = *resp.FieldValue
        finalizeAccount(session.OnboardingData)
        sendToClient(resp.Answer)
        return
    }

    // 7. Campo normal → validar no BFA
    err := validateField(step, *resp.FieldValue, session)
    if err != nil {
        rejectAndRetry(clientMessage, step, err.Error(), resp, session)
        return
    }

    // 8. Válido → persistir + avançar
    session.OnboardingData[step] = *resp.FieldValue
    session.History = append(session.History, ChatMessage{
        Query:     clientMessage,
        Answer:    resp.Answer,
        Step:      &step,
        Validated: boolPtr(true),
    })
    sendToClient(resp.Answer)
}

func rejectAndRetry(query, step, errMsg string, origResp AgentResponse, session *Session) {
    // Salvar turno como rejeitado
    session.History = append(session.History, ChatMessage{
        Query:     query,
        Answer:    origResp.Answer,
        Step:      &step,
        Validated: boolPtr(false),
    })

    // Reenviar ao agente com validation_error
    retryReq := AgentRequest{
        CustomerID:      session.CustomerID,
        Query:           query,
        History:         session.History,
        ValidationError: errMsg,
    }
    retryResp := callAgent(retryReq)

    // Resposta do retry vai direto ao cliente
    sendToClient(retryResp.Answer)
}

func validateField(field, value string, session *Session) error {
    switch field {
    case "cnpj":
        digits := onlyDigits(value)
        if len(digits) != 14 { return fmt.Errorf("CNPJ deve ter 14 dígitos") }
        if cnpjExists(digits) { return fmt.Errorf("CNPJ já cadastrado") }
    case "razaoSocial":
        if len(strings.TrimSpace(value)) < 3 { return fmt.Errorf("Mínimo 3 caracteres") }
    case "nomeFantasia":
        if len(strings.TrimSpace(value)) < 2 { return fmt.Errorf("Mínimo 2 caracteres") }
    case "email":
        if !isValidEmail(value) { return fmt.Errorf("E-mail inválido") }
    case "representanteName":
        if len(strings.TrimSpace(value)) < 5 { return fmt.Errorf("Mínimo 5 caracteres") }
    case "representanteCpf":
        digits := onlyDigits(value)
        if len(digits) != 11 { return fmt.Errorf("CPF deve ter 11 dígitos") }
    case "representantePhone":
        digits := onlyDigits(value)
        if len(digits) < 10 { return fmt.Errorf("Mínimo 10 dígitos") }
    case "representanteBirthDate":
        date, err := time.Parse("02/01/2006", value)
        if err != nil { return fmt.Errorf("Formato: DD/MM/AAAA") }
        if calculateAge(date) < 18 { return fmt.Errorf("Representante deve ter 18+ anos") }
    case "password":
        if !regexp.MustCompile(`^\d{6}$`).MatchString(value) {
            return fmt.Errorf("Senha: exatamente 6 dígitos")
        }
    case "passwordConfirmation":
        if value != session.OnboardingData["password"] {
            return fmt.Errorf("Senhas não coincidem")
        }
    }
    return nil
}
```

---

## 9. Checklist de Implementação

- [ ] Criar struct `ChatMessage` com campos `Step *string` e `Validated *bool`
- [ ] Criar struct `AgentRequest` com `ValidationError string`
- [ ] Ler `step`, `field_value` e `next_step` da response do agente
- [ ] Implementar `validateField()` com os 10 casos
- [ ] Tratar `step == "welcome"` → history com `step: null`
- [ ] Tratar `step == next_step` → agente rejeitou inline, salvar `validated: false`
- [ ] Tratar `next_step == "completed"` → finalizar cadastro
- [ ] Se validação falhar → history com `validated: false` + reenviar com `validation_error`
- [ ] Se validação passar → history com `validated: true` + persistir + enviar answer
- [ ] Guardar `password` na sessão para comparar com `passwordConfirmation`
- [ ] O agente controla retries (MAX_RETRIES = 3) — BFA não precisa contar
