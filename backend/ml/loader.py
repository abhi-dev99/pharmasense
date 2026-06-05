"""
Singleton model registry. Loads all artifacts at startup.
Exposes is_ready(model_name) for health checks.
Falls back gracefully when artifacts are missing.
"""
import structlog
from backend.config import settings

log = structlog.get_logger()

class ModelRegistry:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        self._models: dict = {}
        self._ready: dict[str, bool] = {}
        self._initialized = True
    
    def load_all(self):
        log.info("ml.registry.loading_artifacts")
        # In a real environment, we'd use torch.load, joblib, etc. here.
        # Since this is a hackathon where some massive weights might be missing locally, 
        # we catch exceptions and mark them as not ready so Prophet fallback can kick in.
        self._load_stgnn()
        self._load_graphwavenet()
        self._load_tft()          
        self._load_nbeats()
        self._load_prophet()
        self._load_anomaly()
        self._load_lgbm()
    
    def _load_stgnn(self):
        try:
            # mock loading for now
            self._models['stgnn'] = {"type": "stgnn", "status": "loaded"}
            self._ready['stgnn'] = True
        except Exception as e:
            self._ready['stgnn'] = False
            log.warning("ml.registry.stgnn.missing", error=str(e))

    def _load_graphwavenet(self):
        try:
            from backend.ml.graphwavenet import load_gwn_artifact
            artifact = load_gwn_artifact()
            if artifact is not None:
                self._models['graphwavenet'] = {"type": "graphwavenet", "status": "loaded"}
                self._ready['graphwavenet'] = True
            else:
                self._ready['graphwavenet'] = False
        except Exception as e:
            self._ready['graphwavenet'] = False
            log.warning("ml.registry.graphwavenet.missing", error=str(e))

    def _load_tft(self):
        try:
            from backend.ml.tft import load_tft_artifact
            artifact = load_tft_artifact()
            if artifact is not None:
                self._models['tft'] = {"type": "tft", "status": "loaded"}
                self._ready['tft'] = True
            else:
                self._ready['tft'] = False
        except Exception as e:
            self._ready['tft'] = False
            log.warning("ml.registry.tft.missing", error=str(e))

    def _load_nbeats(self):
        try:
            from backend.ml.nbeats import load_nbeats_artifact
            artifact = load_nbeats_artifact()
            if artifact is not None:
                self._models['nbeats'] = {"type": "nbeats", "status": "loaded"}
                self._ready['nbeats'] = True
            else:
                self._ready['nbeats'] = False
        except Exception as e:
            self._ready['nbeats'] = False
            log.warning("ml.registry.nbeats.missing", error=str(e))

    def _load_prophet(self):
        try:
            from backend.ml.prophet import load_prophet_artifact
            artifact = load_prophet_artifact()
            if artifact is not None:
                self._models['prophet'] = {"type": "prophet", "status": "loaded"}
                self._ready['prophet'] = True
            else:
                self._ready['prophet'] = False
        except Exception as e:
            self._ready['prophet'] = False
            log.warning("ml.registry.prophet.missing", error=str(e))

    def _load_anomaly(self):
        try:
            from backend.ml.anomaly import load_anomaly_artifact
            artifact = load_anomaly_artifact()
            if artifact is not None:
                self._models['anomaly'] = {"type": "anomaly", "status": "loaded"}
                self._ready['anomaly'] = True
            else:
                self._ready['anomaly'] = False
        except Exception as e:
            self._ready['anomaly'] = False
            log.warning("ml.registry.anomaly.missing", error=str(e))
        
    def _load_lgbm(self):
        try:
            from backend.ml.lgbm import load_lgbm_artifact
            artifact = load_lgbm_artifact()
            if artifact is not None:
                self._models['lgbm'] = {"type": "lgbm", "status": "loaded"}
                self._ready['lgbm'] = True
            else:
                self._ready['lgbm'] = False
        except Exception as e:
            self._ready['lgbm'] = False
            log.warning("ml.registry.lgbm.missing", error=str(e))

    def is_ready(self, name: str) -> bool:
        return self._ready.get(name, False)
    
    def get(self, name: str):
        return self._models.get(name)
    
    @property
    def health_map(self) -> dict[str, bool]:
        return dict(self._ready)

# Global singleton
registry = ModelRegistry()
