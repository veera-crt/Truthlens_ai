import os
import json
import time
# pyrefly: ignore [missing-import]
import torch
import requests
import re
import pandas as pd
# pyrefly: ignore [missing-import]
from transformers import pipeline

try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    pass # Will handle gracefully if not installed

try:
    from modules.phase4_evidence.evidence import EvidenceRetrievalEngine
except ImportError:
    EvidenceRetrievalEngine = None

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "llama3.2" # Enterprise forensic extraction model

class AdaptiveTrustLearner:
    def __init__(self, data_path=None):
        if data_path is None:
            # Dynamically calculate the project root directory from this file's location
            _root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.data_path = os.path.join(_root_dir, "trust_training_data.csv")
        else:
            self.data_path = data_path
        self.model = None
        self.is_trained = False
        self._train_if_ready()

    def _train_if_ready(self):
        if not os.path.exists(self.data_path):
            return
            
        try:
            df = pd.read_csv(self.data_path)
            # Only use rows where label is 0 or 1
            labeled_df = df[df['label'].isin([0, 1, 0.0, 1.0, '0', '1'])]
            
            if len(labeled_df) >= 3:
                from sklearn.ensemble import RandomForestClassifier
                X = labeled_df[['misinformation', 'propaganda', 'fear', 'urgency', 'neutral']]
                y = labeled_df['label'].astype(int)
                self.model = RandomForestClassifier(n_estimators=10, random_state=42)
                self.model.fit(X, y)
                self.is_trained = True
                print(f"🧠 Adaptive Trust Engine: Trained on {len(labeled_df)} labeled instances.")
            else:
                print("🧠 Adaptive Trust Engine: Not enough labeled data (need >= 3). Using fallback formula.")
        except Exception as e:
            print(f"⚠️ Adaptive Trust Engine Error: {e}")

    def log_features(self, features):
        """Append features to CSV for future learning."""
        row = pd.DataFrame([{
            'misinformation': features.get('misinformation', 0.0),
            'propaganda': features.get('propaganda', 0.0),
            'fear': features.get('fear', 0.0),
            'urgency': features.get('urgency', 0.0),
            'neutral': features.get('neutral', 0.0),
            'label': '' # Unlabeled by default
        }])
        
        if not os.path.exists(self.data_path):
            row.to_csv(self.data_path, index=False)
        else:
            row.to_csv(self.data_path, mode='a', header=False, index=False)

    def predict_trust_index(self, features):
        """Predicts Trust Index 0-100 based on ML model, or falls back to static formula."""
        misinfo = features.get("misinformation", 0)
        propaganda = features.get("propaganda", 0)
        fear = features.get("fear", 0)
        urgency = features.get("urgency", 0)
        neutral = features.get("neutral", 0)
        
        if self.is_trained and self.model is not None:
            X_new = pd.DataFrame([[misinfo, propaganda, fear, urgency, neutral]], 
                                 columns=['misinformation', 'propaganda', 'fear', 'urgency', 'neutral'])
            # Predict probability of class 1 (Trustworthy)
            proba = self.model.predict_proba(X_new)[0]
            # Probabilities array might not have class 1 if training data only had 0s
            if len(self.model.classes_) == 2:
                trust_prob = proba[1]
            else:
                trust_prob = 1.0 if self.model.classes_[0] == 1 else 0.0
                
            return round(trust_prob * 100, 2)
        else:
            # Fallback Formula: Penalize fear and misinformation more heavily for realistic risk grading
            trust_index = 100 - (misinfo * 45) - (propaganda * 30) - (fear * 25) - (urgency * 15) + (neutral * 5)
            return round(max(0.0, min(100.0, trust_index)), 2)

