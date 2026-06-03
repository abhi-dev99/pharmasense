# AgTechathon: Supplite-Med Production Blueprint & Architecture
We are abandoning the "we only have 24 hours" crutch. To win—and to build a genuine, marketable product—we are treating this as an enterprise-grade startup launch. The architecture below is expansive, commercially viable, and built for scale.

This blueprint establishes the **Unique Selling Proposition (USP)**, the **India-compliant data strategy**, an **upgraded cloud-native tech stack**, and the **production deployment pipeline**.

---

## 1. The Core USP & Innovative Features
If we want to impress the judges as a legitimate SaaS product, we need features that go beyond a basic dashboard. 

* **The Ultimate USP**: Shifting the healthcare supply chain from *Reactive* (restocking when shelves are empty) to *Predictive* (restocking 14 days before a localized outbreak hits) by fusing non-clinical alternative data (weather + search trends).
* **Innovation 1: Automated Inter-Hospital Stock Balancing**: Instead of just ordering *new* stock, the AI detects if Hospital A (Mumbai South) has excess stock while Hospital B (Mumbai North) is about to face a surge, and suggests a lateral stock transfer.
* **Innovation 2: "Zero-Click" WhatsApp Approvals**: Integrating Twilio/WhatsApp Business APIs. The system doesn't just show a dashboard; it texts the head pharmacist: *"Dengue surge predicted in Pune. Paracetamol stock is low. Reply 'YES' to auto-generate a supplier purchase order."*
* **Innovation 3: Multi-Tiered Access (B2B SaaS)**: Different views for State Health Ministers (Macro-level 3D maps) vs. Local Pharmacy Managers (Micro-level inventory tables).

---

## 2. India-Compliant Data Depth & Sourcing
You cannot pitch this in India without proving it works for the Indian demographic and geography. We will build deep, real data pipelines for the **Top 5-10 Metros** (Mumbai, Delhi, Bengaluru, Pune, Chennai, Hyderabad).

### A. Epidemiological Demand Signal
* **Google Trends via pytrends**: We will geofence our queries specifically to the top 10 Indian cities. We will also include multilingual / regional search queries (e.g., searching for "fever" vs "bukhar").
* **Data.gov.in (Historical Baseline)**: We will seed our ML model using historical monsoon disease outbreak datasets available from the Indian government's open data portal to prove our baseline is medically authentic.

### B. Environmental Stress Signal 
* **OpenWeatherMap API**: We will map exact polygons over our target Indian cities. The intelligence engine will specifically look for the classic Indian outbreak formula: Heavy monsoon rains followed by 3 days of stagnant high humidity.

### C. Live Inventory & Database State
* **Supabase (PostgreSQL)**: Instead of faking everything in Python memory, we will seed a live Supabase PostgreSQL database. It will model a real hierarchy: States -> Districts -> Primary Health Centres (PHCs) / Major Hospitals (e.g., AIIMS, KEM).

---

## 3. Tech Stack Lock-Down (The Startup Fleet)
We are upgrading from the basic supplite stack to a modern, scalable cloud infrastructure.

| Domain | Selected Technology | Reasoning & Scale Factor |
| :--- | :--- | :--- |
| **Frontend** | **Next.js + Deck.GL** | Moving from Vite/React to Next.js proves production readiness (SSR, better routing, API routes if needed). Deck.GL handles the massive 3D data visualization for our city maps seamlessly. |
| **Backend** | **FastAPI (Python)** | High-concurrency. Handles the heavy ML inferencing and data crunching asynchronously. |
| **Database & Auth** | **Supabase** | We drop the demo_data files entirely. Supabase gives us an enterprise-grade PostgreSQL DB, built-in Row Level Security (RLS) for multi-tenant hospital access, and instant JWT Authentication (Google/Email login for hospital admins). |
| **ML Engine** | **Spatio-Temporal Graph Neural Net (ST-GNN) / PyTorch Geometric** | XGBoost belongs in 2018. Outbreaks are not isolated tabular rows; they spread dynamically across geographic networks. We model Indian hospitals and cities as a mathematical graph (nodes = cities, edges = transit routes). An ST-GNN captures both *time-series* (weather/searches over days) and *spatial-spread* (Dengue in Pune today increases risk for Mumbai tomorrow). For pure time-series forecasting, we use **Temporal Fusion Transformers (TFT)**, bypassing legacy gradient boosters entirely. |
| **LLM Orchestration** | **LangChain + OpenAI** | Used to generate the detailed, contextual "Hospital Brief" PDFs explaining the imminent outbreak risks. |

---

## 4. Cloud Deployment & CI/CD Strategy
A product pitch without a live URL is just a PowerPoint. Judges instantly boost scores for teams that prove their architecture survives in the cloud.

* **Frontend Hosting (Vercel)**: Connect the Next.js GitHub repository directly to Vercel for automated, edge-delivered global hosting.
* **Backend Hosting (AWS App Runner or Render.com)**: Package the FastAPI backend into a Dockerfile. Deploying a containerized microservice proves to the judges that the ML engine can scale infinitely on AWS/GCP.
* **CI/CD Pipeline**: Write a GitHub Actions .yml workflow that automatically runs linting (
uff, lake8) and unit tests on every pull request. Having a slide titled "Automated CI/CD Pipeline" separates the engineers from the amateurs.

---

## 5. supplite Codebase Evolution (The Upgrade Path)
To support this expansive vision, we must modify the existing supplite repository heavily:

1. **Rip Out \demo_data.py\ completely**: Replace it with the supabase-py client. Every backend lookup must be a real SQL query to our Supabase instance fetching actual seeded inventory data for Indian hospitals.
2. **MLOps Real-Time Integration**: We completely abandon the static CSV Random Forest approach in `train_real_estate_model.py`. We will implement a custom PyTorch Geometric (PyG) network. We will serialize the PyTorch model (`.pt` or `.onnx`) and load it directly into FastAPI's memory on startup (`@app.on_event("startup")`). When the React frontend sends a live weather anomaly trigger, the backend updates the node features mathematically and propagates the risk score across the spatial graph in real-time.
3. **Supabase Auth Guarding**: Implement middleware in FastAPI that verifies the Supabase JWT token. This proves that Hospital A cannot see Hospital B's inventory data without proper authorization.
