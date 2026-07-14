"""
PHASE 6: Trust Index Fusion
Aggregates signals from all 5 phases into a single composite trust score.
Output: risk level, per-dimension breakdown, and human-readable recommendation.
"""

from datetime import datetime


# ─────────────────────────────────────────────
# SCORE NORMALIZERS
# Convert raw outputs from each phase → [0, 1] (Risk Space)
# ─────────────────────────────────────────────

def normalize_engagement(stats: dict) -> float:
    """
    stats: {"views": int, "likes": int, "comments": int, "dislikes": int}
    Anomalous engagement (no comments but many likes) → high score.
    """
    views = max(stats.get("views", 0), 1)
    likes = stats.get("likes", 0)
    comments = stats.get("comments", 0)

    like_rate = likes / views
    comment_rate = comments / views

    score = 0.0

    # Suspiciously high like rate with near-zero comments = purchased likes
    if like_rate > 0.1 and comment_rate < 0.001:
        score += 0.6
    # Extremely high like rate overall
    if like_rate > 0.2:
        score += 0.3
    # Comments disabled (comment_rate = 0 exactly) on viral video
    if views > 10_000 and comments == 0:
        score += 0.2

    return min(score, 1.0)


def normalize_platform_spread(harvest_result: dict) -> float:
    """
    Measures how rapidly content spread across platforms.
    Higher cross-platform velocity → more suspicious.
    """
    sources = harvest_result.get("sources", [])
    platforms_hit = len([s for s in sources if s.get("posts")])
    total_posts = sum(len(s.get("posts", [])) for s in sources)

    # More platforms + more posts = higher spread score
    spread_score = min((platforms_hit / 3.0) * 0.5 + (total_posts / 100.0) * 0.5, 1.0)
    return spread_score


def normalize_nlp(nlp_result: dict) -> float:
    """Extract manipulation score from NLP batch result."""
    if "aggregate" in nlp_result:
        return float(nlp_result["aggregate"].get("avg_manipulation_score", 0))
    return float(nlp_result.get("manipulation_score", 0))

def normalize_evidence(nlp_result: dict) -> float:
    """Extract evidence confidence and invert to Risk Space (1 = critical risk, 0 = safe)."""
    if "aggregate" in nlp_result:
        conf = float(nlp_result["aggregate"].get("avg_evidence_confidence", 1.0))
    else:
        conf = float(nlp_result.get("avg_evidence_confidence", 1.0))
    return 1.0 - conf


def normalize_graph(graph_result: dict) -> float:
    """Extract coordination score from graph analysis."""
    base = float(graph_result.get("coordination_score", 0))
    bot_penalty = min(len(graph_result.get("bot_suspects", [])) * 0.05, 0.3)
    return min(base + bot_penalty, 1.0)


# ─────────────────────────────────────────────
# RISK CLASSIFICATION
# ─────────────────────────────────────────────
RISK_BANDS = [
    (0.0,  0.2,  "AUTHENTIC",  "#22c55e", "Content shows no significant manipulation signals."),
    (0.2,  0.4,  "LOW RISK",   "#84cc16", "Minor anomalies detected. Likely authentic with minor concerns."),
    (0.4,  0.6,  "MODERATE",   "#f59e0b", "Multiple manipulation indicators present. Independent verification recommended."),
    (0.6,  0.8,  "HIGH RISK",  "#ef4444", "Strong manipulation signals across multiple dimensions. Flag for review."),
    (0.8,  1.01, "CRITICAL",   "#7c3aed", "Severe indicators of coordinated inauthentic behavior or deepfakes. Immediate action required."),
]


def classify_risk(score: float) -> dict:
    for lo, hi, label, color, desc in RISK_BANDS:
        if lo <= score < hi:
            return {"label": label, "color": color, "description": desc}
    return {"label": "UNKNOWN", "color": "#6b7280", "description": "Score out of expected range."}


# ─────────────────────────────────────────────
# CONFIDENCE ESTIMATOR
# ─────────────────────────────────────────────
def estimate_confidence(dimensions: dict) -> float:
    """
    Confidence is higher when:
    - All dimensions contributed (none are 0 due to missing data)
    - Scores across dimensions agree directionally
    """
    values = list(dimensions.values())
    non_zero = sum(1 for v in values if v > 0)
    coverage = non_zero / len(values)

    # Variance: low variance = high agreement = high confidence
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    agreement = max(0, 1 - (variance * 4))  # penalize disagreement

    return round((coverage * 0.5) + (agreement * 0.5), 3)