class ForensicNLPEngine:
    def __init__(self):
        print("[*] Initializing TruthLens Forensic NLP Engine (Adaptive Upgrade)...")
        self.device = -1
        self.classifier = None
        self.emotion_classifier = None
        self.learner = AdaptiveTrustLearner()
        self._init_models()

    def _init_models(self):
        print("📥 Loading Manipulation Detection Model (mDeBERTa)...")
        self.classifier = pipeline(
            "zero-shot-classification",
            model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
            device=self.device
        )
        print("📥 Loading Emotion Detection Model (GoEmotions)...")
        self.emotion_classifier = pipeline(
            "text-classification",
            model="SamLowe/roberta-base-go_emotions",
            top_k=None,
            device=self.device
        )
        self.evidence_engine = None

    def _get_evidence_engine(self):
        """Lazy load the Evidence Engine so it doesn't block Flask startup."""
        if self.evidence_engine is None:
            if EvidenceRetrievalEngine is not None:
                self.evidence_engine = EvidenceRetrievalEngine()
        return self.evidence_engine

    def _chunk_text_by_words(self, text, chunk_size=200):
        words = text.split()
        return [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

    def _safe_extend(self, all_c, c):
        if isinstance(c, list):
            all_c.extend(c)
        elif isinstance(c, dict):
            has_nested_list = False
            for val in c.values():
                if isinstance(val, list):
                    all_c.extend(val)
                    has_nested_list = True
                    break
            if not has_nested_list:
                all_c.append(c)

    def _parse_claims_json(self, raw_out, source_name):
        raw_out = raw_out.strip()
        # Clean <think> tags from reasoning models if present
        if "<think>" in raw_out and "</think>" in raw_out:
            raw_out = raw_out.split("</think>")[-1].strip()
        if raw_out.startswith("```json"): raw_out = raw_out[7:]
        if raw_out.startswith("```"): raw_out = raw_out[3:]
        if raw_out.endswith("```"): raw_out = raw_out[:-3]
        raw_out = raw_out.strip()
        
        parsed = None
        # Try direct JSON parsing
        try:
            parsed = json.loads(raw_out)
        except Exception:
            # Try regex parsing for dict
            match_dict = re.search(r"\{.*\}", raw_out, re.DOTALL)
            if match_dict:
                try:
                    parsed = json.loads(match_dict.group(0))
                except Exception:
                    pass
            
            # Try regex parsing for list if dict failed
            if not parsed:
                match_list = re.search(r"\[.*\]", raw_out, re.DOTALL)
                if match_list:
                    try:
                        parsed = json.loads(match_list.group(0))
                    except Exception:
                        pass
                        
        if parsed is None:
            print(f"⚠️ {source_name} parser failed to decode JSON. Raw output: {raw_out[:200]}")
            return []
            
        # Extract claims from parsed structure
        claims = []
        if isinstance(parsed, dict):
            # Case-insensitive search for 'claims' key
            claims_key = next((k for k in parsed if k.lower() == 'claims'), None)
            if claims_key:
                claims = parsed[claims_key]
            else:
                # Fallback: if 'claims' is not present but there is a list value, use it
                for val in parsed.values():
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], (dict, str)):
                        claims = val
                        break
        elif isinstance(parsed, list):
            claims = parsed
            
        # Ensure claims is a list
        if not isinstance(claims, list):
            claims = [claims] if claims else []
            
        print(f"✅ {source_name} parser success: Extracted {len(claims)} claims.")
        return claims

    def _extract_claims_with_gemini(self, chunk):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("⚠️ Error: GEMINI_API_KEY not found in environment. Please add it to your .env file.")
            return []
            
        prompt = f"""
You are a strict forensic NLP system.
Your job is to act as a structured reasoning engine, operating in 3 steps:

Step 1: CONTEXT COMPREHENSION.
Read the entire text and understand the overall concept, theme, main entities, and general topic of the video content.

Step 2: CORE CONCEPT MAPPING.
Identify the primary concepts, arguments, or assertions made in the text. Map out who is saying what, identifying specific people, organizations, places, or dates.

Step 3: SPECIFIC CLAIM EXTRACTION & RESOLUTION.
For each concept, extract ONLY highly specific, verifiable factual claims.
- Rule A (Strict Specificity): Avoid vague or random claims with unresolved pronouns (like "he did this", "she said that", "it happened"). Resolve all pronouns to their actual entities based on the context (e.g. "Dr. Trisha Pas states pooping wrong causes issues" instead of "She says pooping wrong causes issues").
- Rule B (Fact-Check Readiness): Every claim must be an independent, self-contained atomic fact that contains all necessary names, entities, and context so it can be verified standalone by a search engine.
- Rule C (Filter Fluff): Completely ignore greetings, personal opinions, rhetorical questions, subjective arguments, slogans, and narrative filler.
- Assign a strict VERIFIABILITY SCORE:
   - HIGH: Specific numbers, historical dates, statistics, official policies, or concrete events.
   - MEDIUM: Specific policy statements, planned public events, or verifiable promises.
   - LOW: Rhetorical narrative, subjective feelings, slogans.
- For HIGH and MEDIUM claims, generate a clean, entity-focused `search_query` (e.g. "Dr. Trisha Pas author you have been pooping all wrong" or "Vijay public meeting date Chennai"). For LOW claims, leave it empty.

You MUST return ONLY a valid JSON object matching this exact format. No explanations. No markdown.

FORMAT STRICTLY:
{{
  "themes": ["theme 1", "theme 2"],
  "claims": [
    {{"type":"[statistic/event/policy/statement]", "verifiability_score":"[HIGH/MEDIUM/LOW]", "text":"[The atomic factual claim]", "search_query":"[keywords for fact checking]"}}
  ]
}}

If there are no factual claims, output {{"themes": [], "claims": []}}.

TEXT:
{chunk}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1}
        }
        
        max_retries = 3
        backoff = 1.5  # seconds
        success = False
        raw_out = ""
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=30)
                if response.status_code == 429:
                    print(f"⚠️ Gemini API rate limited (429). Retrying in {backoff}s... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                response.raise_for_status()
                data = response.json()
                raw_out = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                success = True
                break
            except Exception as e:
                print(f"⚠️ Gemini request attempt {attempt+1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    last_error = e

        if success:
            return self._parse_claims_json(raw_out, "Gemini")
            
        print(f"⚠️ Gemini API failed completely after {max_retries} attempts.")
        print("🔄 Falling back to Groq API (llama-3.3-70b)...")
        try:
            groq_key = os.environ.get("GROQ_API_KEY")
            if not groq_key:
                raise Exception("Missing GROQ_API_KEY in .env")

            groq_url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {groq_key}"
            }
            payload_groq = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a strict forensic NLP system."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.1
            }
            resp = requests.post(groq_url, headers=headers, json=payload_groq, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            raw_out_groq = data["choices"][0]["message"]["content"]
            print("✅ Groq extraction success")
            return self._parse_claims_json(raw_out_groq, "Groq")
        except Exception as ex:
            print(f"⚠️ Groq fallback failed: {ex}")
            print("🔄 Falling back to Local Ollama API (deepseek-r1:7b)...")
            try:
                ollama_url = "http://127.0.0.1:11434/api/generate"
                payload_ollama = {
                    "model": "deepseek-r1:7b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1
                    }
                }
                resp = requests.post(ollama_url, json=payload_ollama, timeout=600)
                resp.raise_for_status()
                data = resp.json()
                raw_out_ollama = data.get("response", "")
                return self._parse_claims_json(raw_out_ollama, "Ollama")
            except Exception as ollama_ex:
                print(f"🚨 Error with Ollama DeepSeek fallback: {ollama_ex}")
                return []

    def analyze_full_spectrum(self, text, url=None, title=None):
        if text and "FetchedTranscriptSnippet" in text:
            # Clean up direct API snippet wrappers if present
            text = re.sub(r"FetchedTranscriptSnippet\(text=(['\"])(.*?)\1,\s*start=.*?,?\s*duration=.*?\)", r"\2", text)
            text = re.sub(r"FetchedTranscriptSnippet\(text=(['\"])(.*?)\1,.*?\)", r"\2", text)
            
        print("🤖 Extracting forensic claims with Gemini AI...")
        chunks = self._chunk_text_by_words(text, chunk_size=200)
        
        all_claims = []
        for chunk in chunks:
            claims = self._extract_claims_with_gemini(chunk)
            self._safe_extend(all_claims, claims)
            
        labels = ["propaganda", "conspiracy", "fear", "misinformation", "neutral"]
        
        graph_ready_nodes = []
        total_misinfo, total_propaganda, total_fear, total_neutral, total_urgency = 0, 0, 0, 0, 0
        
        red_flags = []
        detected_claims_text = []
        seen_claims = set()
        
        for item in all_claims:
            if isinstance(item, str):
                item = {"type": "UNKNOWN", "verifiability_score": "MEDIUM", "text": item}
            elif not isinstance(item, dict):
                continue
                
            claim_text = str(item.get("text") or item.get("claim") or item.get("claim_text") or item.get("claim_content") or item.get("fact") or item.get("atomic_fact") or "").strip()
            claim_type = str(item.get("type") or item.get("claim_type") or "UNKNOWN")
            verifiability = str(item.get("verifiability_score") or item.get("verifiability") or "MEDIUM").upper()
            
            if isinstance(claim_type, str) and len(claim_type) > 20 and len(claim_text) < 20:
                claim_text, claim_type = claim_text, claim_type
                
            claim_type = str(claim_type).upper()
            if not claim_text: continue
            
            # 1. Noise Filter: Skip single words or tiny fragments (3 words minimum globally)
            if len(claim_text.split()) < 3:
                continue
            
            # 2. Deduplication Layer
            if claim_text in seen_claims:
                continue
            seen_claims.add(claim_text)
            
            # NEW: Claim Gate - skip vague or un-verifiable opinions
            if verifiability == "LOW" and claim_type != "URGENCY":
                continue
            
            res_manip = self.classifier(claim_text, labels, multi_label=True)
            scores_map = {lbl: score for lbl, score in zip(res_manip["labels"], res_manip["scores"])}
            
            res_emo = self.emotion_classifier(claim_text)[0]
            top_emotions = {emo["label"]: emo["score"] for emo in res_emo if emo["score"] > 0.05}
            
            node_risk = (scores_map.get("misinformation", 0) * 0.4 + 
                         scores_map.get("propaganda", 0) * 0.3 + 
                         scores_map.get("fear", 0) * 0.3)
                         
            is_urgent = 1.0 if claim_type == "URGENCY" else 0.0
            
            total_misinfo += scores_map.get("misinformation", 0)
            total_propaganda += scores_map.get("propaganda", 0)
            total_fear += scores_map.get("fear", 0)
            total_neutral += scores_map.get("neutral", 0)
            total_urgency += is_urgent
            
            if is_urgent > 0 or scores_map.get("propaganda", 0) > 0.6:
                red_flags.append(claim_text)
                
            detected_claims_text.append(claim_text)
            
            node = {
                "text": claim_text,
                "type": claim_type,
                "embedding": None,
                "score": round(node_risk, 4),
                "semantic_features": {k: round(v, 4) for k, v in scores_map.items()},
                "emotions": {k: round(v, 4) for k, v in top_emotions.items()}
            }
            
            # ── EVIDENCE RETRIEVAL FACT CHECK ──
            evidence_engine = self._get_evidence_engine()
            if evidence_engine is not None and claim_type not in ["FEAR", "URGENCY", "EMOTIONAL"]:
                # Use the Gemini-generated search query if available
                search_query = item.get("search_query", claim_text)
                fact = evidence_engine.verify_claim(claim_text, search_query)
                node["evidence_confidence"] = fact.get("evidence_confidence", 0.0)
                node["supporting_source"] = fact.get("supporting_source", {})
                node["evidence_text"] = fact.get("evidence_text", "")
                
                # ── TRUTHLENS V3: CONTRADICTION ENGINE (NLI) ──
                raw_evidence = fact.get("evidence_text", "")
                if raw_evidence and node["evidence_confidence"] > 0:
                    # Compression Layer: top 3 sentences only to prevent noise
                    compressed_evidence = ". ".join(raw_evidence.split(".")[:3]) + "."
                    
                    # 3-way NLI Reasoning (Pure Premise-Hypothesis inference)
                    inputs = self.classifier.tokenizer(
                        compressed_evidence, 
                        claim_text, 
                        return_tensors="pt", 
                        truncation=True, 
                        max_length=512
                    ).to(self.device if self.device != -1 else "cpu")
                    
                    # pyrefly: ignore [missing-import]
                    import torch
                    with torch.no_grad():
                        logits = self.classifier.model(**inputs).logits
                    probs = logits.softmax(dim=-1)[0]
                    id2label = self.classifier.model.config.id2label
                    nli_scores = {id2label[i].lower(): p.item() for i, p in enumerate(probs)}
                    
                    support = nli_scores.get("entailment", 0.0)
                    contradict = nli_scores.get("contradiction", 0.0)
                    uncertain = nli_scores.get("neutral", 0.0)
                    
                    # Verdict Generation
                    if contradict > support and contradict > 0.4:
                        verdict = "⚠ Contradicted by external evidence"
                    elif support > 0.5:
                        verdict = "✔ Supported by available evidence"
                    else:
                        verdict = "⚠ Insufficient conclusive evidence"
                        
                    node["nli"] = {
                        "support": round(support, 2),
                        "contradict": round(contradict, 2),
                        "uncertain": round(uncertain, 2),
                        "verdict": verdict
                    }
                else:
                    node["nli"] = None
            else:
                node["evidence_confidence"] = 0.0
                node["evidence_text"] = ""
                node["supporting_source"] = {"source": "#", "title": "No Factual Claim Detected"}
                node["nli"] = None

            graph_ready_nodes.append(node)

        num_claims = max(1, len(graph_ready_nodes))
        
        features = {
            "misinformation": total_misinfo / num_claims,
            "propaganda": total_propaganda / num_claims,
            "fear": total_fear / num_claims,
            "urgency": total_urgency / num_claims,
            "neutral": total_neutral / num_claims
        }
        
        # Log to CSV for learning
        self.learner.log_features(features)
        
        # Adaptive Trust Score
        trust_index = self.learner.predict_trust_index(features)
        
        # Virality Score
        propaganda_density = sum(1 for n in graph_ready_nodes if n["type"] == "PROPAGANDA SIGNAL") / num_claims
        repetition_factor = (features["urgency"] * 10) + (propaganda_density * 10)
        virality_score = (features["urgency"] * 100) + (features["fear"] * 100) + (features["misinformation"] * 100) + (features["propaganda"] * 100) + repetition_factor
        virality_score = min(100.0, virality_score / 4.0)
        
        # Calculate Average Evidence Confidence for Phase 6 Fusion
        total_evidence_conf = 0.0
        factual_claims = 0
        for n in graph_ready_nodes:
            if "evidence_confidence" in n and n.get("type") not in ["FEAR", "URGENCY", "EMOTIONAL"]:
                total_evidence_conf += n["evidence_confidence"]
                factual_claims += 1
                
        avg_evidence_confidence = (total_evidence_conf / factual_claims) if factual_claims > 0 else 1.0 # 1.0 trust if no claims
        
        # Determine risk level string
        risk_level = "LOW"
        if trust_index < 40: risk_level = "HIGH"
        elif trust_index < 70: risk_level = "MODERATE"
        
        return {
            "manipulation_score": round((100 - trust_index) / 100, 2), # Inverted UI bar mapping
            "trust_index": trust_index,
            "avg_evidence_confidence": round(avg_evidence_confidence, 4),
            "virality_score": round(virality_score, 2),
            "risk_level": risk_level,
            "detected_claims": detected_claims_text,
            "red_flags": red_flags,
            "claim_analysis": graph_ready_nodes,
            "sentiment": {"pos": features["neutral"], "neg": features["fear"], "neu": features["neutral"]}, # Rough map for UI
            "tone": "Urgent" if features["urgency"] > 0.5 else "Neutral",
            "top_keywords": ["urgency", "propaganda"] if propaganda_density > 0.3 else [],
            "caps_ratio": 0.0,
            "triggered_cues": red_flags
        }
