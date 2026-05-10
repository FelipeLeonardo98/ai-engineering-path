# Week 9 Study Agenda: MCP Servers & Multi-Agent Systems

## Session 1: Architecture And Mental Model

Goal: understand MCP as a controlled bridge between AI clients and private systems.

- Draw `Agent/Client <-> MCP Server <-> Tools/Data`.
- Compare Path A and Path B.
- Explain why the LLM should not directly own database credentials or arbitrary system access.
- One-sentence summary: MCP is a contract that exposes approved context and actions to AI systems.

Reflection question: what should be a tool, what should be a resource, and what should stay unavailable?

## Session 2: MCP Server

Goal: build the local server and SQLite surface.

- Seed a local SQLite database.
- Expose `sqlite://schema` as a resource.
- Add controlled tools: `list_tables`, `describe_table`, `get_customer_by_id`.
- Add constrained Path A tool: `query_readonly`.
- Test unsafe input such as `DROP TABLE customers`.

Analogy: the MCP server is the reception desk. It can answer approved questions and call approved departments, but visitors do not get the master key.

## Session 3: Ollama Agent And Multi-Agent Thinking

Goal: connect a local LLM to MCP and reason about scaling the pattern.

- Run Ollama locally in Docker.
- Ask the LLM to select an MCP tool with JSON.
- Call the MCP server through stdio.
- Pass the result back to the LLM for a final answer.
- Extend the diagram conceptually to a supervisor agent, data agent, and support agent using shared MCP servers.

Final explanation: teach a junior engineer why fixed tools are safer than model-generated SQL, and when flexible SQL is still useful.
