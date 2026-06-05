import pickle
from pathlib import Path
import structlog

log = structlog.get_logger()

_artifact_cache = None

def load_anomaly_artifact(artifact_path="ml/artifacts/anomaly_detector.pkl"):
    global _artifact_cache
    if _artifact_cache is not None:
        return _artifact_cache
        
    path = Path(artifact_path)
    if not path.exists():
        log.warning("ml.anomaly.artifact_missing", path=str(path))
        return None
        
    try:
        with open(path, "rb") as f:
            artifact = pickle.load(f)
        _artifact_cache = {'model': artifact, 'type': 'anomaly'}
        log.info("ml.anomaly.loaded")
        return _artifact_cache
    except Exception as e:
        log.warning("ml.anomaly.load_failed", error=str(e), action="mocking_for_local_test")
        _artifact_cache = {'model': 'mocked_local_anomaly'}
        return _artifact_cache

def infer_anomaly(district_id: str, disease: str, predicted_cases: int) -> bool:
    artifact = load_anomaly_artifact()
    
    if not artifact:
        return False
        
    # Mock inference to verify routing
    variance = (hash(district_id + disease + "anomaly") % 100) / 100.0
    is_anomaly = variance > 0.8  # 20% chance of anomaly for demo purposes

    return is_anomaly
