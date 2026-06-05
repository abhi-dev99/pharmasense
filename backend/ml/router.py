from enum import Enum

COMMUNICABLE = {'dengue', 'malaria', 'cholera', 'acute_diarrhoeal_disease'}
NCD = {'hypertension', 'type2_diabetes', 'tuberculosis', 'anaemia',
       'viral_fever_urti', 'acute_gastritis_dyspepsia', 'musculoskeletal_pain',
       'asthma_copd_respiratory', 'helminth_infestation',
       'uti_bacterial_infections', 'maternal_anc_supplements'}

class InferenceStrategy(Enum):
    SPATIAL_ENSEMBLE  = 'spatial'    # ST-GNN + GWN → communicable
    DEMAND_ENSEMBLE   = 'demand'     # TFT + N-BEATS → NCD
    PROPHET_FALLBACK  = 'prophet'    # when PT models not loaded
    ANOMALY_ONLY      = 'anomaly'    # supplement to spatial

def route(disease: str, registry) -> InferenceStrategy:
    """
    Decides which model strategy to use based on disease type and currently loaded models.
    """
    if disease in COMMUNICABLE:
        if registry.is_ready('stgnn') or registry.is_ready('graphwavenet'):
            return InferenceStrategy.SPATIAL_ENSEMBLE
        return InferenceStrategy.PROPHET_FALLBACK
        
    if disease in NCD:
        if registry.is_ready('tft') or registry.is_ready('nbeats'):
            return InferenceStrategy.DEMAND_ENSEMBLE
        return InferenceStrategy.PROPHET_FALLBACK
        
    return InferenceStrategy.PROPHET_FALLBACK
