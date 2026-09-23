<div align="center">
  <h1>💊 Pharmasense</h1>
  <p><b>Predictive Pharmaceutical Supply Chain Platform</b></p>
</div>

## 📌 Overview

**Pharmasense** is a predictive pharmaceutical supply chain platform built for India. Instead of reacting to drug stockouts during disease outbreaks, Pharmasense cross-references live environmental signals (monsoon weather, symptom search trends) against district-level epidemiological baselines to predict outbreaks **7-14 days before they physically cross into a new district**.

The moment a prediction crosses a risk threshold, the system autonomously generates Purchase Orders and alerts pharmacists—solving the problem *before* shelves go empty.

## 🚀 Key Differentiators

- **ICMR Translation Layer**: 1 confirmed dengue case → exact quantity of paracetamol, IV fluids, ORS required per ICMR Standard Treatment Guidelines. We predict exact drug-level drawdown volumes from first principles.
- **Dual-Engine ML Router**: 
  - *Communicable diseases* (dengue, malaria, cholera) are routed to an **ST-GNN** (Spatio-Temporal Graph Neural Network) modeling geographical spread.
  - *Non-communicable / baseline demand* (hypertension meds) are routed to a **TFT** (Temporal Fusion Transformer) utilizing time-series and covariates.
- **Role-Based Access Control**: Macro (State Health Minister), Meso (District Health Officer), and Micro (Hospital Pharmacist) views enforced physically at the database level via Supabase Row Level Security (RLS).

## 🏗 Architecture

Our architecture is designed to be highly scalable, utilizing a Go API Gateway to route traffic seamlessly to Python ML microservices via gRPC.

- **Frontend**: Streamlit (Phase 1) & Next.js 14 App Router (Phase 2)
- **API Gateway**: Go (Gin + gRPC client) for JWT verification, rate limiting, and request routing.
- **ML Service**: Python (FastAPI + gRPC server) running ST-GNN (PyTorch Geometric) and TFT (pytorch-forecasting).
- **Event Bus**: Kafka + Zookeeper for outbreak events (PO Generation, WhatsApp Twilio Notifications).
- **Database & Auth**: Supabase (PostgreSQL 15 + PostGIS + Auth + RLS).
- **Caching**: Redis (Prediction cache).

## 📊 Data Pipeline

Pharmasense relies on a robust mix of static datasets and live telemetry:
- **EpiClim (2016-2023)**: 7 years of weekly district-level case counts.
- **Live Signals**: OpenWeatherMap API (hourly) & Google Trends/pytrends (daily).
- **ICMR Rules**: Translation engine converting case counts into specific SKU demand volumes.

## ⚙️ How it works

1. **Daily Batch**: Fetches weather and search signals, computes risk probabilities per district using the ML Router, and caches predictions in Redis.
2. **Event Trigger**: If a predicted shortfall exceeds a threshold, an outbreak_event is published to Kafka.
3. **Automated POs**: A Kafka consumer autonomously generates a Purchase Order in Supabase.
4. **WhatsApp Alerts**: Another consumer triggers a Twilio WhatsApp alert to the pharmacist ("Reply YES to auto-approve PO").
5. **Real-time Map**: The frontend updates with live 3D district heatmaps and LLM-generated hospital risk briefs powered by Gemini 1.5 Flash.

## 💻 Tech Stack Summary

- **Language:** Go, Python, TypeScript
- **Machine Learning:** PyTorch, PyTorch Geometric, pytorch-forecasting, scikit-learn
- **Infrastructure:** Docker, Redis, Apache Kafka, Supabase
- **APIs:** Gemini API, Twilio, OpenWeatherMap

----
