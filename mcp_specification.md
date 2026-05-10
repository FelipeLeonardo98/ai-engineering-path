Aqui está o Documento Mestre consolidado. Ele foi estruturado para ser copiado e colado em qualquer editor Markdown (como VS Code, Obsidian ou Notion), preservando a formatação e os diagramas.
------------------------------
## 📘 Documentação de Projeto: Ecossistema MCP para Engenharia de IA
Este documento consolida a arquitetura, conceitos e códigos para a implementação de um servidor Model Context Protocol (MCP) integrado a fluxos de dados em tempo real.
------------------------------
## 1. Persona do Agente (System Prompt)
Utilize este prompt para configurar o especialista em qualquer interface de IA.

"Você é um Engenheiro de IA Sênior especializado em MCP (Model Context Protocol). Sua missão é guiar a construção de servidores que conectam LLMs a dados privados (Bancos, APIs e Filas de Eventos). Você opera em duas etapas: primeiro explica a arquitetura e aguarda aprovação, depois fornece o código. Seu foco é segurança, escalabilidade e o uso de padrões modernos (async/await)."

------------------------------
## 2. Conceitos Fundamentais (Caminho A vs Caminho B)
Ao conectar uma IA a um banco de dados ou API, existem duas abordagens principais:

* Caminho A (Orquestrador/Natural): O LLM recebe o esquema da tabela (ex: nomes de colunas) e escreve o SQL por conta própria.
* Pró: Flexibilidade total para perguntas complexas.
   * Contra: Requer travas de segurança (Read-Only) para evitar injeção de comandos.
* Caminho B (Especialista/Controlado): Você define funções fixas (ex: get_status(user_id)).
* Pró: Segurança máxima e previsibilidade.
   * Contra: Menos flexibilidade; se a função não existir, a IA não responde.

------------------------------
## 3. Arquitetura: Observabilidade de Jornada (Kafka + Redis)
Para monitorar usuários em múltiplos canais (WhatsApp, Voz, Chat) em tempo real, a arquitetura recomendada utiliza o Estado Consolidado:
## Fluxo de Dados

   1. Eventos Brutos: Kafka recebe eventos de múltiplos canais.
   2. Worker de Estado: Um serviço consome o Kafka e salva a "foto atual" do usuário no Redis.
   3. MCP Server: Expõe ferramentas que consultam o Redis sob demanda do LLM.

## Diagrama (Mermaid)

graph LR
    subgraph "Ingestão"
        W[WhatsApp] --> K[Kafka]
        V[Voz] --> K
    end
    subgraph "Processamento"
        K --> Worker[State Worker]
        Worker --> Redis[(Redis Cache)]
    end
    subgraph "IA"
        Redis <--> MCP[MCP Server]
        MCP <--> LLM[Claude/GPT]
        User[Gestor] --> |"Onde está o João?"| LLM
    end

------------------------------
## 4. Exemplos de Implementação (Python)## 4.1. MCP Server Híbrido (SQL + API Privada)

import asyncioimport mcp.types as typesfrom mcp.server import Serverfrom mcp.server.stdio import stdio_server
server = Server("ai-specialist")

@server.list_tools()async def handle_list_tools() -> list[types.Tool]:
    return [
        # Caminho A: Flexível
        types.Tool(
            name="query_estoque",
            description="Executa SQL SELECT na tabela 'estoque' (item, qtd, preco).",
            inputSchema={
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"]
            }
        ),
        # Caminho B: Controlado (Ex: Consulta Redis/API)
        types.Tool(
            name="localizar_usuario",
            description="Retorna o canal atual e status de um usuário via ID.",
            inputSchema={
                "type": "object",
                "properties": {"user_id": {"type": "string"}},
                "required": ["user_id"]
            }
        )
    ]
# Implementação das chamadas omitida para brevidade (ver histórico do chat)

## 4.2. Servidor com Transporte SSE (Acesso Remoto via Web)

from fastapi import FastAPI, Requestfrom mcp.server import Serverfrom mcp.server.sse import SseServerTransport
app = FastAPI()mcp_server = Server("remote-mcp")sse = SseServerTransport("/messages")

@app.get("/sse")async def handle_sse(request: Request):
    async with sse.connect_scope(request.scope, request.receive, request.send) as scope:
        await mcp_server.run(scope.read_stream, scope.write_stream, mcp_server.create_initialization_options())

@app.post("/messages")async def handle_messages(request: Request):
    await sse.handle_post_resource(request.scope, request.receive, request.send)

------------------------------
## 5. Próximos Passos Sugeridos

   1. Segurança: Implementar SELECT-only no banco e sanitização de strings para o Caminho A.
   2. Infra: Containerizar o Servidor MCP com Docker para deploy em nuvem.
   3. Monitoramento: Utilizar o mcp-inspector para depurar as chamadas de ferramentas.

------------------------------
Dica: Salve este conteúdo como especificacao_mcp.md. Se precisar de ajuda para codificar o Worker do Kafka que alimenta o Redis, é só me chamar!
Como você quer prosseguir com a implementação do Worker?

