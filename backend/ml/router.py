from enum import Enum

COMMUNICABLE = {'dengue', 'malaria', 'cholera', 'acute_diarrhoeal_disease'}
NCD = {'hypertension', 'type2_diabetes', 'tuberculosis', 'anaemia',
       'viral_fever_urti', 'acute_gastritis_dyspepsia', 'musculoskeletal_pain',
       'asthma_copd_respiratory', 'helminth_infestation',
       'uti_bacterial_infections', 'maternal_anc_supplements'}

class InferenceStrategy(Enum):
    SPATIAL_ENSEMBLE  = 'spatial'    # ST-GNN + GWN → communicable
    DEMAND_ENSEMBLE   = 'demand'     # TFT + N-BEATS → NCD
    ANOMALY_ONLY      = 'anomaly'    # supplement to spatial

def route(disease: str, registry) -> InferenceStrategy:
    """
    Decides which model strategy to use based on disease type.
    """
    if disease in COMMUNICABLE:
        return InferenceStrategy.SPATIAL_ENSEMBLE
        
    if disease in NCD:
        return InferenceStrategy.DEMAND_ENSEMBLE
        
    # Default to demand ensemble if unclassified
    return InferenceStrategy.DEMAND_ENSEMBLE
