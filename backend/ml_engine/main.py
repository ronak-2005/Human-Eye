"""
HumanEye ML Engine — PLACEHOLDER
Replace this entire folder with the real ML engine when delivered.
This stub returns realistic scores so the backend can be tested end-to-end.
Satisfies the exact health contract the backend checks (phase1_ready, phase2_ready).
"""
from fastapi import FastAPI

app = FastAPI(title="HumanEye ML Engine (placeholder)", version="0.1.0-stub")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "phase1_ready": True,    # stub always reports ready
        "phase2_ready": False,   # Phase 2 not implemented yet
        "models_loaded": ["behavioral_stub", "text_stub"],
        "gpu_available": False,
        "note": "placeholder — replace with real ML engine",
    }


@app.get("/models")
def models():
    return {
        "loaded_models": ["behavioral_stub", "text_stub"],
        "versions": {"behavioral_stub": "0.1.0", "text_stub": "0.1.0"},
        "last_trained": None,
    }


@app.post("/analyze")
def analyze(data: dict):
    """
    Stub Phase 1 response. Returns realistic-looking scores.
    action_type in context influences stub weights.
    """
    context     = data.get("context", {})
    action_type = context.get("action_type", "generic")
    keystrokes  = data.get("signals", {}).get("keystrokes", [])
    text        = data.get("signals", {}).get("text_content")

    behavioral = 0.82 if keystrokes else None
    text_score = 0.78 if text       else None

    scores = [s for s in [behavioral, text_score] if s is not None]
    combined = sum(scores) / len(scores) if scores else 0.75

    return {
        "human_trust_score":  int(round(combined * 100)),
        "combined_score":     round(combined, 4),
        "behavioral_score":   behavioral,
        "text_score":         text_score,
        "flags":              [],
        "signal_scores":      {"keystroke": behavioral, "text": text_score},
        "confidence":         "high" if len(scores) >= 2 else "medium",
        "processing_time_ms": 42,
        "signals_analyzed":   (["keystroke"] if keystrokes else []) + (["text"] if text else []),
    }


@app.post("/analyze/face")
def analyze_face(data: dict):
    """Phase 2 stub."""
    return {
        "liveness_score":       0.95,
        "deepfake_probability": 0.03,
        "skin_physics_pass":    None,
        "rppg_bpm":             None,
        "asymmetry_score":      None,
        "flags":                [],
        "phase":                "stub_phase2",
    }


@app.post("/analyze/voice")
def analyze_voice(data: dict):
    """Phase 2 stub."""
    return {
        "clone_probability": 0.02,
        "jitter_score":      None,
        "shimmer_score":     None,
        "breathing_natural": None,
        "flags":             [],
        "phase":             "stub_phase2",
    }
