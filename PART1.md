# Part 1: AI-Assisted Coding

## 1. Current Workflow

I use AI tools (Claude Code, ChatGPT, Cursor) as **architectural partners** rather than just code generators. My workflow follows a deliberate pattern:

**For AI-specific tasks (RAG pipelines, MCP servers)**:
- Start with **architecture design**: I describe the problem and constraints, then iterate on system design with the AI
- Use AI to **research best practices**: "Compare PyMuPDF vs Docling for PDF extraction" → evaluate tradeoffs → make informed decisions
- **Prototype rapidly**: Generate boilerplate (FastAPI routes, Pydantic schemas), then refine manually
- **Document as we go**: AI helps structure README sections while I provide technical rationale

**For general backend work**:
- More **directive**: "Write a Celery task for async document processing with progress tracking"
- Use for **repetitive patterns**: CRUD operations, database migrations, test fixtures
- Less iteration on architecture, more on implementation details

**Key difference**: For AI systems, I treat the AI as a **design collaborator** (questioning my assumptions, suggesting alternatives). For standard backend tasks, I use it as a **senior pair programmer** (executing my vision efficiently).

**This project**: I used Claude Code for ~80% of implementation. I designed the architecture (8 services, hybrid search, MCP tools), and Claude Code implemented it while I reviewed, tested, and refined. Critical decisions (PyMuPDF4LLM, cross-encoder reranking, tool interface design) were collaborative.

---

## 2. The Good & The Bad

### The Good

**Biggest value I've experienced**:

1. **Velocity on well-defined problems**: Building this MCP server with 10 tools would have taken 3-4 days manually. With AI: ~12 hours. The AI handles boilerplate, integrations, and edge cases I'd forget (like Redis cache serialization bugs).

2. **Knowledge synthesis**: When I asked "Should I use PyMuPDF4LLM or Docling for PDF extraction?", the AI researched both, compared performance, and helped me choose. This compressed hours of research into minutes.

3. **Documentation quality**: AI helps me write clear, comprehensive docs (see README.md). Left to myself, I'd write minimal docs and move on. AI encourages thoroughness.

### The Bad

**Current limitations and risks**:

1. **Over-confidence in generated code**: AI will confidently generate code that *looks* correct but has subtle bugs (e.g., the cache deserialization issue we hit). I now **always test** rather than assume correctness.

2. **Architecture decisions need human judgment**: AI suggested enabling cross-encoder reranking by default, but didn't initially consider the 10s cold-start latency impact. I had to weigh UX vs quality tradeoffs myself.

3. **Context window blindness**: When building systems consumed by AI agents, the AI doesn't naturally think about **its own limitations**. For example, it didn't initially suggest that MCP tool descriptions should include "Use this when..." guidance—I had to add that pattern based on understanding how LLMs consume tool definitions.

4. **Dependency sprawl**: AI will happily add dependencies (PaddleOCR, Tabula-py) without considering Docker image size (2GB+). Human oversight is critical for production constraints.

**Risk for AI-consumed systems**: There's a meta-problem where the AI helping you build the system doesn't deeply understand how another AI will interact with it. Tool naming, description clarity, default parameters—these need **human empathy** for the agent's perspective.

---

## 3. The Future

**My vision for the AI Solutions Engineer role**:

In 2-3 years, LLMs will write most code autonomously. The role will shift from **code author** to **system architect + quality gatekeeper**:

1. **Architecture becomes the skill**: Deciding "hybrid search with reranking" vs "vector-only search" will matter more than implementing either. LLMs will handle implementation; humans will handle tradeoffs (latency vs quality, cost vs accuracy, complexity vs maintainability).

2. **Agent-centric design thinking**: As more systems are consumed by AI agents (like MCP servers), we'll need deep intuition for **how agents think**. What makes a tool description unambiguous? What default parameters minimize agent errors? This is UX design, but for LLMs.

3. **Prompt engineering as a core skill**: The quality of my output will depend on how well I can **steer** AI collaborators. Clear problem statements, explicit constraints, and asking the right follow-up questions will be more valuable than typing speed.

4. **Human-in-the-loop becomes the job**: My role will be reviewing AI-generated architecture proposals, catching edge cases the AI missed, and making judgment calls on risks it can't assess (security, compliance, business impact).

**Skills that will matter most**:

- **Systems thinking**: Understanding how 8 microservices interact at scale, not just how to code a single service
- **Critical evaluation**: Quickly assessing AI-generated code for correctness, performance, and maintainability
- **Domain expertise**: Financial services, healthcare, legal—contexts where wrong answers have consequences and human judgment is non-negotiable
- **Communication**: Explaining technical decisions to non-technical stakeholders (clients, PMs) will be the **primary differentiator** when everyone has access to AI coding assistants

**My personal bet**: In 3 years, the best AI Solutions Engineers won't be the fastest coders—they'll be the people who can **architect elegant systems, ask the right questions, and explain complex tradeoffs clearly**. This assignment reinforced that: the code was fast to generate, but choosing PyMuPDF4LLM over Docling, designing 10 MCP tools with clear semantics, and documenting the "why" behind every decision—that required human judgment.

---

**Final note**: I'm excited about this shift. I've always enjoyed system design more than implementation details. If LLMs can handle the "boring" parts (CRUD, migrations, boilerplate), I get to spend more time on the interesting problems: "How do we make this knowledge base easy for an AI agent to use?" That's exactly the kind of challenge I'd love to tackle at indigo.ai.
