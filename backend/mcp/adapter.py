# mcp/adapter.py

from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route("/model/query", methods=["POST"])
def model_query():
    data = request.json
    tool_name = "rag.ask"
    response = requests.post(
        "http://localhost:5000/rag/ask",
        json={"question": data.get("query")},
        timeout=10
    )
    return jsonify(response.json())

@app.route("/tool/callTool", methods=["POST"])
def call_tool():
    data = request.json
    tool_name = data.get("tool_name")
    params = data.get("parameters", {})
    
    if tool_name == "external.delegate":
        target_url = params.get("url")
        question = params.get("question")
        response = requests.post(
            f"{target_url}/model/query",
            json={"model_name": "mistral-local", "query": question},
            timeout=10
        )
        return jsonify(response.json())
    
    elif tool_name == "query.hybrid":
        response = requests.post(
            "http://localhost:5000/query",
            json={"query": params.get("query")},
            timeout=10
        )
        return jsonify(response.json())

    else:
        return jsonify({"error": "Unsupported tool"}), 400
