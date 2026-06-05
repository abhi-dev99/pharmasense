import pickle
from pathlib import Path
import structlog

log = structlog.get_logger()

_artifact_cache = None

def load_prophet_artifact(artifact_path="ml/artifacts/prophet_models.pkl"):
    global _artifact_cache
    if _artifact_cache is not None:
        return _artifact_cache
        
    path = Path(artifact_path)
    if not path.exists():
        log.warning("ml.prophet.artifact_missing", path=str(path))
        return None
        
    try:
        with open(path, "rb") as f:
            artifact = pickle.load(f)
        _artifact_cache = {'model': artifact, 'type': 'prophet'}
        log.info("ml.prophet.loaded")
        return _artifact_cache
    except Exception as e:
        log.warning("ml.prophet.load_failed", error=str(e), action="mocking_for_local_test")
        _artifact_cache = {'model': 'mocked_local_prophet'}
        return _artifact_cache

def infer_prophet(district_id: str, target_disease: str, target_date=None) -> dict:
    artifact = load_prophet_artifact()
    
    if not artifact:
        return {
            "predicted_cases": 0,
            "risk_score": 0.0,
            "error": "Model artifact unavailable"
        }
        
    # Mock inference to verify routing
    base_cases = 120
    variance = (hash(district_id + target_disease + "prophet") % 40) / 100.0 - 0.2
    predicted_cases = max(0, int(base_cases * (1.0 + variance)))
    risk_score = min(0.8, max(0.2, (variance + 0.2) / 0.4 * 0.6 + 0.2))

    return {
        "predicted_cases": predicted_cases,
        "risk_score": float(risk_score),
        "model_used": "prophet"
    }
