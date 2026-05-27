# Supplite → Gig Economy Pivot

## Current Project Foundation
- **Name**: Supplite (Demand Intelligence System)
- **Original Domain**: WSI (Williams-Sonoma) inventory forecasting
- **Core Innovation**: Fuses 3 signals (sales history + Google Trends virality + US Census housing permits)
- **Output**: LLM-powered "buyer briefs" with action recommendations
- **Architecture**: Python backend (ML/geocoding) + React 3D map dashboard + API layer

## Hackathon Theme Target
"Gig & Freelancing Economy" — improving income stability, fair opportunities, and support systems for independent workers.

## Proposed Pivots (choose one or combine)

### Option A: Freelancer Skills Demand Forecast
- **Idea**: Predict demand for freelance services before it appears in jobs data
- **Signals**: Google Trends (searches for "web designer", "content writer", etc) + Real estate permits (construction spikes = contractor demand) + Job posting trends
- **Output**: "Skill briefing" for freelancers — when to upskill, which markets are heating up
- **USP**: Only gig system using real estate as a leading indicator for service demand

### Option B: Gig Worker Opportunity Navigator
- **Idea**: Help gig workers (delivery, TaskRabbit, Upwork) find high-opportunity markets
- **Signals**: Real estate activity (permits/renovations = TaskRabbit demand) + Google Trends + Task posting velocity
- **Output**: Regional opportunity alerts, earning forecasts, best times/places to work
- **Dashboard**: Map showing gig economy "heat" by region and category

### Option C: Income Stability Intelligence for Contractors
- **Idea**: Help independent contractors (electricians, plumbers, designers) predict work pipelines
- **Signals**: Real estate construction permits + Search trends for home services + Seasonal patterns
- **Output**: "Work pipeline briefing" — predict 4-12 weeks ahead when work will be scarce/abundant
- **Differentiator**: Fair opportunities + income planning = financial stability

### Option D: Multi-Service Marketplace Dashboard (combines A+B+C)
- **Unified platform** for all gig economy participants
- Predict demand across multiple service categories simultaneously
- Help workers make portfolio decisions (which services to offer, when)

## Reusable Assets from Supplite
✅ Geospatial mapping (territories → regions/cities)
✅ Signal fusion architecture (can adapt to any 3+ signal set)
✅ LLM briefing generation pipeline
✅ Dashboard filtering/layer toggles
✅ Risk classification logic (stockout/overstock → opportunity/shortage/stable)
✅ API/backend structure

## Changed Elements
- Data sources: Google Trends + Census permits + gig platform APIs
- ML model: Retrain on freelance/gig demand instead of furniture SKUs
- Domain terminology: "SKU" → "Service Category", "Buyer Brief" → "Worker Brief", etc.
- Map visualization: Regional opportunity heatmaps instead of store territories
