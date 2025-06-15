from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

app = FastAPI(
    title="MCP Adapter API",
    description="Adapter for MCP model queries and tool calls",
    version="1.0.0"
)

class ModelQueryRequest(BaseModel):
    query: str

class ToolCallRequest(BaseModel):
    tool_name: str
    parameters: dict = {}

@app.post("/model/query")
async def model_query(request: ModelQueryRequest):
    tool_name = "rag.ask"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:5000/rag/ask",
            json={"question": request.query},
            timeout=10
        )
    
    return response.json()

@app.post("/tool/callTool")
async def call_tool(request: ToolCallRequest):
    tool_name = request.tool_name
    params = request.parameters
    
    if tool_name == "external.delegate":
        target_url = params.get("url")
        question = params.get("question")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{target_url}/model/query",
                json={"model_name": "mistral-local", "query": question},
                timeout=10
            )
        
        return response.json()
    
    elif tool_name == "query.hybrid":
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:5000/query",
                json={"query": params.get("query")},
                timeout=10
            )
        
        return response.json()
    else:
        raise HTTPException(status_code=400, detail={"error": "Unsupported tool"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
