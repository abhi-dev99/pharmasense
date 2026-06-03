"""
Pharmasense — Model Ensemble Combiner
Combines outputs of multiple models into final prediction + uncertainty bounds.
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class SpatialPrediction:
    """Output from ST-GNN or Graph WaveNet."""
    district_id: str
    disease: str
    predicted_cases: np.ndarray   # [horizon_weeks]
    model_name: str


@dataclass
class DemandPrediction:
    """Output from TFT or N-BEATS."""
    district_id: str
    condition: str
    demand_q10: np.ndarray        # 10th percentile (minimum expected)
    demand_q50: np.ndarray        # median (baseline)
    demand_q90: np.ndarray        # 90th percentile (procurement buffer)
    trend_component: Optional[np.ndarray]     # from N-BEATS decomposition
    seasonal_component: Optional[np.ndarray]  # from N-BEATS decomposition
    model_name: str


class SpatialEnsemble:
    """
    Combines ST-GNN and Graph WaveNet epidemic predictions.
    Uses inverse-variance weighting when validation errors are available,
    otherwise simple average (equal weights).

    Why ensemble: two models with different inductive biases.
    ST-GNN: fixed geographic adjacency as prior (stable, conservative)
    GWN:    learned transmission adjacency (adaptive, captures non-geographic spread)
    Average = variance reduction without additional training.
    """

    def __init__(self, stgnn_val_mae: float = 1.0, gwn_val_mae: float = 1.0):
        # Inverse-variance weighting: better model (lower MAE) gets higher weight
        total = 1.0/stgnn_val_mae + 1.0/gwn_val_mae
        self.w_stgnn = (1.0/stgnn_val_mae) / total
        self.w_gwn   = (1.0/gwn_val_mae) / total
        print(f'Spatial ensemble weights — ST-GNN: {self.w_stgnn:.3f}, GWN: {self.w_gwn:.3f}')

    def combine(self, stgnn_pred: SpatialPrediction,
                gwn_pred: SpatialPrediction) -> SpatialPrediction:
        """Weighted average of two spatial predictions."""
        combined = self.w_stgnn * stgnn_pred.predicted_cases + self.w_gwn * gwn_pred.predicted_cases
        return SpatialPrediction(
            district_id=stgnn_pred.district_id,
            disease=stgnn_pred.disease,
            predicted_cases=combined,
            model_name='ST-GNN+GWN_ensemble',
        )


class DemandEnsemble:
    """
    Combines TFT (all conditions) and N-BEATS (NCD-specific) demand predictions.
    For NCD conditions: averages TFT + N-BEATS.
    For communicable: uses TFT only (N-BEATS not trained on comm data).
    """

    NCD_CONDITIONS = {'hypertension', 'type2_diabetes', 'tuberculosis', 'anaemia'}

    def __init__(self, tft_val_loss: float = 1.0, nbeats_val_loss: float = 1.0):
        total = 1.0/tft_val_loss + 1.0/nbeats_val_loss
        self.w_tft    = (1.0/tft_val_loss) / total
        self.w_nbeats = (1.0/nbeats_val_loss) / total
        print(f'Demand ensemble weights — TFT: {self.w_tft:.3f}, N-BEATS: {self.w_nbeats:.3f}')

    def combine(self, tft_pred: DemandPrediction,
                nbeats_pred: Optional[DemandPrediction] = None) -> DemandPrediction:
        """Combine predictions. N-BEATS only used for NCD conditions."""
        if nbeats_pred is None or tft_pred.condition not in self.NCD_CONDITIONS:
            return tft_pred  # TFT-only for communicable diseases

        # NCD: weighted average
        q50 = self.w_tft * tft_pred.demand_q50 + self.w_nbeats * nbeats_pred.demand_q50
        q10 = self.w_tft * tft_pred.demand_q10 + self.w_nbeats * (nbeats_pred.demand_q50 * 0.7)
        q90 = self.w_tft * tft_pred.demand_q90 + self.w_nbeats * (nbeats_pred.demand_q50 * 1.3)

        return DemandPrediction(
            district_id=tft_pred.district_id,
            condition=tft_pred.condition,
            demand_q10=q10, demand_q50=q50, demand_q90=q90,
            trend_component=nbeats_pred.trend_component,     # keep N-BEATS decomposition
            seasonal_component=nbeats_pred.seasonal_component,
            model_name='TFT+N-BEATS_ensemble',
        )


def epidemic_to_demand_signal(spatial_pred: SpatialPrediction,
                               icmr_rules: Dict) -> Dict[str, np.ndarray]:
    """
    Convert epidemic case predictions to drug demand.
    Uses ICMR Standard Treatment Workflows.

    Args:
        spatial_pred: combined ST-GNN + GWN prediction (case counts per week)
        icmr_rules:   ICMR rules dict {disease: {drug_id: units_per_case}}

    Returns:
        {drug_id: additional_demand_units_per_week [horizon]}
    """
    disease = spatial_pred.disease
    if disease not in icmr_rules:
        return {}

    drug_demands = {}
    for drug_id, units_per_case in icmr_rules[disease].items():
        drug_demands[drug_id] = spatial_pred.predicted_cases * units_per_case

    return drug_demands
