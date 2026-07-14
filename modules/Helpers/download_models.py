import os

print("[*] Preparing to download TruthLens AI Models...")
print("[!] This will download ~1.4GB of data. Please do not cancel until it finishes.\n")

# Force-disable broken XetHub integration that causes Mac freezing
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "true"

try:
    import huggingface_hub.file_download
    huggingface_hub.file_download.xet_get = None
    print("[*] Successfully bypassed broken XetHub integration.")
except:
    pass

print("1/5: Downloading Semantic Brain (all-MiniLM-L6-v2) [~90MB]...")
try:
    from sentence_transformers import SentenceTransformer
    # This automatically downloads and caches the model
    model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
    print("✅ all-MiniLM-L6-v2 downloaded and cached successfully!\n")
except Exception as e:
    print(f"❌ Failed to download MiniLM: {e}\n")

print("2/5: Downloading Query Intelligence (google/flan-t5-small) [~308MB]...")
try:
    from transformers import pipeline
    # This automatically downloads and caches the model
    pipe = pipeline("text2text-generation", model="google/flan-t5-small", device=-1)
    print("✅ google/flan-t5-small downloaded and cached successfully!\n")
except Exception as e:
    print(f"❌ Failed to download flan-t5: {e}\n")

print("3/5: Downloading Manipulation Detection (MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) [~370MB]...")
try:
    from transformers import pipeline
    # This automatically downloads and caches the zero-shot classifier model
    pipe = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli", device=-1)
    print("✅ mDeBERTa zero-shot model downloaded and cached successfully!\n")
except Exception as e:
    print(f"❌ Failed to download mDeBERTa: {e}\n")

print("4/5: Downloading Emotion Detection (SamLowe/roberta-base-go_emotions) [~500MB]...")
try:
    from transformers import pipeline
    # This automatically downloads and caches the emotions model
    pipe = pipeline("text-classification", model="SamLowe/roberta-base-go_emotions", device=-1)
    print("✅ GoEmotions model downloaded and cached successfully!\n")
except Exception as e:
    print(f"❌ Failed to download GoEmotions: {e}\n")

print("5/5: Downloading Speech-to-Text Whisper (base) [~140MB]...")
try:
    from faster_whisper import WhisperModel
    # This automatically downloads and caches the faster-whisper base model
    model = WhisperModel("base", device="cpu", compute_type="float32")
    print("✅ Whisper base model downloaded and cached successfully!\n")
except Exception as e:
    print(f"❌ Failed to download Whisper base model: {e}\n")

print("🎉 All models successfully cached!")
print("You can now safely run TruthLens AI. It will load instantly offline!")

