"""
PHASE 5: Graph Neural Networks & Coordination Mapping
Uses NetworkX for graph construction + coordination heuristics.
Detects: inorganic amplification, bot clusters, coordinated inauthentic behavior (CIB).
"""

import re
import math
from datetime import datetime
from collections import defaultdict, Counter


# ─────────────────────────────────────────────
# CONTENT SIMILARITY (pure Python cosine similarity)
# ─────────────────────────────────────────────
def tokenize(text: str) -> list:
    return re.findall(r'\b[a-z]{2,}\b', text.lower())


def tfidf_vector(tokens: list, idf: dict) -> dict:
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {t: (c / total) * idf.get(t, 1.0) for t, c in tf.items()}


def cosine_sim(v1: dict, v2: dict) -> float:
    keys = set(v1) | set(v2)
    dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in keys)
    mag1 = math.sqrt(sum(x**2 for x in v1.values()))
    mag2 = math.sqrt(sum(x**2 for x in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def build_idf(corpus: list) -> dict:
    N = len(corpus)
    doc_freq = Counter()
    for doc in corpus:
        for t in set(tokenize(doc)):
            doc_freq[t] += 1
    return {t: math.log((N + 1) / (f + 1)) + 1 for t, f in doc_freq.items()}


# ─────────────────────────────────────────────
# PURE-PYTHON GRAPH (no networkx needed)
# Falls back to NetworkX if available for richer metrics
# ─────────────────────────────────────────────
class SimpleGraph:
    def __init__(self):
        self.nodes = {}       # id -> {attrs}
        self.edges = []       # [(src, dst, {attrs})]
        self._adj = defaultdict(set)

    def add_node(self, node_id: str, **attrs):
        self.nodes[node_id] = self.nodes.get(node_id, {})
        self.nodes[node_id].update(attrs)

    def add_edge(self, src: str, dst: str, **attrs):
        self.edges.append((src, dst, attrs))
        self._adj[src].add(dst)
        self._adj[dst].add(src)

    def degree(self, node_id: str) -> int:
        return len(self._adj.get(node_id, set()))

    def connected_components(self) -> list:
        visited = set()
        components = []

        def dfs(node, component):
            visited.add(node)
            component.add(node)
            for neighbor in self._adj.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor, component)

        for node in self.nodes:
            if node not in visited:
                comp = set()
                dfs(node, comp)
                components.append(comp)

        return components

    def pagerank(self, damping: float = 0.85, iterations: int = 20) -> dict:
        if not self.nodes:
            return {}
        N = len(self.nodes)
        rank = {n: 1.0 / N for n in self.nodes}

        for _ in range(iterations):
            new_rank = {}
            for node in self.nodes:
                in_neighbors = [src for src, dst, _ in self.edges if dst == node]
                in_score = sum(
                    rank[src] / max(self.degree(src), 1)
                    for src in in_neighbors
                )
                new_rank[node] = (1 - damping) / N + damping * in_score
            rank = new_rank

        return rank


# ─────────────────────────────────────────────
# COORDINATION DETECTOR
# ─────────────────────────────────────────────
class CoordinationMapper:
    SIMILARITY_THRESHOLD = 0.65      # posts above this are "coordinated"
    TIME_WINDOW_MINUTES = 30         # posts within this window are time-correlated
    BOT_SCORE_THRESHOLD = 0.6

    def __init__(self):
        self.graph = SimpleGraph()

    def build_graph(self, posts: list) -> dict:
        """
        posts: list of dicts with keys:
          - author (str)
          - content (str)
          - timestamp (ISO str or empty)
          - platform (str)
          - metrics (dict: likes, retweets, views, followers)
        """
        if not posts:
            return {"error": "No posts provided", "nodes": 0}

        self.graph = SimpleGraph()

        # Add author nodes
        for post in posts:
            author = post.get("author", "unknown")
            metrics = post.get("metrics", {})
            self.graph.add_node(
                author,
                platform=post.get("platform", "unknown"),
                post_count=self.graph.nodes.get(author, {}).get("post_count", 0) + 1,
                followers=metrics.get("followers_count", 0),
            )

        # Build IDF for similarity scoring
        contents = [p.get("content", "") for p in posts]
        idf = build_idf(contents)
        vectors = [tfidf_vector(tokenize(c), idf) for c in contents]

        # Connect nodes with high content similarity
        for i in range(len(posts)):
            for j in range(i + 1, len(posts)):
                sim = cosine_sim(vectors[i], vectors[j])
                if sim >= self.SIMILARITY_THRESHOLD:
                    a1 = posts[i].get("author", f"user_{i}")
                    a2 = posts[j].get("author", f"user_{j}")
                    if a1 != a2:
                        self.graph.add_edge(a1, a2, similarity=round(sim, 3), type="content_similarity")

        # Connect nodes posting within tight time windows
        self._add_temporal_edges(posts)

        return self._compute_metrics(posts)

    def _add_temporal_edges(self, posts: list):
        """Link authors who post at similar timestamps."""
        timed = []
        for post in posts:
            ts_str = post.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                timed.append((post.get("author", "unknown"), ts))
            except Exception:
                pass

        timed.sort(key=lambda x: x[1])
        for i in range(len(timed)):
            for j in range(i + 1, len(timed)):
                delta_min = (timed[j][1] - timed[i][1]).total_seconds() / 60
                if delta_min > self.TIME_WINDOW_MINUTES:
                    break
                if timed[i][0] != timed[j][0]:
                    self.graph.add_edge(
                        timed[i][0], timed[j][0],
                        time_delta_minutes=round(delta_min, 1),
                        type="temporal_proximity"
                    )

    def _compute_metrics(self, posts: list) -> dict:
        n_nodes = len(self.graph.nodes)
        n_edges = len(self.graph.edges)

        if n_nodes == 0:
            return {"nodes": 0, "edges": 0, "coordination_score": 0.0, "clusters": [], "top_accounts": []}

        # Coordination density
        max_edges = n_nodes * (n_nodes - 1) / 2 or 1
        edge_density = n_edges / max_edges

        # Cluster analysis
        components = self.graph.connected_components()
        suspicious_clusters = [list(c) for c in components if len(c) > 1]

        # PageRank for top amplifiers
        pr = self.graph.pagerank()
        top_accounts = sorted(pr.items(), key=lambda x: x[1], reverse=True)[:5]

        # Bot likelihood per node
        bot_scores = self._bot_scores(posts)

        # Overall coordination score
        cluster_score = len(suspicious_clusters) / max(n_nodes, 1)
        density_score = min(edge_density * 5, 1.0)
        coordination_score = (cluster_score * 0.4) + (density_score * 0.6)

        # Edge type breakdown
        edge_types = Counter(e[2].get("type", "unknown") for e in self.graph.edges)

        return {
            "nodes": n_nodes,
            "edges": n_edges,
            "edge_density": round(edge_density, 4),
            "coordination_score": round(min(coordination_score, 1.0), 4),
            "suspicious_clusters": suspicious_clusters,
            "top_amplifiers": [{"author": a, "pagerank": round(s, 4)} for a, s in top_accounts],
            "bot_suspects": [a for a, s in bot_scores.items() if s > self.BOT_SCORE_THRESHOLD],
            "bot_scores": {a: round(s, 3) for a, s in bot_scores.items()},
            "edge_types": dict(edge_types),
            "graph_nodes": [
                {
                    "id": nid,
                    "degree": self.graph.degree(nid),
                    "pagerank": round(pr.get(nid, 0), 4),
                    **attrs,
                }
                for nid, attrs in self.graph.nodes.items()
            ],
            "graph_edges": [
                {"source": src, "target": dst, **attrs}
                for src, dst, attrs in self.graph.edges
            ],
        }

    def _bot_scores(self, posts: list) -> dict:
        """
        Heuristic bot likelihood per author.
        Signals: low follower count, high post rate, generic usernames, round numbers.
        """
        author_posts = defaultdict(list)
        for post in posts:
            author_posts[post.get("author", "unknown")].append(post)

        scores = {}
        for author, author_post_list in author_posts.items():
            score = 0.0
            metrics = author_post_list[-1].get("metrics", {})

            # Generic username pattern (user123, account_2847, etc.)
            if re.match(r'^(user|account|profile|node)[_\d]+$', author, re.I):
                score += 0.3

            # Low follower count
            followers = metrics.get("followers_count", 0)
            if 0 < followers < 50:
                score += 0.2

            # Round like numbers (often purchased engagement)
            likes = metrics.get("like_count", metrics.get("public_metrics", {}).get("like_count", 0))
            if likes > 0 and likes % 100 == 0:
                score += 0.1

            # High post count in short period = automation signal
            if len(author_post_list) > 5:
                score += 0.2

            scores[author] = min(score, 1.0)

        return scores
