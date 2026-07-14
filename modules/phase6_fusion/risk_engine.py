from modules.phase6_fusion.trust_fusion import TrustIndexFusion
import datetime

class TruthLensRiskEngine:
    def __init__(self):
        print("[*] Initializing TruthLens Trust Index Fusion Engine (Phase 6)...")
        self.fusion = TrustIndexFusion()

    def compute_final_verdict(self, 
                              yt_metadata=None, 
                              social_results=None, 
                              nlp_results=None, 
                              vision_results=None, 
                              graph_results=None):
        """
        Fuses all 6 phases of intelligence into a unified TruthLens report.
        """
        # Map YouTube metadata to the format expected by Phase 6
        yt_stats = {
            "views": (yt_metadata.get("view_count") or 0) if isinstance(yt_metadata, dict) else 0,
            "likes": (yt_metadata.get("like_count") or 0) if isinstance(yt_metadata, dict) else 0,
            "comments": (yt_metadata.get("comment_count") or 0) if isinstance(yt_metadata, dict) else 0
        }
        
        # Fuse intelligence
        report = self.fusion.compute(
            stats=yt_stats,
            harvest_result=social_results,
            nlp_result=nlp_results,
            cv_result=vision_results,
            graph_result=graph_results
        )
        
        return report

    def get_summary(self, video_id, report):
        """
        Generates a human-readable summary for the dashboard.
        """
        return {
            "video_id": video_id,
            "verdict": report["risk_level"],
            "trust_score": (1 - report["composite_score"]) * 100,
            "risk_score": report["composite_score"] * 100,
            "confidence": report["confidence"] * 100,
            "red_flags": report["red_flags"],
            "timestamp": datetime.datetime.now().isoformat()
        }
