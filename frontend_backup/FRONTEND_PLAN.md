# Pharmasense — Frontend Implementation Plan
# Next.js 14 (App Router) · Light Mode · Enterprise Grade

> **Stack:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · shadcn/ui · deck.gl · Recharts · Supabase Auth · SWR
> **Design language:** Clean, minimal, enterprise. White backgrounds, black text, Inter/Geist as the system font (Neue Haas Grotesk equivalent, free). Apple-level polish.
> **Auth:** Supabase Auth JS. Two roles: `pharmacist` (facility-scope) and `district_officer` (district-scope).
> **API:** All data comes from the Go gateway REST API (`/api/*`). No direct Supabase calls from client.

---

## Open Questions (resolve before building)

1. **Map tiles:** Do you have a **Mapbox access token**? The 3D district map uses deck.gl + react-map-gl which needs a Mapbox token for the base map tiles. Without it we fall back to OpenStreetMap tiles (uglier but free). Yes/No?
2. **Domain / deployment:** Are we deploying to Vercel? If yes, any env var setup needed there?
3. **Go gateway URL:** What is the base URL of the Go API gateway for API calls? (Needed for the `.env.local`)
4. **Logo / Brand:** Any existing logo file or wordmark for "Pharmasense"? If not I'll generate one.

---

## 1. Tech Stack — Locked

| Layer | Tool | Why |
|---|---|---|
| Framework | Next.js 14 App Router | SSR, streaming, file-based routing |
| Language | TypeScript | Required for enterprise-grade — no negotiation |
| Styling | Tailwind CSS | Fast, consistent, pairs with shadcn |
| Components | shadcn/ui | Radix primitives + Tailwind — no runtime JS, fully customizable |
| Map | deck.gl + react-map-gl | 3D extruded district heatmap. Industry standard |
| Charts | Recharts | Lightweight, composable, easy to style |
| Auth | @supabase/ssr + @supabase/auth-js | Server-side session management |
| Data fetching | SWR | Stale-while-revalidate, perfect for dashboard data |
| State | Zustand (minimal, only for global state) | Lighter than Redux, simpler than Context for our use case |
| Fonts | next/font → `Geist Sans` (Vercel) | Free, Helvetica-quality, renders perfectly on all platforms |
| Icons | Lucide React | Clean, consistent, works with shadcn |
| Table | TanStack Table v8 | The only real option for enterprise-grade data grids |
| Notifications | Sonner (toast) | Minimal, beautiful toasts |
| Animation | Framer Motion (selective) | Only for page transitions + risk pulse animations — not everywhere |

---

## 2. Monorepo Location

```
pharmasense/
└── frontend/
    ├── app/
    │   ├── (public)/              ← No auth required
    │   │   └── page.tsx           ← Landing page
    │   ├── (auth)/
    │   │   ├── login/page.tsx
    │   │   └── layout.tsx
    │   ├── (dashboard)/           ← Auth wall. All screens inside here.
    │   │   ├── layout.tsx         ← App shell: sidebar + topbar
    │   │   ├── overview/page.tsx  ← Dashboard home
    │   │   ├── inventory/page.tsx
    │   │   ├── orders/page.tsx
    │   │   ├── intelligence/page.tsx
    │   │   ├── simulate/page.tsx
    │   │   └── settings/page.tsx
    │   ├── layout.tsx             ← Root layout (fonts, providers)
    │   └── globals.css
    ├── components/
    │   ├── ui/                    ← shadcn generated components
    │   ├── map/
    │   │   ├── IndiaRiskMap.tsx
    │   │   └── DistrictTooltip.tsx
    │   ├── charts/
    │   │   ├── SignalTimeline.tsx
    │   │   ├── RiskGauge.tsx
    │   │   └── InventoryBar.tsx
    │   ├── shared/
    │   │   ├── AppShell.tsx
    │   │   ├── Sidebar.tsx
    │   │   ├── TopBar.tsx
    │   │   ├── RiskBadge.tsx
    │   │   ├── StatCard.tsx
    │   │   └── HospitalBriefDrawer.tsx
    │   └── tables/
    │       ├── InventoryTable.tsx
    │       └── OrdersTable.tsx
    ├── lib/
    │   ├── api.ts                 ← Typed API client (fetch wrapper)
    │   ├── auth.ts                ← Supabase auth helpers
    │   ├── types.ts               ← All shared TS types
    │   └── utils.ts               ← cn(), formatters, etc.
    ├── hooks/
    │   ├── useDistrict.ts
    │   ├── useInventory.ts
    │   ├── useOrders.ts
    │   └── useRiskScore.ts
    ├── public/
    │   └── logo.svg
    ├── .env.local
    ├── next.config.ts
    ├── tailwind.config.ts
    └── package.json
```