# ─────────────────────────────────────────────
# TRUST INDEX FUSION ENGINE
# ─────────────────────────────────────────────
class TrustIndexFusion:

    def compute(
        self,
        stats: dict = None,
        harvest_result: dict = None,
        nlp_result: dict = None,
        cv_result: dict = None,
        graph_result: dict = None,
    ) -> dict:
        """
        Accepts outputs from all 5 phase modules.
        Any missing inputs default to 0 (neutral).
        """
        stats = stats or {}
        harvest_result = harvest_result or {"sources": []}
        nlp_result = nlp_result or {}
        cv_result = cv_result or {}
        graph_result = graph_result or {}

        dimensions = {
            "engagement_anomaly":   normalize_engagement(stats),
            "platform_spread":      normalize_platform_spread(harvest_result),
            "nlp_manipulation":     normalize_nlp(nlp_result),
            "evidence_risk":        normalize_evidence(nlp_result),
            "coordination_network": normalize_graph(graph_result),
        }

        # ── LAYER 1: TRUTH CORE ──
        # Truth always dominates intent
        truth_risk_score = (dimensions["evidence_risk"] * 0.75) + (dimensions["nlp_manipulation"] * 0.25)
        
        # ── LAYER 2: PROPAGATION RISK AMPLIFIER ──
        propagation_multiplier = 1.0
        
        # Only amplify if Truth Risk is significant (prevents punishing authentic viral posts)
        if truth_risk_score > 0.2:
            virality_signal = (
                dimensions["engagement_anomaly"] * 0.40 + 
                dimensions["coordination_network"] * 0.30 + 
                dimensions["platform_spread"] * 0.30
            )
            # Cap amplification at 1.5x
            propagation_multiplier += virality_signal * 0.5
            
        final_risk = min(1.0, truth_risk_score * propagation_multiplier)
        composite = round(final_risk, 4)

        risk = classify_risk(composite)
        confidence = estimate_confidence(dimensions)

        # Collect all red flags
        red_flags = []
        
        # Smart Red Flag (Continuous severity)
        red_flag_severity = dimensions["nlp_manipulation"] * dimensions["evidence_risk"]
        if red_flag_severity > 0.3:
            red_flags.append(f"CRITICAL: Highly manipulative claim with zero verifiable evidence (Severity: {round(red_flag_severity, 2)})")
            
        if nlp_result:
            if "aggregate" in nlp_result:
                flagged = nlp_result["aggregate"].get("flagged_posts", 0)
                if flagged > 0:
                    red_flags.append(f"{flagged} posts with manipulation cues detected")
            cues = nlp_result.get("triggered_cues", [])
            if cues:
                red_flags.append(f"Manipulation phrases: {', '.join(cues[:3])}")
        if graph_result.get("bot_suspects"):
            bots = graph_result["bot_suspects"][:3]
            red_flags.append(f"Suspected bot accounts: {', '.join(bots)}")
        if graph_result.get("suspicious_clusters"):
            nc = len(graph_result["suspicious_clusters"])
            red_flags.append(f"{nc} coordinated account cluster(s) detected")

        # Per-dimension labels
        dimension_labels = {
            "evidence_risk":        "Evidence Risk (Unverified)",
            "nlp_manipulation":     "NLP Manipulation Score",
            "engagement_anomaly":   "Engagement Anomaly",
            "coordination_network": "Coordination Network",
            "platform_spread":      "Cross-Platform Spread"
        }

        return {
            "composite_score": composite,
            "risk_level": risk["label"],
            "risk_color": risk["color"],
            "risk_description": risk["description"],
            "confidence": confidence,
            "truth_risk_score": round(truth_risk_score, 4),
            "propagation_multiplier": round(propagation_multiplier, 4),
            "dimensions": {
                dimension_labels[k]: {
                    "score": round(dimensions[k], 4)
                }
                for k in dimension_labels
            },
            "red_flags": red_flags,
            "recommendation": risk["description"],
            "analyzed_at": datetime.utcnow().isoformat() + "Z",
        }


# ─────────────────────────────────────────────
# DEMO / STANDALONE TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import json

    engine = TrustIndexFusion()

    result = engine.compute(
        stats={"views": 500_000, "likes": 80_000, "comments": 12},
        harvest_result={"sources": [{"posts": ["a"] * 20}, {"posts": ["b"] * 15}]},
        nlp_result={"manipulation_score": 0.72, "triggered_cues": ["wake up", "share before deleted"]},
        cv_result={"manipulation_likelihood": 0.55, "flags": ["ELA: artifacts detected"]},
        graph_result={"coordination_score": 0.68, "bot_suspects": ["user_8921", "account_3340"], "suspicious_clusters": [["a","b","c"]]},
    )

    print(json.dumps(result, indent=2))
