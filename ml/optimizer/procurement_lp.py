"""
Pharmasense — LP Procurement Optimizer
=======================================
Given demand forecasts from the ML models (TFT/N-BEATS median + 90th percentile),
computes the optimal procurement order per drug per hospital.

This is NOT ML — it's linear programming (Operations Research).
This closes the loop: Predict demand → Solve the procurement problem.

No other team will have this. They predict. We prescribe.

Usage:
    from ml.optimizer.procurement_lp import ProcurementOptimizer
    opt = ProcurementOptimizer(db_config)
    orders = opt.optimize(demand_forecasts, hospital_id='HOSP_001')
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class DrugForecast:
    """Output from TFT or N-BEATS for a single drug, single hospital, next N weeks."""
    drug_id: str
    drug_name: str
    formulation: str
    horizon_weeks: int
    demand_q50: np.ndarray   # median forecast (units/week), shape [horizon_weeks]
    demand_q90: np.ndarray   # 90th percentile (procurement buffer), shape [horizon_weeks]
    current_stock: float     # current inventory units
    unit_cost_inr: float     # cost per unit (INR)
    shelf_life_weeks: int    # how many weeks before expiry
    lead_time_weeks: int     # weeks from order to delivery (default 2)
    reorder_level: float     # safety stock trigger (default = 2 weeks demand)


@dataclass
class ProcurementOrder:
    """Recommended purchase order for one drug."""
    drug_id: str
    drug_name: str
    order_quantity: float    # units to order
    order_cost_inr: float    # total cost
    weeks_of_cover: float    # how many weeks the order covers (from delivery)
    urgency: str             # 'CRITICAL', 'HIGH', 'NORMAL', 'DEFER'
    reason: str              # human-readable explanation


@dataclass
class OptimizationResult:
    """Full optimization result for a hospital."""
    hospital_id: str
    district_id: str
    horizon_weeks: int
    orders: List[ProcurementOrder]
    total_cost_inr: float
    budget_used_pct: float
    drugs_at_risk: List[str]   # drugs that will stock out even with order
    optimization_status: str   # 'OPTIMAL', 'INFEASIBLE', 'BUDGET_CONSTRAINED'


class ProcurementOptimizer:
    """
    LP-based procurement optimizer for hospital drug supply.

    Model:
        Decision variables: order_qty[d] for each drug d (continuous, ≥ 0)

        Objective:
            minimize sum(unit_cost[d] * order_qty[d])

        Constraints:
            1. Don't stock out (worst case):
               current_stock[d] + order_qty[d] ≥ sum(demand_q90[d]) over [lead_time, horizon]
            2. Don't over-order perishables:
               order_qty[d] ≤ shelf_life_demand[d]  (don't order more than you can use before expiry)
            3. Budget (optional):
               sum(unit_cost[d] * order_qty[d]) ≤ budget
            4. Non-negativity:
               order_qty[d] ≥ 0

        Extensions:
            - Urgency classification based on days-of-cover
            - Substitution suggestions (not in LP but as post-processing)
    """

    # Urgency thresholds (weeks of cover before order arrives)
    URGENCY_THRESHOLDS = {
        'CRITICAL': 0,    # will stock out before order arrives
        'HIGH':     1,    # less than 1 week cover at delivery
        'NORMAL':   4,    # less than 4 weeks cover
        'DEFER':   float('inf'),  # sufficient stock
    }

    # Default planning parameters (India public health context)
    DEFAULT_LEAD_TIME_WEEKS = 2    # 2-week delivery from state medical store
    DEFAULT_SAFETY_FACTOR   = 1.0  # use q90 as the conservative demand estimate
    DEFAULT_BUDGET_MULTIPLIER = 10.0  # if no budget specified, allow 10x minimum spend

    def __init__(self, db_config: Optional[dict] = None):
        self.db_config = db_config

    def optimize(
        self,
        forecasts: List[DrugForecast],
        hospital_id: str,
        district_id: str,
        budget_inr: Optional[float] = None,
        horizon_weeks: int = 4,
    ) -> OptimizationResult:
        """
        Run LP optimization for a hospital's drug procurement.

        Args:
            forecasts:     List of DrugForecast objects (one per drug)
            hospital_id:   Hospital identifier
            district_id:   District identifier
            budget_inr:    Optional budget constraint (INR)
            horizon_weeks: Planning horizon (should match forecast horizon)

        Returns:
            OptimizationResult with recommended orders
        """
        try:
            from scipy.optimize import linprog
        except ImportError:
            raise ImportError("scipy required: pip install scipy")

        n_drugs = len(forecasts)
        if n_drugs == 0:
            return OptimizationResult(
                hospital_id=hospital_id, district_id=district_id,
                horizon_weeks=horizon_weeks, orders=[],
                total_cost_inr=0.0, budget_used_pct=0.0,
                drugs_at_risk=[], optimization_status='OPTIMAL',
            )

        # ── Build LP problem ──────────────────────────────────────────────────
        unit_costs = np.array([f.unit_cost_inr for f in forecasts], dtype=float)
        # Clamp for numerical stability
        unit_costs = np.clip(unit_costs, 0.01, 1e8)

        # Objective: minimize total procurement cost
        c = unit_costs  # [n_drugs]

        # Inequality constraints: A_ub @ x <= b_ub
        A_ub_rows, b_ub_rows = [], []

        # Constraint 1: don't over-order perishables
        # order_qty[d] <= shelf_life_weeks[d] * avg_weekly_demand[d]
        for i, f in enumerate(forecasts):
            if f.shelf_life_weeks < 52:  # only constrain perishables (< 1 year)
                row = np.zeros(n_drugs)
                row[i] = 1.0
                max_order = f.shelf_life_weeks * float(np.mean(f.demand_q90))
                A_ub_rows.append(row)
                b_ub_rows.append(max_order)

        # Constraint 2: budget (optional)
        if budget_inr is not None:
            A_ub_rows.append(unit_costs.copy())
            b_ub_rows.append(float(budget_inr))

        A_ub = np.array(A_ub_rows) if A_ub_rows else np.zeros((1, n_drugs))
        b_ub = np.array(b_ub_rows) if b_ub_rows else np.array([1e12])

        # Equality constraints: none
        A_eq, b_eq = None, None

        # Bounds: order_qty >= min_order for each drug, >= 0
        # min_order[d] = max(0, demand_q90_over_horizon - current_stock)
        # This is the minimum we NEED to order to avoid stockout
        bounds = []
        min_orders = []
        for f in forecasts:
            effective_horizon = min(horizon_weeks, len(f.demand_q90))
            # Demand during lead time (can't be restocked)
            demand_during_lead = float(np.sum(f.demand_q90[:f.lead_time_weeks]))
            # Total demand over full horizon
            total_demand_q90 = float(np.sum(f.demand_q90[:effective_horizon]))
            # Minimum order to avoid stockout
            min_order = max(0.0, total_demand_q90 - f.current_stock)
            min_orders.append(min_order)
            # Maximum order = shelf_life_demand (handled in constraints above, but set bound too)
            max_order = f.shelf_life_weeks * float(np.mean(f.demand_q90)) * 2
            bounds.append((min_order, max(min_order, max_order)))

        # ── Solve ─────────────────────────────────────────────────────────────
        try:
            result = linprog(
                c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                bounds=bounds, method='highs',
            )
            if result.status == 0:
                opt_status = 'OPTIMAL'
                order_qtys = result.x
            elif result.status == 2:
                # Infeasible — budget too tight. Fall back to min orders ignoring budget.
                opt_status = 'BUDGET_CONSTRAINED'
                order_qtys = np.array([b[0] for b in bounds])
                logger.warning(f'Hospital {hospital_id}: budget infeasible, using minimum orders')
            else:
                opt_status = 'INFEASIBLE'
                order_qtys = np.array([b[0] for b in bounds])
                logger.warning(f'Hospital {hospital_id}: LP status={result.status}, using minimum orders')
        except Exception as e:
            logger.error(f'LP solver error: {e}')
            opt_status = 'INFEASIBLE'
            order_qtys = np.array([b[0] for b in bounds])

        # ── Build output ──────────────────────────────────────────────────────
        orders = []
        drugs_at_risk = []
        total_cost = 0.0

        for i, (f, qty) in enumerate(zip(forecasts, order_qtys)):
            qty = max(0.0, round(qty))
            cost = qty * f.unit_cost_inr

            # Weeks of cover after order arrives
            avg_weekly_demand = float(np.mean(f.demand_q50)) or 1.0
            stock_at_delivery = f.current_stock - float(np.sum(f.demand_q50[:f.lead_time_weeks]))
            total_stock = max(0, stock_at_delivery) + qty
            weeks_of_cover = total_stock / avg_weekly_demand if avg_weekly_demand > 0 else 999

            # Urgency
            cover_before_delivery = f.current_stock / avg_weekly_demand
            if cover_before_delivery < f.lead_time_weeks:
                urgency = 'CRITICAL'
                drugs_at_risk.append(f.drug_name)
                reason = f'Will stock out in {cover_before_delivery:.1f}w, order arrives in {f.lead_time_weeks}w'
            elif weeks_of_cover < 1:
                urgency = 'HIGH'
                reason = f'Only {weeks_of_cover:.1f}w cover after delivery'
            elif qty == 0:
                urgency = 'DEFER'
                reason = f'Sufficient stock ({f.current_stock:.0f} units, {weeks_of_cover:.1f}w cover)'
            else:
                urgency = 'NORMAL'
                reason = f'Order {qty:.0f} units → {weeks_of_cover:.1f}w cover after delivery'

            orders.append(ProcurementOrder(
                drug_id=f.drug_id,
                drug_name=f.drug_name,
                order_quantity=qty,
                order_cost_inr=cost,
                weeks_of_cover=round(weeks_of_cover, 1),
                urgency=urgency,
                reason=reason,
            ))
            total_cost += cost

        budget_used_pct = (total_cost / budget_inr * 100) if budget_inr else 0.0

        # Sort by urgency
        urgency_rank = {'CRITICAL': 0, 'HIGH': 1, 'NORMAL': 2, 'DEFER': 3}
        orders.sort(key=lambda o: urgency_rank.get(o.urgency, 4))

        return OptimizationResult(
            hospital_id=hospital_id,
            district_id=district_id,
            horizon_weeks=horizon_weeks,
            orders=orders,
            total_cost_inr=round(total_cost, 2),
            budget_used_pct=round(budget_used_pct, 1),
            drugs_at_risk=drugs_at_risk,
            optimization_status=opt_status,
        )

    def format_report(self, result: OptimizationResult) -> str:
        """Human-readable procurement report."""
        lines = [
            f"\n{'='*65}",
            f"  PROCUREMENT ORDER — {result.hospital_id} ({result.district_id})",
            f"  Horizon: {result.horizon_weeks} weeks | Status: {result.optimization_status}",
            f"{'='*65}",
        ]
        if result.drugs_at_risk:
            lines.append(f"  [!!] CRITICAL STOCKOUT RISK: {', '.join(result.drugs_at_risk)}")
            lines.append("")

        lines.append(f"  {'Drug':<35} {'Qty':>8} {'Cost (₹)':>12} {'Cover':>8} {'Urgency':>10}")
        lines.append(f"  {'-'*75}")

        for o in result.orders:
            if o.order_quantity > 0:
                lines.append(
                    f"  {o.drug_name[:35]:<35} {o.order_quantity:>8.0f} "
                    f"{o.order_cost_inr:>12,.0f} {o.weeks_of_cover:>7.1f}w {o.urgency:>10}"
                )

        lines.append(f"  {'-'*75}")
        lines.append(f"  {'TOTAL':>55} ₹{result.total_cost_inr:>12,.0f}")
        if result.budget_used_pct:
            lines.append(f"  Budget utilisation: {result.budget_used_pct:.1f}%")
        lines.append(f"{'='*65}\n")
        return '\n'.join(lines)


# ── Standalone demo ────────────────────────────────────────────────────────────
if __name__ == '__main__':
    """
    Demo: run optimizer with synthetic forecasts.
    In production, demand_q50 and demand_q90 come from TFT/N-BEATS model outputs.
    """
    import numpy as np

    # Simulate model outputs for a district hospital
    np.random.seed(42)
    HORIZON = 4

    demo_forecasts = [
        DrugForecast(
            drug_id='ORS_001', drug_name='ORS Sachet 27.9g (WHO)', formulation='sachet',
            horizon_weeks=HORIZON,
            demand_q50=np.array([120, 130, 125, 135]),  # median forecast
            demand_q90=np.array([180, 195, 188, 203]),  # 90th percentile
            current_stock=80.0, unit_cost_inr=4.5, shelf_life_weeks=104, lead_time_weeks=2,
            reorder_level=240.0,
        ),
        DrugForecast(
            drug_id='AML_001', drug_name='Amlodipine 5mg Tablet', formulation='tablet',
            horizon_weeks=HORIZON,
            demand_q50=np.array([450, 455, 460, 458]),
            demand_q90=np.array([540, 546, 552, 550]),
            current_stock=3200.0, unit_cost_inr=0.93, shelf_life_weeks=156, lead_time_weeks=2,
            reorder_level=900.0,
        ),
        DrugForecast(
            drug_id='ART_001', drug_name='Artesunate 60mg Injection', formulation='vial',
            horizon_weeks=HORIZON,
            demand_q50=np.array([8, 10, 9, 11]),
            demand_q90=np.array([15, 18, 16, 20]),
            current_stock=5.0,  # critically low!
            unit_cost_inr=38.0, shelf_life_weeks=24, lead_time_weeks=2,
            reorder_level=30.0,
        ),
        DrugForecast(
            drug_id='MET_001', drug_name='Metformin 500mg Tablet', formulation='tablet',
            horizon_weeks=HORIZON,
            demand_q50=np.array([680, 690, 685, 695]),
            demand_q90=np.array([816, 828, 822, 834]),
            current_stock=6000.0, unit_cost_inr=0.53, shelf_life_weeks=156, lead_time_weeks=2,
            reorder_level=1360.0,
        ),
        DrugForecast(
            drug_id='IFA_001', drug_name='IFA Tablet (Iron + Folic Acid)', formulation='tablet',
            horizon_weeks=HORIZON,
            demand_q50=np.array([320, 325, 322, 330]),
            demand_q90=np.array([384, 390, 386, 396]),
            current_stock=900.0, unit_cost_inr=0.18, shelf_life_weeks=52, lead_time_weeks=2,
            reorder_level=640.0,
        ),
        DrugForecast(
            drug_id='RIF_001', drug_name='Rifampicin 150mg Tablet (DOTS)', formulation='tablet',
            horizon_weeks=HORIZON,
            demand_q50=np.array([210, 215, 212, 218]),
            demand_q90=np.array([252, 258, 254, 262]),
            current_stock=1400.0, unit_cost_inr=1.10, shelf_life_weeks=52, lead_time_weeks=2,
            reorder_level=420.0,
        ),
    ]

    optimizer = ProcurementOptimizer()
    result = optimizer.optimize(
        forecasts=demo_forecasts,
        hospital_id='HOSP_DH_PUNE_001',
        district_id='27_025',  # Pune, Maharashtra
        budget_inr=50_000,     # ₹50,000 procurement budget this cycle
        horizon_weeks=HORIZON,
    )

    print(optimizer.format_report(result))
    print(f'Drugs at critical risk: {result.drugs_at_risk}')
    print(f'Optimization status: {result.optimization_status}')
    print(f'Total orders: {len([o for o in result.orders if o.order_quantity > 0])}')