---

## 3. Design System

### Color Palette (Light Mode Only)
```css
--background:     #FFFFFF
--foreground:     #0A0A0A
--muted:          #F5F5F5
--muted-fg:       #6B6B6B
--border:         #E5E5E5
--input:          #FAFAFA

/* Risk semantic colors — the only non-neutral colors in the app */
--risk-critical:  #DC2626   /* red-600 */
--risk-high:      #EA580C   /* orange-600 */
--risk-moderate:  #CA8A04   /* yellow-600 */
--risk-low:       #16A34A   /* green-600 */
--risk-none:      #6B7280   /* gray-500 */

/* Accent — used sparingly for interactive elements */
--accent:         #2563EB   /* blue-600 */
--accent-fg:      #FFFFFF
```

### Typography
```css
font-family: 'Geist Sans', 'Helvetica Neue', -apple-system, sans-serif;

/* Scale */
--text-xs:   11px / 1.4  → labels, metadata
--text-sm:   13px / 1.5  → table cells, secondary text  
--text-base: 15px / 1.6  → body copy
--text-lg:   17px / 1.4  → subheadings
--text-xl:   20px / 1.3  → section headers
--text-2xl:  24px / 1.25 → page titles
--text-4xl:  36px / 1.1  → hero numbers (stat cards)
--text-6xl:  56px / 1.0  → landing hero

font-weight: 400 (regular), 500 (medium), 600 (semibold)
/* No bold/700 except for hero numerals. Keep it clean. */
```

### Spacing & Radius
```css
/* 4px base unit */
--radius-sm: 6px   → badges, tags
--radius:    8px   → cards, inputs, buttons
--radius-lg: 12px  → modals, drawers
--radius-xl: 16px  → map container

/* Sidebar: 240px wide, fixed */
/* TopBar: 56px tall */
/* Content area: full width minus sidebar, padding 24px */
```

### Component Rules
- **Cards:** white bg, 1px `--border` border, `--radius` corners, `16px` padding, subtle `shadow-sm`
- **Buttons:** primary = `--accent` bg; secondary = white bg with border; destructive = `--risk-critical`
- **Tables:** no outer border, thin row dividers (`--border`), row hover = `--muted`
- **Risk badges:** pill-shaped, color = semantic risk color, font-size 11px, uppercase
- **No gradients, no glassmorphism, no shadows except `shadow-sm` on cards.** The Apple restraint.

---

## 4. Screens — Full Spec

---

### SCREEN 1 — Landing Page (`/`) — Public

**Purpose:** Convert visitors (judges, investors, potential customers). Show the power of the product without needing a login.

**Layout:** Full-width, no sidebar. Simple top nav (logo left, "Sign In" CTA right).

**Sections (top to bottom):**

#### Hero Section
- **Headline:** `"Drug shortages don't happen overnight. We see them coming."` (or similar — you confirm copy)
- **Sub-copy:** 2 lines max. "Pharmasense uses epidemic intelligence to predict drug demand across 641 Indian districts — before outbreaks happen."
- **CTA:** Two buttons — `Get Started` (→ /login) and `See how it works` (smooth scroll to features)
- **Background:** Clean white. The hero is the MAP below it, not a splash image.

#### Live Risk Map (The Hero Visual)
- Full-width interactive 3D deck.gl map of India
- Districts rendered as extruded 3D polygons — height AND color both encode the current 14-day risk score
  - Green (low) → Yellow (moderate) → Orange (high) → Pulsing Red (critical)
- Hover tooltip: district name, risk score, top predicted disease, days to predicted peak
- Click a district: side panel slides in showing the signal breakdown (weather + search + epid trend mini-charts)
- **No auth required.** This is the bait. This is what gets judges to lean forward.
- Label: `"Live 14-day outbreak risk — updated daily"` — small badge in top-left of map

#### How It Works Strip
- 3 steps in a horizontal card row:
  1. **Predict** — "ST-GNN + Graph WaveNet models detect outbreak spread patterns 7-14 days early"
  2. **Translate** — "ICMR treatment protocols convert case predictions into exact drug quantities"
  3. **Order** — "Auto-generated Purchase Orders reach pharmacists before shelves run empty"

