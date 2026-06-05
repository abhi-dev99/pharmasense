# AgTechathon-Med: Predictive Epidemiological Supply Chain (AGTech45-CE01-2)
## Complete Requirements Analysis & Market Landscape

This document scopes out the exact requirements needed to adapt your existing `AgTechathon` architecture into an **unbeatable** predictive drug inventory system for the 24-hour hackathon. 

---

## 1. Executive Summary
Standard drug inventory systems track what has already been sold. **AgTechathon-Med** predicts what *will be needed* before the demand exists. By correlating external environmental stress markers (weather, search trends, local news) with existing hospital inventory, the system models the geographical spread of diseases (e.g., Dengue, Malaria, viral flu) and automatically generates preemptive restock orders. 

* **The Vision**: Prevent medical supply chain collapse in Tier-2 and rural sectors by acting proactively rather than reactively.
* **The "Hackathon Wow Factor"**: A glowing 3D Mapbox/Deck.gl visualization plotting disease risk heatmaps overlapping with pharmacy inventory statuses, accompanied by AI-generated "Restock Briefing" documents.

---

## 2. Market Landscape & Competitor Analysis
We must know the market to prove to the judges that this isn't just a toy, but a commercially viable product. I scoured the enterprise space. Here is who is doing this, and how you beat them:

| Competitor | Core Offering | Weakness / Where You Win |
|---|---|---|
| **Macro-Eyes (Sibyl)** | AI predicting vaccine demand and health supply chains. Used in Africa / global health. | Highly proprietary, relies heavily on government-level data integration. You win on localized, open-source signal fusion (Weather + Google Trends). |
| **TraceLink (Opus)** | The global standard for pharma "Track and Trace" & serialization. | Focuses purely on compliance (DSCSA). It tells you *where* a drug is, but doesn't predict *why* you will need it next week. |
| **Controlant** | IoT cold-chain monitoring (used for Pfizer COVID vaccines). | Heavily hardware-reliant. Doesn't do predictive epidemiological modeling. |
| **Blue Yonder / Kinaxis** | Giant enterprise SaaS supply chain planning. | Slower, generic, requires massive historical ERP data to function. Useless for rapid deployments in rural grids. |
| **Palantir Foundry (Health)**| Ultimate big-data routing used by NHS and CDC. | Multi-million dollar barrier to entry. Over-engineered for local clinics. |

**Your Unique Selling Proposition (USP)**:
Competitors need 5 years of clean SQL data to predict trends. Your system uses **Public Alternative Data** (Weather APIs + Search Trends) via your existing `AgTechathon` signal-fusion engine, making it deployable instantly for regions with zero historical medical records.

---

## 3. Functional Requirements (FR)
What the prototype *must* do during the 24-hour hackathon to secure the win:

* **FR-1: Geospatial UI (The Command Center)**
  * An interactive 3D map interface plotting hospitals/pharmacies as nodes.
  * Nodes must glow different colors based on "Risk Status" (Green = Optimal, Yellow = Impending Surge, Red = Critical Stockout Danger).
* **FR-2: Multimodal Signal Fusion (The Engine)**
  * **Signal A:** Internal Inventory levels (Simulated synthetic SQL/CSV data of Paracetamol, Antimalarials).
  * **Signal B:** Hyper-local Weather (OpenWeatherMap API -> triggering alerts if high rain & humidity indicate mosquito breeding).
  * **Signal C:** Societal symptom searches (Static mocked data representing Google Trends spikes for "fever" or "cough").
* **FR-3: Predictive Risk Profiling**
  * The backend must cross-reference Signal A against B & C to flag locations. If a node is in a heavy rain zone with rising fever searches, and Paracetamol supply is < 30 days, the node is flagged red.
* **FR-4: LLM-Generated "Hospital Briefs"**
  * Clicking a node generates a dynamic Markdown/PDF brief using an LLM API (OpenAI/Anthropic). 
  * *Example output*: "URGENT: 85% probability of Dengue surge in District X next week due to 40mm rainfall average. Current IV fluid stock will deplete in 4 days. Recommended Order: 5,000 units."

---

## 4. Non-Functional Requirements (NFR)
* **NFR-1: Simulated Real-Time Feasibility**: The architecture must simulate a distributed system, handling asynchronous updates so the UI visually updates without refreshing. 
* **NFR-2: Aesthetics First**: The React dashboard must be dark-themed, futuristic, and lag-free, serving as the anchor of the 3-minute pitch. (Judges buy with their eyes).
* **NFR-3: Pitch Interactivity**: Provide a button on the UI that lets a judge "Simulate a Monsoon Surge," instantly turning the map red and triggering the AI reports. 

---

## 5. Technical Stack (Leveraging `AgTechathon` repo)

* **Frontend**: React.js + Deck.GL / Mapbox GL JS *(You already matched this in `AgTechathon`)*. TailwindCSS for futuristic styling.
* **Backend**: Python FastAPI. It is lightweight, async, and handles your data tasks quickly.
* **Data Processing**: Pandas / Geopandas for aligning zip codes/districts. 
* **AI/Intelligence**: 
  * Time-Series Mocking: `scikit-learn` or custom algorithmic math to simulate the demand curve.
  * Brief Generation: Hook into OpenAI `gpt-4o-mini` API (with templated prompts) to dynamically write the hospital briefings.
* **Database**: SQLite or simply static JSON/CSV files running locally for speed *(Hackathons don't require heavy DB setups unless explicitly asked)*.

---

## 6. The 24-Hour Hackathon Execution Roadmap (Do or Die)

* **Hour 0-2 (Setup & Scripts)**: Clone `AgTechathon`. Strip all references to "Retail/Williams-Sonoma". Rename variables to `pharmacy_id`, `drug_sku`, `vulnerability_score`.
* **Hour 2-6 (Synthetic Data)**: Write a quick Python script to generate 3 CSVs: `pharmacies.csv` (lat/long points), `inventory.csv` (stock levels), `weather_trends.csv` (mocked anomaly markers).
* **Hour 6-12 (Backend Logic)**: Modify your signal fusion code. If `weather_score` > `0.8` AND `inventory_stock` < `100`, then `status` = `"CRITICAL"`. Export to an API endpoint.
* **Hour 12-18 (Frontend Polish)**: Connect the Map UI to the new API. Ensure the Mapbox pins reflect the danger status. Code the "Generate AI Report" button.
* **Hour 18-20 (Pitch Integration)**: Build the "Simulate Disaster" toggle. Make sure the transition looks beautiful for the judges. 
* **Hour 20-24 (The Narrative)**: Rehearse the pitch. Stop writing code. The code only exists to serve the presentation. 
