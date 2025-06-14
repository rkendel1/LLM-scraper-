import networkx as nx
import os
import json

def build_ontology(crawled_docs, domain):
    G = nx.DiGraph()
    
    for doc in crawled_docs:
        url = doc['url']
        title = doc.get('title', url)
        G.add_node(url, title=title)

        # Extract internal links from text or HTML
        links = extract_internal_links(doc['html'], domain)
        for link in links:
            if link in [d['url'] for d in crawled_docs]:
                G.add_edge(url, link)

    # Save as GraphML
    nx.write_graphml(G, f"graphs/{domain}.graphml")

    return G

def extract_internal_links(html, domain):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    links = set()

    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith(f"https://{domain}")  or href.startswith("/"):
            full_url = resolve_url(href, domain)
            links.add(full_url)

    return list(links)

def resolve_url(href, domain):
    if href.startswith("http"):
        return href
    else:
        return f"https://{domain}{href}" 
def export_graph_json(G, domain):
    nodes = [{"id": n, "title": G.nodes[n].get("title", n)} for n in G.nodes]
    edges = [{"source": u, "target": v} for u, v in G.edges]

    data = {"nodes": nodes, "links": edges}
    with open(f"graphs/{domain}.json", "w") as f:
        json.dump(data, f)
