# Blueprint-AI Graph Contract
### Agent Specification for the LangGraph Orchestration Pipeline

This document defines the behavioral contract for every node in the Blueprint-AI LangGraph pipeline. It is written as an **engineering reference** — the source of truth for what each agent is responsible for, what it can touch, and what it must never touch. Any change to an agent's behavior should be checked against this contract before being merged.

---

## 1. Design Philosophy

The pipeline is built around a simple idea: **each agent does exactly one job, and does it in isolation.** Agents don't share responsibilities, don't reach into each other's outputs, and don't make decisions outside their lane. This keeps the graph predictable, testable, and easy to extend — if you need to swap out the Tech Stack Agent for a fine-tuned model tomorrow, nothing else in the pipeline should need to change.

**Core principles at a glance:**
- **Single Responsibility** — one agent, one well-defined task.
- **Loose Coupling** — agents talk only through shared graph state, never directly.
- **Immutable Outputs** — once an agent writes its section of state, no other agent may edit it.
- **Deterministic Routing** — the graph only branches based on `critic_verdict`, nothing else.
- **Explicit Contracts** — every node has a documented input/output boundary, so the pipeline stays easy to test and replace piece by piece.

---

## 2. Graph Flow

The pipeline runs linearly through four stages, with one conditional loop:

```
START → Requirements → Tech Stack → Architecture → Critic
                                          ▲            │
                                          │            ├── APPROVE → Diagram → END
                                          └── REVISE ───┘
```

**Key notes:**
- The path from `Requirements` → `Tech Stack` → `Architecture` → `Critic` always runs in order — no stage can be skipped.
- `Critic` is the only decision point in the graph. Its verdict determines whether the pipeline moves forward (to `Diagram`) or loops back (to `Architecture`).
- The revision loop is bounded — it repeats until either `APPROVE` is returned or a maximum revision count is reached (preventing infinite loops).

---

## 3. Shared Graph State

All agents read from and write to a single shared state object. No agent holds private state outside of this.

```python
GraphState
├── problem_statement
├── requirements
├── techstack
├── architecture
├── critic_verdict
├── diagram
├── revision_count
└── critic_history
```

**Key notes:**
- Every agent reads *only* the fields it needs — not the entire state blindly.
- Every agent writes to *exactly one* field. No agent should write to two sections of state.
- Think of this as a strict "read-your-inputs, write-your-output" contract per node.

---

## 4. Agent Specifications

### 4.1 Requirements Agent

**Responsibility:** Translate the user's natural-language system design question into structured, unambiguous requirements. This is the foundation the rest of the pipeline builds on — if this agent gets it wrong, every downstream agent inherits the error.

| | |
|---|---|
| **Reads** | `problem_statement` |
| **Writes** | `requirements` |
| **Output type** | `RequirementsOutput` |

**Output contains:**
- Functional requirements
- Non-functional requirements
- Scale expectations
- Constraints
- Assumptions

**Must not:**
- Choose or suggest technologies
- Design any part of the architecture
- Estimate cost

> **Key highlight:** This agent's *only* job is requirement extraction. If you catch it recommending a database or sketching components, that's a contract violation.

---

### 4.2 Tech Stack Agent

**Responsibility:** Recommend a technology stack that satisfies the requirements produced upstream — nothing more.

| | |
|---|---|
| **Reads** | `requirements` |
| **Writes** | `techstack` |
| **Output type** | `TechStackOutput` |

**Output contains:**
- Frontend
- Backend
- Database
- Cache
- Queue
- Storage
- Deployment

**Must not:**
- Redefine or reinterpret requirements
- Invent new features not present in requirements
- Generate architecture or component design

> **Key highlight:** This agent recommends *technology choices*, not *system design*. Architecture decisions belong strictly to the next agent.

---

### 4.3 Architecture Agent

**Responsibility:** Produce the component-level system architecture based on the requirements and tech stack. This is also the agent responsible for handling revisions when the Critic sends the design back.

