# backend/utils/forwarder.py

import requests

def forward_to_agent(agent_url: str, question: str):
    try:
        response = requests.post(
            f"{agent_url}/model/query",
            json={"model_name": "mistral-local", "query": question},
            timeout=10
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}
