# backend/utils/ontology_router.py

def route_query_to_agent(query: str) -> str:
    """
    Routes query to appropriate agent based on keywords.
    Returns endpoint URL or None if no match.
    """
    query = query.lower()
    
    if any(word in query for word in ["solar", "energy", "electricity"]):
        return "http://state-energy-agent:8080"
    
    elif any(word in query for word in ["zoning", "building", "permit"]):
        return "http://state-planning-agent:8080"
    
    elif any(word in query for word in ["tax", "revenue", "income"]):
        return "http://state-taxes-agent:8080"

    return None
