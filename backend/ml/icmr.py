import json
from typing import Dict
from pathlib import Path

class ICMRTranslator:
    def __init__(self, rules_path: str = "data/icmr_rules.json"):
        # Load from disk or just define statically if missing
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, path: str) -> Dict:
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            # Fallback mock rules for the hackathon
            return {
                "dengue": {"paracetamol_500mg": 15, "iv_fluids_rl_500ml": 2},
                "malaria": {"artemether_lumefantrine": 6, "paracetamol_500mg": 10},
                "cholera": {"ors_sachets": 10, "azithromycin_500mg": 3},
                "type2_diabetes": {"metformin_500mg": 30, "glimepiride_2mg": 30}
            }

    def translate(
        self,
        disease: str,
        predicted_cases: int,
        severity_mix: dict = None
    ) -> Dict[str, float]:
        """
        Returns {drug_key: total_units_needed} over the forecast horizon.
        """
        if disease not in self.rules:
            return {}

        drug_needs = {}
        for drug_key, units_per_case in self.rules[disease].items():
            drug_needs[drug_key] = units_per_case * predicted_cases

        return drug_needs

translator = ICMRTranslator()
