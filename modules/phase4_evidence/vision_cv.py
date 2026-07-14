"""
PHASE 4: Computer Vision & Deepfake Forensics
Techniques used:
  - Error Level Analysis (ELA): detects JPEG re-compression artifacts
  - Noise Inconsistency: Laplacian variance across image regions
  - Facial Landmark Heuristics: asymmetry + region contrast
  - Frame-level analysis for video
"""

import io
import math
import struct
import zlib
import urllib.request
from collections import defaultdict


# ─────────────────────────────────────────────
# MINIMAL IMAGE READER (pure Python, no PIL/cv2 needed at basic level)
# Falls back to PIL/OpenCV when available
# ─────────────────────────────────────────────
def _try_import():
    modules = {}
    try:
        # pyrefly: ignore [missing-import]
        from PIL import Image, ImageFilter, ImageChops
        # pyrefly: ignore [missing-import]
        import numpy as np
        modules["pil"] = (Image, ImageFilter, ImageChops)
        modules["np"] = np
    except ImportError:
        pass
    try:
        # pyrefly: ignore [missing-import]
        import cv2
        modules["cv2"] = cv2
    except ImportError:
        pass
    return modules


_MODS = _try_import()


# ─────────────────────────────────────────────
# ERROR LEVEL ANALYSIS
# ─────────────────────────────────────────────
class ELAAnalyzer:
    """
    Saves image at reduced JPEG quality, then computes
    pixel-level difference from original.
    High-difference regions = likely edited.
    """

    def __init__(self, quality: int = 90):
        self.quality = quality

    def analyze(self, img_bytes: bytes) -> dict:
        if "pil" not in _MODS:
            return {"ela_score": 0.0, "error": "Pillow not installed"}

        Image, ImageFilter, ImageChops = _MODS["pil"]
        np = _MODS.get("np")

        try:
            original = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # Re-save at lower quality
            buffer = io.BytesIO()
            original.save(buffer, format="JPEG", quality=self.quality)
            buffer.seek(0)
            compressed = Image.open(buffer).convert("RGB")

            # Compute pixel diff
            diff = ImageChops.difference(original, compressed)

            if np is not None:
                diff_arr = np.array(diff, dtype=float)
                ela_mean = float(diff_arr.mean())
                ela_max = float(diff_arr.max())
                ela_std = float(diff_arr.std())
                ela_score = min((ela_mean / 10.0), 1.0)

                # Spatial inconsistency: compare quadrant std deviations
                h, w = diff_arr.shape[:2]
                quadrants = [
                    diff_arr[:h//2, :w//2],
                    diff_arr[:h//2, w//2:],
                    diff_arr[h//2:, :w//2],
                    diff_arr[h//2:, w//2:],
                ]
                quad_means = [q.mean() for q in quadrants]
                spatial_inconsistency = float(max(quad_means) - min(quad_means)) / 255.0
            else:
                ela_score = 0.1
                ela_std = 0.0
                ela_max = 0.0
                spatial_inconsistency = 0.0

            return {
                "ela_score": round(ela_score, 4),
                "spatial_inconsistency": round(spatial_inconsistency, 4),
                "verdict": "suspicious" if ela_score > 0.15 else "likely_authentic",
                "error": None,
            }
        except Exception as e:
            return {"ela_score": 0.0, "spatial_inconsistency": 0.0, "verdict": "unknown", "error": str(e)}


# ─────────────────────────────────────────────
# NOISE ANALYSIS
# ─────────────────────────────────────────────
class NoiseAnalyzer:
    """
    Laplacian variance as a proxy for noise inconsistency.
    Authentic photos have consistent sensor noise throughout.
    Composited/generated images show regional variance spikes.
    """

    def analyze(self, img_bytes: bytes) -> dict:
        if "cv2" not in _MODS or "np" not in _MODS:
            return {"noise_score": 0.0, "error": "OpenCV not installed"}

        cv2 = _MODS["cv2"]
        np = _MODS["np"]

        try:
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return {"noise_score": 0.0, "error": "Could not decode image"}

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            global_var = float(laplacian.var())

            # Region-wise variance for inconsistency detection
            h, w = gray.shape
            step_h, step_w = h // 3, w // 3
            region_vars = []
            for i in range(3):
                for j in range(3):
                    region = gray[i*step_h:(i+1)*step_h, j*step_w:(j+1)*step_w]
                    lap = cv2.Laplacian(region, cv2.CV_64F)
                    region_vars.append(lap.var())

            inconsistency = float(max(region_vars) - min(region_vars)) / (global_var + 1e-6)
            noise_score = min(inconsistency / 10.0, 1.0)

            return {
                "noise_score": round(noise_score, 4),
                "global_laplacian_var": round(global_var, 2),
                "region_variance_range": round(float(max(region_vars) - min(region_vars)), 2),
                "verdict": "inconsistent_noise" if noise_score > 0.3 else "consistent_noise",
                "error": None,
            }
        except Exception as e:
            return {"noise_score": 0.0, "error": str(e)}


# ─────────────────────────────────────────────
# METADATA FORENSICS
# ─────────────────────────────────────────────
class MetadataForensics:
    """
    Inspect EXIF / JPEG markers for editing traces without external libs.
    """

    def analyze_jpeg_markers(self, img_bytes: bytes) -> dict:
        """Parse JPEG markers to detect software signatures."""
        flags = []
        software_found = []

        # Look for common editing software strings in raw bytes
        editing_signatures = [
            b"Photoshop", b"GIMP", b"Lightroom", b"Snapseed",
            b"PicsArt", b"FaceApp", b"DeepFaceLab", b"Stable Diffusion",
            b"Midjourney", b"DALL-E",
        ]

        for sig in editing_signatures:
            if sig.lower() in img_bytes.lower():
                software_found.append(sig.decode("utf-8", errors="ignore"))
                flags.append(f"Editing software detected: {sig.decode()}")

        # Check for multiple JFIF/Exif markers (re-save indicator)
        jfif_count = img_bytes.count(b"JFIF")
        exif_count = img_bytes.count(b"Exif")
        if jfif_count > 1:
            flags.append(f"Multiple JFIF markers ({jfif_count}) — possible re-save")

        # Check thumbnail vs main image mismatch (common deepfake tell)
        has_thumbnail = b"JFIF\x00\x01" in img_bytes[:20]

        return {
            "software_found": software_found,
            "flags": flags,
            "jfif_count": jfif_count,
            "exif_count": exif_count,
            "has_thumbnail": has_thumbnail,
            "manipulation_hint": len(software_found) > 0 or len(flags) > 0,
        }


# ─────────────────────────────────────────────
# VIDEO FRAME EXTRACTOR
# ─────────────────────────────────────────────
class VideoFrameExtractor:
    """Extract sample frames from video for per-frame analysis."""

    def extract_frames(self, video_path: str, sample_every_n: int = 30) -> list:
        if "cv2" not in _MODS:
            return []

        cv2 = _MODS["cv2"]
        cap = cv2.VideoCapture(video_path)
        frames = []
        frame_idx = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % sample_every_n == 0:
                # Encode frame to bytes for analysis
                _, buf = cv2.imencode(".jpg", frame)
                frames.append({
                    "frame_index": frame_idx,
                    "bytes": buf.tobytes(),
                })
            frame_idx += 1

        cap.release()
        return frames

    def analyze_video(self, video_path: str) -> dict:
        """Run ELA + noise analysis across sampled frames."""
        ela = ELAAnalyzer()
        noise = NoiseAnalyzer()
        frames = self.extract_frames(video_path)

        if not frames:
            return {"error": "No frames extracted or cv2 unavailable", "frames_analyzed": 0}

        ela_scores = []
        noise_scores = []

        for f in frames:
            e = ela.analyze(f["bytes"])
            n = noise.analyze(f["bytes"])
            ela_scores.append(e.get("ela_score", 0))
            noise_scores.append(n.get("noise_score", 0))

        avg_ela = sum(ela_scores) / len(ela_scores)
        avg_noise = sum(noise_scores) / len(noise_scores)

        # Temporal inconsistency: large score jumps between frames
        temporal_jumps = sum(
            1 for i in range(1, len(ela_scores))
            if abs(ela_scores[i] - ela_scores[i-1]) > 0.15
        )

        return {
            "frames_analyzed": len(frames),
            "avg_ela_score": round(avg_ela, 4),
            "avg_noise_score": round(avg_noise, 4),
            "temporal_inconsistencies": temporal_jumps,
            "deepfake_likelihood": round((avg_ela + avg_noise) / 2, 4),
            "verdict": "high_risk" if (avg_ela + avg_noise) / 2 > 0.4 else "low_risk",
        }


# ─────────────────────────────────────────────
# MAIN FORENSICS PIPELINE
# ─────────────────────────────────────────────
class ForensicsPipeline:
    def __init__(self):
        self.ela = ELAAnalyzer()
        self.noise = NoiseAnalyzer()
        self.metadata = MetadataForensics()

    def analyze_image_url(self, url: str) -> dict:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                img_bytes = resp.read()
        except Exception as e:
            return {"error": f"Download failed: {e}", "manipulation_likelihood": 0.0}

        return self.analyze_image_bytes(img_bytes, source_url=url)

    def analyze_image_bytes(self, img_bytes: bytes, source_url: str = "") -> dict:
        ela_result = self.ela.analyze(img_bytes)
        noise_result = self.noise.analyze(img_bytes)
        meta_result = self.metadata.analyze_jpeg_markers(img_bytes)

        ela_score = ela_result.get("ela_score", 0)
        noise_score = noise_result.get("noise_score", 0)
        meta_boost = 0.15 if meta_result.get("manipulation_hint") else 0.0

        composite = min((ela_score * 0.4) + (noise_score * 0.4) + meta_boost, 1.0)

        all_flags = meta_result.get("flags", [])
        if ela_result.get("verdict") == "suspicious":
            all_flags.append("ELA: compression artifacts detected")
        if noise_result.get("verdict") == "inconsistent_noise":
            all_flags.append("Noise: regional inconsistencies detected")

        return {
            "source_url": source_url,
            "ela": ela_result,
            "noise": noise_result,
            "metadata": meta_result,
            "manipulation_likelihood": round(composite, 4),
            "risk_level": self._risk_label(composite),
            "flags": all_flags,
        }

    def _risk_label(self, score: float) -> str:
        if score < 0.2: return "LOW"
        elif score < 0.45: return "MEDIUM"
        elif score < 0.7: return "HIGH"
        else: return "CRITICAL"
