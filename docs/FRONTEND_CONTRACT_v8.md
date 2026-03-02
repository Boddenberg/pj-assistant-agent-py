# Frontend — Contrato do Chat v8.0.0

> Guia para integração do chat com onboarding no frontend React/Next.js.

---

## Endpoint

```
POST /v1/chat              → cliente anônimo (onboarding)
POST /v1/chat/{customerId} → cliente autenticado
```

---

## 1. Request (front → BFA)

**Não mudou.** Continua igual:

```json
{
  "query": "Quero abrir minha conta PJ",
  "history": [
    { "query": "Olá", "answer": "Olá! Como posso ajudar?" }
  ]
}
```

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `query` | `string` | ✅ | Mensagem do usuário |
| `history` | `HistoryEntry[]` | ❌ | Últimas mensagens da conversa (máx 5 são usadas) |

```typescript
interface HistoryEntry {
  query: string;
  answer: string;
}
```

---

## 2. Response (BFA → front)

### Campos novos (v8.0.0)

```typescript
interface ChatResponse {
  answer: string;                    // Mensagem para exibir ao usuário
  context: string | null;            // "onboarding" | "pix" | "general" | ...
  intent: string | null;             // "open_account" | "pix_transfer" | ...
  confidence: number;                // 0.0 a 1.0

  // ✨ NOVOS
  current_field: string | null;      // Qual campo do onboarding está sendo tratado
  field_value: string | null;        // Valor extraído da resposta do usuário
  account_data: AccountData | null;  // Dados da conta criada (só no completed)

  suggested_actions: string[];       // Sugestões de ações
}

interface AccountData {
  customerId: string;   // UUID do cliente criado
  agencia: string;      // Ex: "0001"
  conta: string;        // Ex: "123456-7"
}
```

---

## 3. Valores de `current_field`

| Valor | Significado | O que o front faz |
|-------|-------------|-------------------|
| `null` | **Não é onboarding.** Conversa normal. | Exibir `answer` normalmente |
| `"welcome"` | Onboarding iniciou. Boas-vindas. | Exibir `answer`. Opcionalmente: mostrar progresso 0% |
| `"cnpj"` | Pedindo/recebendo CNPJ | Exibir `answer` + progresso 10% |
| `"razaoSocial"` | Pedindo/recebendo Razão Social | Exibir `answer` + progresso 20% |
| `"nomeFantasia"` | Pedindo/recebendo Nome Fantasia | Exibir `answer` + progresso 30% |
| `"email"` | Pedindo/recebendo E-mail | Exibir `answer` + progresso 40% |
| `"representanteName"` | Pedindo/recebendo Nome do representante | Exibir `answer` + progresso 50% |
| `"representanteCpf"` | Pedindo/recebendo CPF | Exibir `answer` + progresso 60% |
| `"representantePhone"` | Pedindo/recebendo Telefone | Exibir `answer` + progresso 70% |
| `"representanteBirthDate"` | Pedindo/recebendo Data de nascimento | Exibir `answer` + progresso 80% |
| `"password"` | Pedindo/recebendo Senha | Exibir `answer` + progresso 90%. Input type=password |
| `"passwordConfirmation"` | Pedindo confirmação de senha | Exibir `answer` + progresso 95%. Input type=password |
| `"completed"` | **Conta criada!** 🎉 | Exibir `answer` + `account_data`. Redirecionar p/ login |
| `"error"` | Erro no cadastro (ex: CNPJ duplicado) | Exibir `answer` com mensagem de erro |

---

## 4. Lógica no Frontend (pseudocódigo)

```typescript
const response = await fetch('/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ query: userMessage, history }),
});

const data: ChatResponse = await response.json();

// Sempre exibir a mensagem
addMessage({ role: 'assistant', text: data.answer });

// Atualizar histórico
history.push({ query: userMessage, answer: data.answer });

// Lógica condicional por current_field
if (data.current_field === null) {
  // Conversa normal, nada especial
}

else if (data.current_field === 'completed' && data.account_data) {
  // 🎉 Conta criada — mostrar tela de sucesso
  showAccountCreatedScreen({
    agencia: data.account_data.agencia,
    conta: data.account_data.conta,
    customerId: data.account_data.customerId,
  });
}

else if (data.current_field === 'error') {
  // Erro no cadastro — exibir alerta
  showErrorAlert(data.answer);
}

else if (data.current_field === 'password' || data.current_field === 'passwordConfirmation') {
  // Campo de senha — mudar input para type=password
  setInputType('password');
}

else {
  // Campo de onboarding em andamento — atualizar barra de progresso
  setInputType('text');
  updateProgress(data.current_field);
}
```

