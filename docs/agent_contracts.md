# Agent Contracts — Engineering Design Assistant

This is the single source of truth for every agent's input/output shape.
**Rule: nobody changes their agent's output shape without updating this file and pinging the team.**

All agents are plain Python functions: `run(...) -> dict`. The dict shape below is also what goes in `state.py` as the shared LangGraph state.

---

## 0. Shared State Object (lives in `backend/state.py`)

This is what flows through the entire graph. Every agent reads from it and writes back into it.

```python
class DesignState(TypedDict):
    problem_statement: str              # raw user input, set once at start
    requirements: dict                  # output of Requirements Agent
    techstack: dict                     # output of Tech Stack Agent
    architecture: dict                  # output of Architecture Agent
    critic_verdict: dict                # output of Critic Agent
    revision_count: int                 # starts at 0, incremented on each REVISE loop
    final_output: dict                  # assembled at the end, what gets returned to frontend
```

---

## 1. Requirements Agent (Person B)

**Input:** `problem_statement: str`

**Output:**
```json
{
  "functional_requirements": ["string", "string"],
  "non_functional_requirements": ["string", "string"],
  "scale": "string, e.g. '10M daily active users'",
  "constraints": ["string", "string"],
  "assumptions": ["string", "string"]
}
```

**Example:**
Input: `"design a notification system for 10M users"`
```json
{
  "functional_requirements": [
    "send push, email, and SMS notifications",
    "support scheduled and real-time notifications",
    "allow users to set notification preferences"
  ],
  "non_functional_requirements": [
    "low latency delivery (under 5s for real-time)",
    "high availability (99.9%)"
  ],
  "scale": "10M users, assume ~500 notifications/sec peak",
  "constraints": ["must support multiple providers (FCM, APNS, SMTP)"],
  "assumptions": ["users have at most 3 registered devices"]
}
```

---

## 2. Tech Stack Agent (Person B)

**Input:** `requirements: dict` (the object above)

**Output:**
```json
{
  "stack": [
    {
      "component": "string, e.g. 'Message Queue'",
      "choice": "string, e.g. 'Kafka'",
      "justification": "string, 1-2 sentences"
    }
  ]
}
```

**Example:**
```json
{
  "stack": [
    {
      "component": "Message Queue",
      "choice": "Kafka",
      "justification": "Handles high-throughput async delivery and decouples notification producers from senders."
    },
    {
      "component": "Database",
      "choice": "PostgreSQL + Redis",
      "justification": "Postgres for durable preference storage, Redis for fast rate-limiting checks."
    }
  ]
}
```

---

## 3. Architecture Agent (Person C)

**Input:** `requirements: dict`, `techstack: dict`, `revision_notes: list[str] | None` (passed in only on revision loops)

**Output:**
```json
{
  "design_description": "string, 3-6 sentences explaining the overall design",
  "components": [
    {
      "name": "string",
      "responsibility": "string"
    }
  ],
  "mermaid_diagram": "string, raw Mermaid syntax, e.g. 'graph TD\\nA[Client]-->B[API Gateway]\\nB-->C[Notification Service]'",
  "tradeoffs": ["string", "string"]
}
```

**Example:**
```json
{
  "design_description": "Clients send requests to an API Gateway, which publishes events to Kafka. A Notification Service consumes events and dispatches via provider-specific adapters.",
  "components": [
    {"name": "API Gateway", "responsibility": "auth + request routing"},
    {"name": "Notification Service", "responsibility": "consumes events, applies user preferences, dispatches to providers"}
  ],
  "mermaid_diagram": "graph TD\nA[Client] --> B[API Gateway]\nB --> C[Kafka Queue]\nC --> D[Notification Service]\nD --> E[FCM/APNS/SMTP]",
  "tradeoffs": ["Kafka adds operational complexity but is necessary at this scale"]
}
```

**Important for Person A:** when `revision_notes` is non-empty, this same function is called again — output shape is identical, just (hopefully) improved.

---

## 4. Critic Agent (Person C)

**Input:** `architecture: dict`

**Output:**
```json
{
  "verdict": "APPROVE",
  "issues": ["string", "string"]
}
```
`verdict` is always exactly `"APPROVE"` or `"REVISE"` — Person A's conditional edge checks this string exactly, so don't deviate (no "approved", no lowercase, etc — agree on exact casing now).

**Example (rejection case):**
```json
{
  "verdict": "REVISE",
  "issues": [
    "No mention of how delivery failures/retries are handled",
    "Single Notification Service instance is a single point of failure — no redundancy discussed"
  ]
}
```

---

## 5. RAG Retrieval Tool (Person D)

**Input:** `query: str`

**Output:**
```json
{
  "chunks": ["string", "string", "string"]
}
```
Plain list of relevant text chunks — the calling agent (Architecture Agent, if you wire it in) inserts these into its own prompt as extra context.

---

## 6. Web Search Tool (Person D)

**Input:** `query: str`

**Output:**
```json
{
  "results": [
    {"title": "string", "snippet": "string", "url": "string"}
  ]
}
```

---

## 7. Final Output (assembled by Person A in `graph.py`, sent to frontend)

```json
{
  "requirements": { ... },
  "techstack": { ... },
  "architecture": { ... },
  "critic_history": [ { "verdict": "...", "issues": [...] } ],
  "revision_count": 1
}
```

This is the exact JSON Person D's frontend will receive from `POST /design` — build the frontend against this shape using mock data before the backend is ready.

---

## Non-negotiable rules

1. Field names are exact — `functional_requirements`, not `functionalRequirements` or `func_reqs`. Python convention (snake_case) throughout, including in the JSON the frontend receives.
2. Every agent function must `pydantic`-validate its own output before returning, so a malformed LLM response fails loudly in that person's own testing — not three days later in integration.
3. If you need to change a shape, edit this file in a PR and post in the group chat — don't just change it locally.