#### Key Numbers (stat row)
```
641        613        7 yrs       8
Districts  Drug SKUs  Training    Disease
tracked    monitored  data        types
```

#### Signal Showcase (mini version of the Intelligence screen)
- Pick one example district (hardcoded for demo — say, Mumbai or Pune during monsoon)
- Show a 3-line sparkline chart: rainfall vs. search trend vs. predicted cases, with a vertical "Today" marker and the forward prediction shaded differently
- Caption: "7 days before cases peak, our model already sees the signal."

#### CTA Footer
- "Start managing your facility's drug supply intelligently."
- `Sign In` button → /login

---

### SCREEN 2 — Login (`/login`) — Auth

**Layout:** Centered card on white background. Logo at top. No sidebar.

**Content:**
- Logo + "Pharmasense" wordmark
- "Sign in to your facility account" — subtitle
- Email input
- Password input
- "Sign In" button
- "Forgot password?" link
- No sign-up flow (accounts are provisioned by admin — this is enterprise software)

**Post-login redirect logic:**
- `district_officer` role → `/intelligence` (the macro view)
- `pharmacist` role → `/overview` (their facility dashboard)

---

### SCREEN 3 — App Shell (Persistent after login)

All authenticated screens share this layout:

**Sidebar (240px, fixed left):**
```
[Logo + "Pharmasense" wordmark]

Navigation:
  Overview          ← home icon
  Inventory         ← package icon
  Purchase Orders   ← clipboard icon
  Intelligence      ← map/brain icon
  Simulate          ← flask icon (shown for district_officer only)

[Divider]

[Bottom section]
  Settings
  [Avatar + name + role badge]
  Sign Out
```
- Active nav item: left border accent `2px --accent`, text = `--foreground`, bg = `--muted`
- Inactive: `--muted-fg`
- Sidebar is NOT collapsible in v1 — keep it simple

**Top Bar (56px):**
- Left: Page title (changes per route)
- Right: 
  - Notification bell (badge count = pending orders)
  - Hospital/District name chip (shows scope)
  - Last updated timestamp: `"Updated 3 min ago"`

---

### SCREEN 4 — Overview / Dashboard (`/overview`) — Auth

**Purpose:** The first thing a pharmacist sees after login. Everything critical, at a glance.

**Layout:** Single column, card-based grid.

#### Risk Alert Banner (conditional — only if risk > moderate)
- Full-width banner at top of content
- Red/orange left border, light bg
- Example: `⚠ Dengue surge predicted in Pune District — 9 days to estimated peak. 3 drugs at critical levels.`
- `View Intelligence →` link on right

#### Stat Cards Row (4 cards)
| Card | What it shows |
|---|---|
| **Drugs at Risk** | Count of drugs with < 7 days supply. Click → Inventory filtered to critical |
| **Pending Orders** | Count of POs awaiting approval. Click → /orders |
| **District Risk Score** | Current 0–100 risk score with color coding. Subtitle: top disease |
| **Neighboring Alert** | Count of adjacent districts with HIGH/CRITICAL risk. Subtitle: closest threat |

#### Inventory Snapshot (Table preview — top 8 critical drugs)
- Condensed version of the inventory table
- Shows only drugs with stock status WATCH or CRITICAL
- Columns: Drug Name | Stock | Demand (14d) | Days Cover | Status
- `View all inventory →` link at bottom-right

#### Recent Activity Feed (right side — 1/3 width)
- Timeline-style list of system events (most recent first)
- Examples:
  - `[2 hrs ago] Auto-PO drafted: 5,000 units Paracetamol 500mg`
  - `[Yesterday] Risk score updated: Pune → 72/100 (High)`
  - `[2 days ago] PO #1042 approved via WhatsApp`
  - `[3 days ago] Weather anomaly: rain > 40mm for 3 consecutive days`

#### Mini Signal Chart (full width at bottom)
- 90-day sparkline for the facility's district
- 3 lines: Rainfall (blue) | Search Trend (purple) | Case Index (red)
- Forward zone (next 14 days) shaded lighter with prediction confidence band

---

### SCREEN 5 — Inventory Manager (`/inventory`) — Auth

**Purpose:** The daily workhorse screen for a pharmacist. Full drug catalog management.

**Layout:** Full-width table with filter sidebar on left (collapsible, 200px).

#### Filter Sidebar
- Status: All | Safe | Watch | Critical
- Disease category: Dengue drugs | Malaria drugs | Cholera drugs | NCD drugs | ADD drugs
- Formulation: Tablets | Injections | IV Bags | Sachets | All
- Search bar (fuzzy search by drug name or generic name)