---

## 5. Barra de Progresso (opcional)

```typescript
const ONBOARDING_FIELDS = [
  'cnpj', 'razaoSocial', 'nomeFantasia', 'email',
  'representanteName', 'representanteCpf', 'representantePhone',
  'representanteBirthDate', 'password', 'passwordConfirmation',
];

function getProgress(currentField: string | null): number {
  if (!currentField || currentField === 'welcome') return 0;
  if (currentField === 'completed') return 100;
  const idx = ONBOARDING_FIELDS.indexOf(currentField);
  return idx >= 0 ? Math.round(((idx + 1) / ONBOARDING_FIELDS.length) * 100) : 0;
}

// Uso:
// getProgress('cnpj')                  → 10
// getProgress('email')                 → 40
// getProgress('passwordConfirmation')  → 100
// getProgress('completed')             → 100
// getProgress(null)                    → 0
```

---

## 6. Tela de Sucesso (quando `completed`)

Quando `current_field === "completed"`, o `account_data` contém:

```json
{
  "customerId": "a1b2c3d4-...",
  "agencia": "0001",
  "conta": "987654-3"
}
```

**Esse é o mesmo contrato do `POST /v1/auth/register`.** Se o front já tem uma tela de sucesso do registro manual, pode reutilizar o mesmo componente.

Exemplo:

```tsx
{data.current_field === 'completed' && data.account_data && (
  <div className="success-card">
    <h2>🎉 Conta criada com sucesso!</h2>
    <div className="account-info">
      <p><strong>Agência:</strong> {data.account_data.agencia}</p>
      <p><strong>Conta:</strong> {data.account_data.conta}</p>
    </div>
    <button onClick={() => router.push('/login')}>
      Fazer Login
    </button>
  </div>
)}
```

---

## 7. Resumo das Mudanças

| O que | Antes | Agora |
|-------|-------|-------|
| `current_field` | ❌ Não existia | ✅ Identifica o campo do onboarding |
| `field_value` | ❌ Não existia | ✅ Valor extraído (uso interno, front pode ignorar) |
| `account_data` | ❌ Não existia | ✅ Dados da conta quando `completed` |
| Request | `{query, history}` | **Sem mudança** |
| `answer` | Texto livre | **Sem mudança** — sempre contém a mensagem para o usuário |
| Registro | Separado em `POST /v1/auth/register` | **Automático** pelo chat quando todos os campos são validados |

---

## 8. Checklist do Front

- [ ] Tipar `ChatResponse` com `current_field`, `field_value`, `account_data`
- [ ] Quando `current_field === "completed"` + `account_data` → exibir tela de sucesso
- [ ] Quando `current_field === "password"` ou `"passwordConfirmation"` → input type=password
- [ ] Quando `current_field === "error"` → exibir alerta de erro
- [ ] (Opcional) Barra de progresso baseada no `current_field`
- [ ] (Opcional) Ícones/labels por campo (🏢 CNPJ, 📧 Email, 🔒 Senha, etc.)

---

## Nota Importante — Responsabilidades

| Camada | Quem | O que faz |
|--------|------|-----------|
| **Frontend** | React/Next.js | Exibe `answer`, controla progresso, input type, tela de sucesso |
| **BFA** | Go | Valida campos, persiste dados, cria conta, adiciona `account_data` e `error` na response |
| **Agente** | Python | Gera mensagens conversacionais, retorna `current_field` + `field_value` |

Os campos `account_data` e `current_field: "error"` são **adicionados pelo BFA** na response antes de enviar ao front. O agente Python retorna `current_field: "completed"` e o BFA enriquece com os dados da conta criada.
