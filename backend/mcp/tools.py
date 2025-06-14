import requests
from typing import Dict, Any, Optional
from mcp.server import ToolResult

# Define all tools available via MCP
TOOLS = {
    "rag.ask": {
        "name": "rag.ask",
        "description": "Ask a question using the local RAG pipeline",
        "parameters": {"question": "string"},
        "returns": {"answer": "string", "sources": "list"}
    },
    "query.hybrid": {
        "name": "query.hybrid",
        "description": "Search documents using hybrid keyword + vector search",
        "parameters": {"query": "string"},
        "returns": {"results": "list"}
    },
    "file.read": {
        "name": "file.read",
        "description": "Read content from a file (PDFs, TXT, etc.)",
        "parameters": {"path": "string"},
        "returns": {"content": "string"}
    },
    "pdf.upload": {
        "name": "pdf.upload",
        "description": "Download and process a PDF from a URL",
        "parameters": {"url": "string"},
        "returns": {"file_path": "string", "text": "string"}
    },
    "external.delegate": {
        "name": "external.delegate",
        "description": "Forward a query to an external agent (e.g., state-level chatbot)",
        "parameters": {"url": "string", "question": "string"},
        "returns": {"response": "object"}
    }
}


def execute_tool(tool_name: str, parameters: Dict[str, Any]) -> ToolResult:
    """
    Executes the specified tool with given parameters.
    """
    if tool_name == "rag.ask":
        # Import here to avoid circular dependencies
        from backend.app import ask_question
        
        # Simulate Flask's request object structure for compatibility
        class FakeRequest:
            def get_json(self):
                return {"question": parameters["question"]}
        
        result = ask_question(FakeRequest())
        return ToolResult(content=result)

    elif tool_name == "query.hybrid":
        # Import here to avoid circular dependencies
        from backend.app import hybrid_search
        
        # Simulate Flask's request object structure for compatibility
        class FakeRequest:
            def get_json(self):
                return {"query": parameters["query"]}
        
        result = hybrid_search(FakeRequest())
        return ToolResult(content={"results": result})

    elif tool_name == "file.read":
        path = parameters["path"]
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ToolResult(content={"content": content})
        except Exception as e:
            return ToolResult(error=str(e))

    elif tool_name == "pdf.upload":
        from processor.pdf_downloader import download_pdf
        file_path = download_pdf(parameters["url"])
        from processor.cleaner import extract_content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                pdf_text = f.read()
        except UnicodeDecodeError:
            with open(file_path, 'rb') as f:
                pdf_text = f.read().decode('utf-8', errors='ignore')
                
        cleaned = extract_content(pdf_text)
        return ToolResult(content={"file_path": file_path, "text": cleaned['text']})

    elif tool_name == "external.delegate":
        target_url = parameters.get("url")
        question = parameters.get("question")

        if not target_url or not question:
            return ToolResult(error="Missing url or question in parameters")

        try:
            response = requests.post(
                f"{target_url}/model/query",
                json={"model_name": "mistral-local", "query": question},
                timeout=10
            )
            if response.status_code == 200:
                return ToolResult(content=response.json())
            else:
                return ToolResult(error=f"External agent returned {response.status_code}: {response.text}")
        except Exception as e:
            return ToolResult(error=str(e))
    
    else:
        return ToolResult(error=f"Tool '{tool_name}' not found")