#### Main Table (TanStack Table)
**Columns:**
| Column | Detail |
|---|---|
| **Drug Name** | Full name + generic name underneath in smaller text |
| **Formulation** | Pill badge: `Tablet` / `IV Bag` / `Injection` / `Sachet` |
| **Current Stock** | Units on hand |
| **Predicted Demand (14d)** | ML-predicted units needed in next 14 days. Tooltip: "Based on ICMR protocol × predicted cases" |
| **Days Cover** | `stock / (demand / 14)`. Color-coded number: green > 14d, yellow 7-14d, red < 7d |
| **Status** | Pill badge: `SAFE` / `WATCH` / `CRITICAL` |
| **Last Restocked** | Date |
| **Action** | `Draft Order` button on WATCH/CRITICAL rows |

**Table UX:**
- Sortable by any column (click header)
- Default sort: Days Cover ascending (most critical first)
- Row click: expands to show 30-day consumption history sparkline inline
- Sticky header
- Pagination: 25 rows per page
- Export button (CSV): top-right

#### Inline Order Draft (on `Draft Order` click)
- Small inline form below the row (not a modal — doesn't break table flow)
- Pre-filled quantity (from LP optimizer recommendation)
- Supplier field (free text v1)
- Justification (auto-filled: "AI recommendation based on predicted dengue surge")
- `Submit Order` → creates PO in Pending state

---

### SCREEN 6 — Purchase Orders (`/orders`) — Auth

**Purpose:** Track and approve all autonomous and manually-drafted POs.

**Layout:** Split view. Left: order list. Right: order detail panel.

#### Left: Orders List
- Filter tabs at top: `All` | `Pending` | `Approved` | `Rejected`
- Each order card in the list:
  - Drug name (bold) + quantity
  - Status badge (color coded)
  - Triggered by: `[AI — Dengue Risk]` or `[Manual — Pharmacist]`
  - Created: relative time (`3 hours ago`)
  - If WhatsApp-approved: `✓ Approved via WhatsApp` indicator

#### Right: Order Detail Panel
When an order is selected from the list:

- **Drug info:** name, generic, formulation, current stock
- **AI Justification section:**
  - *"This order was automatically generated because the predicted dengue case rate in [District] is expected to exceed the stockout threshold in 6 days. At the ICMR-recommended dose of 15mg/kg/day, the predicted patient load requires approximately 4,800 units of Paracetamol 500mg over the next 14 days. Current stock covers only 3.2 days at this rate."*
- **Signal evidence:**
  - Mini 3-chart strip: rainfall, search index, case forecast (same as Intelligence but compact)
- **LP Optimizer recommendation:**
  - Order qty | Urgency label (`CRITICAL` / `HIGH` / `NORMAL`) | Estimated cost (INR)
- **Actions:**
  - Large `Approve Order` button (green)
  - `Reject` button (ghost, red text)
  - `Edit Quantity` before approving
- **Already approved:** show approval timestamp + who approved (user or "WhatsApp")

---

### SCREEN 7 — Outbreak Intelligence (`/intelligence`) — Auth

**Purpose:** The analytical view. Understanding *why* risk is elevated. More relevant for district officers, but pharmacists can use it too.

**Layout:** Map takes 60% of screen (left). Analysis panel takes 40% (right). Both scrollable independently.

#### Left: Interactive District Map
- Full deck.gl 3D choropleth — same as landing page but with more controls
- **Layer controls (top-left of map):**
  - Toggle: Risk Score | Predicted Cases | Drug Demand | Stock Cover
  - Disease filter: All diseases | Dengue | Malaria | Cholera | ADD
  - Time slider: "Showing forecast for: Today / +3d / +7d / +14d" (scrub forward in time)
- Click district → right panel loads that district's data
- **Adjacency overlay toggle:** shows arrows between districts indicating predicted disease direction of spread (this is the USP visual — nobody else has this)

#### Right: District Analysis Panel
When a district is clicked:

**Header:** District name + State + Current risk score badge

**Tab 1 — Signal Breakdown**
- 3 stacked line charts (Recharts, synchronized x-axis):
  - Rainfall (mm) — last 60d + 14d forecast
  - Symptom Search Index — last 60d + 14d forecast
  - Case Rate per 100k — last 60d + 14d forecast
- Contribution weights: "Risk composed of: 45% weather signal, 30% search signal, 25% historical baseline"
- Horizontal bar breakdown — makes the model interpretable

**Tab 2 — Drug Impact**
- Table: given this district's predicted caseload, what drugs are affected?
- Columns: Drug | ICMR Predicted Demand | Facilities At Risk | Worst-Case Stockout
- Links to relevant inventory items

**Tab 3 — AI Brief**
- The Gemini-generated plain English hospital brief
- Cached 24h, refresh button
- If no brief yet: `Generate Brief` button triggers on-demand Gemini call
- Loading state: skeleton text animation

**Tab 4 — Neighbors**
- List of adjacent districts with their risk scores
- Direction indicator: "Outbreak spreading FROM [District A] → TO [your district]" if applicable
- Allows district officer to see regional picture

---

### SCREEN 8 — Simulate (`/simulate`) — Auth (district_officer only)

**Purpose:** Demo + planning tool. "What happens if monsoon is worse than expected?"

**Layout:** Left: controls panel (320px). Right: live map that reacts to simulation.

#### Controls Panel

**Section 1 — Weather Scenario**
- Rainfall intensity: slider (0% → 200% of normal)
- Duration: select (1 week / 2 weeks / 1 month)
- Humidity spike: toggle (adds 15% humidity to affected regions)

**Section 2 — Target Area**
- Select districts from dropdown (multi-select)
- OR: draw on map (click districts to include)

**Section 3 — Disease Focus**
- Dengue | Malaria | Cholera | All (radio)

**Run Simulation button:**
- Calls `POST /api/simulate/monsoon` with the parameters
- Big, clear, labeled `"Run Simulation"` — not buried

#### Simulation Results (appear after run)
- Map updates: affected districts extrude higher, colors shift toward red
- Summary card below controls: "Under this scenario, **14 districts** shift to HIGH or CRITICAL risk. **3 hospitals** in your district are predicted to stock out of Paracetamol within 5 days."
- Table: District | Current Risk | Simulated Risk | Drug Impact
- "Generate Simulation POs" button → drafts orders for all projected stockouts

**Clearly labeled "SIMULATION MODE" badge on top right of map** — prevents confusion with real data.

---

### SCREEN 9 — Settings (`/settings`) — Auth

**Purpose:** User preferences. Minimal v1.

**Sections:**
- **Profile:** Name, role (read-only), facility name (read-only), email
- **Notifications:** Toggle WhatsApp alerts on/off | Notification threshold (risk score > X)
- **Display:** Date format | Units (this is v1, just placeholder)
- **Security:** Change password (delegates to Supabase)

---

## 5. Shared Components — Detailed Spec

### `RiskBadge`
```tsx
<RiskBadge score={72} />
// Renders: pill-shaped badge, color-coded
// score 0-25:  SAFE (green)
// score 26-50: MODERATE (yellow)
// score 51-75: HIGH (orange)
// score 76-100: CRITICAL (red, subtle pulse animation)
```

### `StatCard`
```tsx
<StatCard
  title="Drugs at Risk"
  value={12}
  subtitle="↑ 3 from yesterday"
  trend="up"          // up = bad here, color red
  href="/inventory"
/>
```
- White card, border, shadow-sm
- Value: `text-4xl font-semibold`
- Trend arrow colored by context (not always red-for-up — context matters)

### `HospitalBriefDrawer`
- Slides in from the right (not a modal — doesn't block the map)
- Width: 480px
- Contains the AI brief text + signal mini-charts
- Dismiss: click outside or X button
- Shows "Loading..." skeleton while Gemini API call is in flight
- Shows "Cached · 4 hrs ago" if from Redis cache

### `SignalTimeline`
- Recharts `ComposedChart`
- 3 series: rain (bar, blue, opacity 0.4), search index (line, purple), cases (line, red)
- Vertical dashed line at "Today"
- Right side shaded zone: "Forecast (next 14 days)"
- All axes share the same x-axis (week dates)

### `IndiaRiskMap`
- deck.gl `GeoJsonLayer` with `extruded: true`
- Elevation = `risk_score * 500` (capped at 50,000m visual height)
- Fill color interpolation: green → yellow → orange → red based on risk_score
- Orbit controller (drag to rotate, scroll to zoom)
- `getTooltip` → district name, risk score, top disease
- Click handler → triggers district selection (updates right panel or drawer)

---

## 6. API Integration Map

All calls go through `lib/api.ts` — a typed fetch wrapper with auth header injection.

| Screen | Endpoints Used |
|---|---|
| Landing map | `GET /api/districts` (all districts + risk scores) |
| Dashboard | `GET /api/hospitals/{id}`, `GET /api/districts/{id}/risk`, `GET /api/purchase-orders` |
| Inventory | `GET /api/hospitals/{id}/inventory` |
| Orders | `GET /api/purchase-orders`, `POST /api/purchase-orders/{id}/approve` |
| Intelligence | `GET /api/districts`, `GET /api/districts/{id}/risk`, `GET /api/signals/timeline/{id}`, `GET /api/hospitals/{id}/brief` |
| Simulate | `POST /api/simulate/monsoon` |

SWR is used for all reads. Mutations use direct fetch + SWR `mutate()` to invalidate cache.

---

## 7. Auth Flow

```
User hits any /dashboard/* route
  → middleware.ts checks Supabase session cookie
  → no session? redirect to /login
  → session valid? extract role from JWT
  → attach role to request context (via headers)
  → render appropriate UI based on role
```

Role-based UI differences:
- `pharmacist`: no Simulate screen in sidebar, hospital-scoped data only
- `district_officer`: Simulate screen visible, sees all hospitals in their district

---

## 8. Build Order

Execute in this exact order. Each step is unblocked by the previous.

```
[ ] Step 1: Scaffold Next.js 14 app in frontend/
    npx create-next-app@latest ./ --typescript --tailwind --app --src-dir=no --import-alias="@/*"

[ ] Step 2: Install all dependencies
    shadcn/ui init, lucide-react, @supabase/ssr, swr, zustand, recharts, 
    deck.gl, react-map-gl, @tanstack/react-table, framer-motion, sonner

[ ] Step 3: Design system setup
    globals.css (CSS variables), tailwind.config.ts (extend theme with custom colors),
    lib/utils.ts (cn() helper)

[ ] Step 4: shadcn/ui component installs
    button, input, badge, card, table, dialog, drawer, tabs, select, 
    slider, separator, avatar, dropdown-menu, skeleton, toast

[ ] Step 5: Type definitions (lib/types.ts)
    District, Hospital, Drug, InventoryItem, PurchaseOrder, RiskScore, 
    SignalTimeline, HospitalBrief, User types

[ ] Step 6: API client (lib/api.ts)
    Typed fetch wrapper, all endpoint functions

[ ] Step 7: Auth infrastructure
    middleware.ts, lib/auth.ts, Supabase client (server + browser),
    login page, auth redirect logic

[ ] Step 8: App shell (components/shared/)
    Sidebar, TopBar, AppShell — the layout every dashboard screen uses

[ ] Step 9: Shared components
    RiskBadge, StatCard, HospitalBriefDrawer, SignalTimeline

[ ] Step 10: India Risk Map (components/map/)
    IndiaRiskMap (deck.gl), DistrictTooltip
    → This takes the longest. Mapbox token required.

[ ] Step 11: Screens — in priority order
    [ ] /overview (Dashboard)
    [ ] /inventory (Inventory Manager + TanStack table)
    [ ] /orders (PO Inbox)
    [ ] /intelligence (Outbreak map + analysis panel)
    [ ] /simulate (Simulation controls)
    [ ] /login
    [ ] / (Landing page — do LAST, most polish needed)
    [ ] /settings

[ ] Step 12: Data hooks (hooks/)
    useInventory, useOrders, useRiskScore, useDistrict

[ ] Step 13: Role-based access control
    Sidebar hiding for pharmacist, data scoping via API params

[ ] Step 14: Landing page
    Full design, signal showcase, how-it-works strip, live map

[ ] Step 15: Polish pass
    Loading skeletons on all async data, empty states, error boundaries,
    responsive layout check (tablet minimum)
```

---

## 9. Performance Rules

- All map data (`/api/districts`) fetched server-side on first load, passed as props to the map component
- SWR `refreshInterval: 300_000` (5 min) for risk scores on dashboard
- `next/image` for any images
- `React.lazy` + `Suspense` for the deck.gl map (it's heavy — don't block the page)
- Skeleton loaders for every async boundary — no spinners
- The map renders client-side only (`dynamic(() => import(...), { ssr: false })`)

---

## 10. Things We Are NOT Building in v1

- Dark mode (light only — keep it simple)
- Mobile layout (tablet is minimum)
- Real-time WebSocket updates (SWR polling is enough for hackathon)
- Admin screen (account provisioning)
- Multi-tenant onboarding flow
- i18n / Hindi language support
- Complex animation sequences
- Any charts that require D3 directly

---

*Last updated: 2026-06-05*
*Frontend version: 1.0 — built for AgTechathon 2.0 2K26*
