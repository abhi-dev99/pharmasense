# ml/data — Pharmasense Training Datasets

These files are the authoritative training inputs for all 7 ML models.
They are loaded directly by Colab notebooks via GitHub raw URLs.

| File | Description | Rows | Source |
|---|---|---|---|
| malaria_2010_2024.csv | District-level annual malaria cases | 10,071 | NVBDCP Annual Reports + WHO API-derived 2017/18 |
| epiclim_clean.csv | Multi-disease weekly outbreaks with climate features | 8,985 | EpiClim IDSP (climate-imputed) |
| disease_drug_map.csv | Disease-to-drug treatment mapping | 23 | India National Treatment Guidelines (NVBDCP, DGHS, RNTCP, NPCDCS) |
| district_index.json | Spatial graph (641 nodes, 3482 edges) | — | Census 2011 GeoJSON adjacency |

Last updated: 2026-06-04
