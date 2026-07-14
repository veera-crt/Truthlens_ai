import requests
# pyrefly: ignore [missing-import]
import certifi
import os
# removed wikipedia and duckduckgo
# pyrefly: ignore [missing-import]
from sentence_transformers import SentenceTransformer, util
import networkx as nx
import json
import uuid

# Global cache to prevent rate-limiting
CACHE = {}

class EvidenceRetrievalEngine:
    def __init__(self):
        print("[*] Initializing TruthLens Evidence Retrieval Engine v2...")
        self.device = -1 # CPU
        
        print("📥 Loading Semantic Brain (all-MiniLM-L6-v2)...")
        self.similarity_model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        
        self.NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
        
        self.SOURCE_WEIGHT = {
            "tavily": 0.95,
            "exa": 0.90,
            "serper": 0.85,
            "who.int": 1.0,
            "gov.in": 0.95,
            "reuters.com": 0.9,
            "bbc.com": 0.85
        }



    def _get_tavily_evidence(self, query):
        try:
            # pyrefly: ignore [missing-import]
            from tavily import TavilyClient
            client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
            response = client.search(
                query=query,
                include_answer="basic",
                search_depth="advanced",
                max_results=3
            )
            text = response.get("answer", "")
            if not text and response.get("results"):
                text = " ".join([r.get("content", "") for r in response.get("results")])
            url = response.get("results")[0].get("url", "") if response.get("results") else ""
            return {"text": text[:1000], "url": url, "source_type": "tavily"}
        except Exception as e:
            print(f"⚠️ Tavily error: {e}")
            return {"text": "", "url": ""}

    def _get_exa_evidence(self, query):
        api_key = os.getenv("EXA_API_KEY")
        if not api_key: return {"text": "", "url": ""}
        try:
            headers = {"x-api-key": api_key, "Content-Type": "application/json"}
            payload = {
                "query": query,
                "useAutoprompt": True,
                "type": "neural",
                "contents": {"text": True},
                "numResults": 2
            }
            res = requests.post("https://api.exa.ai/search", headers=headers, json=payload, verify=certifi.where(), timeout=15).json()
            results = res.get("results", [])
            if not results: return {"text": "", "url": ""}
            text = " ".join([r.get("text", "") for r in results])
            url = results[0].get("url", "")
            return {"text": text[:1000], "url": url, "source_type": "exa"}
        except Exception as e:
            print(f"⚠️ Exa error: {e}")
            return {"text": "", "url": ""}

    def _get_serper_evidence(self, query):
        api_key = os.getenv("SERPER_API_KEY")
        if not api_key: return {"text": "", "url": ""}
        try:
            payload = {
                "q": query,
                "gl": "in",
                "hl": "en",
                "num": 5
            }
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
            res = requests.post("https://google.serper.dev/search", headers=headers, json=payload, verify=certifi.where(), timeout=10)
            data = res.json()
            
            snippets = []
            if "organic" in data:
                snippets = [r.get("snippet", "") for r in data["organic"]][:3]
            text = " ".join(snippets)
            url = data.get("organic", [{}])[0].get("link", "") if snippets else ""
            return {"text": text[:1000], "url": url, "source_type": "serper"}
        except Exception as e:
            print(f"⚠️ Serper error: {e}")
            return {"text": "", "url": ""}

    def _fetch_all_evidence(self, query):
        """Retrieves evidence via Smart Fallback Routing."""
        if query in CACHE:
            return CACHE[query]
            
        results = {}
        
        # 1. Try Serper (Fast web / Breaking news)
        serper_res = self._get_serper_evidence(query)
        if serper_res.get("text"):
            results["serper"] = serper_res
            CACHE[query] = results
            return results
            
        # 2. Try Tavily (Clean Summaries) if Serper failed
        tavily_res = self._get_tavily_evidence(query)
        if tavily_res.get("text"):
            results["tavily"] = tavily_res
            CACHE[query] = results
            return results
            
        # 3. Try Exa (Deep Semantic Search) if both failed
        exa_res = self._get_exa_evidence(query)
        if exa_res.get("text"):
            results["exa"] = exa_res
            CACHE[query] = results
            return results
            
        CACHE[query] = results
        return results

    def semantic_score(self, claim, evidence_text):
        if not evidence_text: return 0.0
        emb1 = self.similarity_model.encode(claim, convert_to_tensor=True)
        emb2 = self.similarity_model.encode(evidence_text, convert_to_tensor=True)
        return util.cos_sim(emb1, emb2).item()

    def get_source_weight(self, source_url, source_type):
        for k, v in self.SOURCE_WEIGHT.items():
            if k in source_url.lower():
                return v
        return self.SOURCE_WEIGHT.get(source_type, 0.5)

    def _build_evidence_graph(self, claim, evidence_dict):
        """Constructs a NetworkX graph linking Claims, Evidence, and Sources."""
        G = nx.DiGraph()
        G.add_node("CLAIM", type="claim", text=claim)
        
        support_edges = 0
        contradict_edges = 0
        total_edges = 0
        
        max_semantic = 0.0
        max_credibility = 0.0
        best_evidence_text = ""
        best_evidence_url = ""
        best_source_type = ""
        
        for e_type, e_data in evidence_dict.items():
            text = e_data.get("text", "")
            url = e_data.get("url", "")
            source_type = e_data.get("source_type", "")
            if not text: continue
            
            # Nodes
            ev_node_id = f"EV_{e_type}"
            src_node_id = f"SRC_{source_type}"
            
            G.add_node(ev_node_id, type="evidence", text=text, url=url)
            G.add_node(src_node_id, type="source", url=url)
            
            # Evidence -> Source Edge
            G.add_edge(ev_node_id, src_node_id, relation="comes_from")
            
            # Semantic Alignment
            semantic = self.semantic_score(claim, text)
            credibility = self.get_source_weight(url, source_type)
            
            if semantic > max_semantic:
                max_semantic = semantic
                max_credibility = credibility
                best_evidence_text = text
                best_evidence_url = url
                best_source_type = e_type
                
            total_edges += 1
            # Simple threshold for support vs contradict
            if semantic >= 0.4:
                G.add_edge("CLAIM", ev_node_id, relation="supported_by", weight=semantic)
                support_edges += 1
            else:
                G.add_edge("CLAIM", ev_node_id, relation="contradicts", weight=semantic)
                contradict_edges += 1
                
        # Calculate Graph Consensus
        if total_edges > 0:
            consensus = (support_edges - contradict_edges) / total_edges
        else:
            consensus = 0.0
            
        return G, max_semantic, max_credibility, consensus, best_evidence_text, best_evidence_url, best_source_type

    def verify_claim(self, claim, search_query=None):
        """Calculates Trust Score by fusing semantic alignment, source credibility, and graph consensus."""
        
        # Use provided query from Gemini, or fallback to simple keyword extraction
        if not search_query or len(search_query.strip()) == 0:
            stopwords = ["is", "a", "the", "this", "that", "has", "been", "to", "and", "or", "of", "in"]
            words = [w for w in claim.lower().split() if w not in stopwords]
            search_query = " ".join(words[:12])
            
        evidence_dict = self._fetch_all_evidence(search_query)
        
        # Build NetworkX Graph and compute metrics
        G, semantic, credibility, consensus, best_text, best_url, best_src = self._build_evidence_graph(claim, evidence_dict)
        
        if not best_text or semantic < 0.2:
            return {
                "claim": claim,
                "evidence_confidence": 0.0,
                "supporting_source": {"source": "#", "title": "No Evidence Found"}
            }
            
        # The baseline TrustScore formula
        # TrustScore = (α × EvidenceScore) + (β × SourceCredibility) + (γ × GraphConsensus)
        alpha = 0.5
        beta = 0.3
        gamma = 0.2
        
        # Normalize consensus from [-1, 1] to [0, 1] for scoring
        normalized_consensus = (consensus + 1.0) / 2.0
        
        trust_score = (alpha * semantic) + (beta * credibility) + (gamma * normalized_consensus)
        
        # Sigmoid normalization (simplified)
        trust_score = max(0.0, min(1.0, trust_score))
        
        # Serialize the graph to JSON for GNN training
        try:
            os.makedirs("dataset/gnn_training", exist_ok=True)
            graph_data = nx.node_link_data(G)
            graph_data["baseline_trust_score"] = trust_score
            graph_data["claim"] = claim
            
            file_id = str(uuid.uuid4())[:8]
            filepath = os.path.join("dataset/gnn_training", f"graph_{file_id}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(graph_data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save GNN training graph: {e}")
        
        return {
            "claim": claim,
            "evidence_text": best_text,
            "evidence_confidence": trust_score,
            "supporting_source": {
                "source": best_url, 
                "title": f"Verified via {best_src.upper()}"
            },
            "graph_metrics": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "consensus": round(consensus, 3)
            },
            "graph_data": graph_data
        }
