# Part 1: AI-Assisted Coding

## 1. Current Workflow

I use AI tools extensively throughout my development workflow, with **Claude Code** and **Cursor** as my primary assistants, complemented by ChatGPT for brainstorming and design discussions.

**For AI-specific tasks** (e.g., RAG pipelines, embedding strategies), I rely heavily on AI for:
- **Architecture design**: Discussing tradeoffs between vector stores (Qdrant vs Pinecone vs pgvector), chunking strategies, and hybrid search approaches
- **Prompt engineering**: Iterating on MCP tool descriptions and parameter schemas to optimize LLM decision-making
- **Performance optimization**: Generating test scenarios for BM25 vs vector search recall comparisons

**For general backend work**, I use AI differently:
- **Code generation**: Writing boilerplate (CRUD endpoints, Pydantic schemas, SQLAlchemy models) and having the AI adapt patterns I've established
- **Debugging**: Pasting error traces and asking for root cause analysis, especially for async/Celery issues
- **Documentation**: Auto-generating docstrings, README sections, and API documentation from code

The key difference is **validation rigor**: for AI systems consumed by other AI agents (like MCP servers), I manually review every tool description and parameter constraint because poor design compounds—an ambiguous tool description leads to incorrect agent decisions. For traditional backend code, I'm more willing to accept AI suggestions with lighter review.

## 2. The Good & The Bad

**The Good:**
- **Velocity on well-defined tasks**: AI excels at translating specs into working code. This project's backend (FastAPI + Celery + Qdrant integration) was 70% AI-generated, freeing me to focus on architecture and edge cases.
- **Knowledge retrieval**: Instead of reading Qdrant docs for 30 minutes, I ask Claude Code to show me the `query_points()` API with filters—instant context without breaking flow.
- **Iteration speed**: Testing chunking strategies (512 vs 1000 tokens, overlap ratios) is dramatically faster when AI generates test harnesses and comparison scripts.

**The Bad:**
- **Over-confidence in suboptimal patterns**: AI will confidently suggest `tiktoken.encoding_for_model("text-embedding-3-small")` when the correct approach is `tiktoken.get_encoding("cl100k_base")`. Silent failures are dangerous.
- **Context window blindness**: When building systems for AI consumption, AI assistants sometimes design tools that are too granular (`get_chunk_by_id`) or too broad (`search_everything`), missing the sweet spot for agent decision-making.
- **Hallucinated best practices**: AI often suggests "best practices" that are outdated (e.g., recommending `sentence-transformers` re-ranking when cross-encoders add 170ms latency for marginal gains in this use case).

**The biggest risk** for AI-consumed systems: **API design that optimizes for human intuition instead of LLM reasoning**. Humans understand implicit context ("search by tag probably filters existing results"), but LLMs need explicit descriptions ("use this when you want to narrow search to specific topics"). AI coding assistants don't naturally prioritize this.

## 3. The Future

**Short-term (1-2 years):** As LLMs improve at code generation, the AI Solutions Engineer role will shift from **writing code** to **designing systems** and **validating AI outputs**. Skills that matter most:
- **Prompt engineering for tool design**: Crafting MCP tool descriptions that guide agent behavior correctly
- **Evaluation methodologies**: Building test suites that measure retrieval quality (recall@k, MRR, nDCG) rather than just "does it run?"
- **Client communication**: Translating vague requirements ("make our documents searchable") into concrete constraints ("semantic search with tag-based filtering, <2s latency, citations to page numbers")

**Long-term (3-5 years):** I envision the role becoming **AI systems architect**—someone who:
- Designs multi-agent systems where one agent queries MCP tools, another validates results, and a third generates responses
- Debugs emergent behaviors (why did the agent choose `search_by_tag` when `search_by_document` was more appropriate?)
- Optimizes cost/quality tradeoffs (GPT-4 for reasoning, Claude for tool calling, local embeddings for cost)

The skills that will differentiate top engineers:
1. **Systems thinking**: Understanding how RAG pipelines, vector stores, caching layers, and re-ranking interact
2. **Behavioral debugging**: Diagnosing *why* an LLM made a bad tool choice (ambiguous description? Missing context? Insufficient examples?)
3. **Client empathy**: Explaining complex AI systems to non-technical stakeholders in terms of business value, not F1 scores

**What fades in importance**: Syntax knowledge, library-specific expertise (AI handles this), raw typing speed. **What rises**: Architectural judgment, evaluation rigor, and the ability to design systems that AI agents—and humans—can trust.

---

**Note on this project:** I used Claude Code for ~80% of code generation (FastAPI routes, Celery tasks, Pydantic schemas, Docker configs). I manually designed the MCP tool interface, chunking strategy, and hybrid search architecture. All tool descriptions were hand-tuned after observing how Claude interpreted them during testing.
