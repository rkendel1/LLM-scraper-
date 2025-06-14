# mcp/server.py

from mcp.server import Server
from mcp.transport.http import HTTPTransport
from mcp.tools import TOOLS, execute_tool
import uvicorn

class MCPServer(Server):
    def __init__(self):
        super().__init__(
            name="LLM Scraper Federated Agent",
            version="1.0",
            tools=list(TOOLS.values()),
            models=["mistral-local"]
        )

    async def handle_tool_call(self, tool_name: str, parameters: dict) -> ToolResult:
        return execute_tool(tool_name, parameters)

    async def handle_model_query(self, model_name: str, query: str) -> ToolResult:
        return execute_tool("rag.ask", {"question": query})


# Start the server
if __name__ == "__main__":
    server = MCPServer()
    transport = HTTPTransport(server=server, port=8080)
    print("🚀 Starting MCP server at http://localhost:8080")
    uvicorn.run(transport.app, host="0.0.0.0", port=8080)
