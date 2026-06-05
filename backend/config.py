import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), extra='ignore')
    
    # Supabase
    supabase_url_a: str = ''
    supabase_service_role_key_a: str = ''
    supabase_db_url_a: str = ''
    
    supabase_url_b: str = ''
    supabase_service_role_key_b: str = ''
    
    # Redis
    redis_url: str = 'redis://localhost:6379'
    redis_max_connections: int = 20
    
    # Kafka
    kafka_bootstrap_servers: str = 'localhost:9092'
    kafka_api_key: Optional[str] = ''
    kafka_api_secret: Optional[str] = ''
    kafka_outbreak_topic: str = 'outbreak_events'
    kafka_consumer_group_po: str = 'pharmasense-po-generator'
    kafka_consumer_group_wa: str = 'pharmasense-whatsapp-notifier'
    
    # Model paths
    stgnn_model_path: str = 'ml/artifacts/stgnn_best.pt'
    gwn_model_path: str   = 'ml/artifacts/graphwavenet_best.pt'
    tft_model_path: str   = 'ml/artifacts/tft_best.ckpt'
    nbeats_model_path: str = 'ml/artifacts/nbeats_ncd_latest.pt'
    prophet_model_path: str = 'ml/artifacts/prophet_models.pkl'
    anomaly_model_path: str = 'ml/artifacts/anomaly_detector.pkl'
    lgbm_model_path: str = 'ml/artifacts/lgbm_demand.pkl'
    district_index_path: str = 'ml/data/district_index.json'
    icmr_rules_path: str = 'data/icmr_rules.json'
    disease_drug_map_path: str = 'data/seed/disease_drug_map.csv'
    
    # External APIs
    openweather_api_key: str
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    
    # Gateway
    supabase_jwt_secret_a: str
    
    # App
    app_env: str = 'development'
    log_level: str = 'INFO'

settings = Settings()