| | |
|---|---|
| **Reads** | `requirements`, `techstack`, `revision_notes` (optional), `revision_count` |
| **Writes** | `architecture` |
| **Output type** | `ArchitectureOutput` |

**Output contains:**
- Components
- Component responsibilities
- Data flow
- `connects_to` mapping (used later for diagramming)
- Design description

**Revision handling rules:**
- If `revision_count == 0` → ignore `revision_notes` entirely (first pass, nothing to revise yet).
- If `revision_count > 0` → `revision_notes` **must** be incorporated into the updated design.

> **Key highlight:** This is the only agent that owns design decisions in the entire pipeline. Everything downstream (Critic, Diagram) treats its output as the design of record.

---

### 4.4 Critic Agent

**Responsibility:** Review the architecture for problems — and only review it. This agent is a gatekeeper, not a fixer.

| | |
|---|---|
| **Reads** | `architecture` |
| **Writes** | `critic_verdict` |
| **Output type** | `CriticVerdict` |

**Output contains:**
- `verdict` → either `APPROVE` or `REVISE`
- `issues[]` → list of identified problems (empty if approved)

**Must not:**
- Fix or edit the architecture directly
- Redesign any component
- Silently approve without reviewing

> **Key highlight:** The Critic identifies problems and hands them off — it never touches the design itself. The pipeline uses `verdict` alone to decide whether to route to `Diagram` or loop back to `Architecture`.

---

### 4.5 Diagram Agent

**Responsibility:** Visualize the final, approved architecture as a Mermaid diagram. This is a rendering step, not a design step.

| | |
|---|---|
| **Reads** | `architecture` |
| **Writes** | `diagram` |
| **Output type** | `DiagramOutput` (contains `mermaid_diagram`) |

**Generation strategy (in priority order):**
1. **Preferred:** Build the diagram directly from `architecture.components` and their `connects_to` mappings.
2. **Fallback:** If connection data is unavailable, fall back to an LLM-based diagram generation pass.

**Must not:**
- Invent architecture that wasn't in the approved design
- Add components not present in `architecture.components`

> **Key highlight:** This agent visualizes existing architecture — it never designs. Anything it draws should be traceable back to the Architecture Agent's output.

---

## 5. Revision Loop Contract

When the Critic returns `REVISE`, the pipeline follows a fixed sequence:

1. Critic returns `REVISE`
2. Pipeline increments `revision_count += 1`
3. Pipeline passes `critic.issues` forward as `revision_notes`
4. Architecture Agent regenerates the design, incorporating the notes
5. Critic reviews the new architecture
6. Repeat steps 1–5 until `APPROVE` **or** the maximum revision count is reached

**Key notes:**
- `revision_count` is the single source of truth for how many loops have occurred — no agent should track this independently.
- The loop must terminate deterministically (either by approval or by hitting the cap) to avoid runaway execution.

---

## 6. Ownership Matrix

| Node | Reads | Writes |
|---|---|---|
| **Requirements** | `problem_statement` | `requirements` |
| **Tech Stack** | `requirements` | `techstack` |
| **Architecture** | `requirements`, `techstack`, `revision_notes` | `architecture` |
| **Critic** | `architecture` | `critic_verdict` |
| **Diagram** | `architecture` | `diagram` |

**Quick-reference rule of thumb:** if a node isn't listed as the writer of a field in this table, it should never be modifying that field — full stop.

---

## 7. Design Principles Recap

1. **Single Responsibility** — each agent performs one well-defined task, nothing adjacent.
2. **Loose Coupling** — agents communicate only through shared graph state, never through direct calls to one another.
3. **Immutable Outputs** — once an agent produces its output, it is treated as final and untouchable by others.
4. **Deterministic Routing** — all graph transitions are driven solely by `critic_verdict`.
5. **Explicit Contracts** — every node's required inputs and guaranteed outputs are documented, keeping the pipeline easy to extend, test, and swap out piece by piece.