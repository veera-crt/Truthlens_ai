from modules.phase5_network.coordination import CoordinationMapper
import json

class GraphEngine:
    def __init__(self):
        print("[*] Initializing TruthLens Coordination Intelligence (Phase 5)...")
        self.mapper = CoordinationMapper()

    def analyze_coordination(self, posts):
        """
        Builds a multi-layer graph of posts and authors to detect CIB 
        (Coordinated Inauthentic Behavior).
        """
        # posts should be a list of standardized post objects from the queue
        if not posts:
            return {"coordination_score": 0, "clusters_detected": 0, "suspicious_nodes": []}
            
        results = self.mapper.build_graph(posts)
        
        # Normalize/Scale for the TruthLens UI
        coordination_score = results.get("coordination_score", 0) * 100
        
        return {
            "coordination_score": round(coordination_score, 1),
            "clusters_detected": len(results.get("suspicious_clusters", [])),
            "suspicious_nodes": results.get("suspicious_clusters", []),
            "bot_suspects": results.get("bot_suspects", []),
            "top_amplifiers": results.get("top_amplifiers", []),
            "graph_data": {
                "nodes": results.get("graph_nodes", []),
                "links": results.get("graph_edges", [])
            }
        }

    def get_cluster_report(self, posts):
        """
        Generates a summary of the most dense coordination clusters.
        """
        analysis = self.analyze_coordination(posts)
        return {
            "risk_level": "HIGH" if analysis["coordination_score"] > 60 else "LOW",
            "summary": f"Detected {analysis['clusters_detected']} suspicious coordination clusters.",
            "top_suspects": analysis["bot_suspects"][:5]
        }
