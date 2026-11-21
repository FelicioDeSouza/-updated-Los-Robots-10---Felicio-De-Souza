import json
import math
from decimal import Decimal, ROUND_HALF_UP
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="ROB-3 | Robotics Kit & Repair Studio", layout="wide")


def money(val) -> float:
    return float(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def default_state():
    return {
        "team_id": "ROB-TEAM",
        "course": "AP Calculus",
        "pathway_id": "ROB-3",
        "selected_level": "Advanced",
        "state_version": 1,
        "snapshot_id": "SNAP-001",
        "simulation_date": "2027-01-31",
        "currency": "USD",
        "opening_cash": 5000.00,
        "cash": 5000.00,
        "equipment_assets": 4000.00,
        "owner_contribution": 12000.00,
        "retained_earnings": 0.00,
        "debt": 0.00,
        "stock_units": 100,
        "component_unit_cost": 30.00,
        "base_price": 120.00,
        "D0": 40,
        "staff_hours": 90.0,
        "hours_per_unit": 3.0,
        "defect_rate": 0.0,
        "noncomponent_var_cost": 35.00,  # $20 labor + $10 packaging + $5 warranty
        "fixed_monthly_cost": 600.00,    # $250 workspace + $100 software + $150 maint + $100 admin
        "processed_run_ids": [],
        "ledger": [],
        "campaigns": [],
        "recommendations": [],
        "decisions": [],
        "cross_course": {
            "subject_1": "Engineering (Science) - Sensor/Controller Defect & Safety Analysis",
            "subject_2": "CTE - Robotics Field Vocabulary, Service Standards & Quality Checklist",
        },
    }


if "biz" not in st.session_state:
    st.session_state.biz = default_state()

biz = st.session_state.biz

# Ensure keys exist if loading a Stage 1 JSON snapshot
for key, default_val in default_state().items():
    if key not in biz:
        biz[key] = default_val


def run_month_step(
    state: dict,
    run_id: str,
    sim_date: str,
    requested: int,
    price: float,
    staff_hours: float,
    hours_per_unit: float,
    restock_units: int,
    defect_rate: float,
    ad_cost: float,
    capacity_override: int | None = None,
):
    if run_id in state["processed_run_ids"]:
        return False, f"Duplicate run_id '{run_id}' rejected. No duplicate transactions created."

    # 1. Restock inventory first (cash outflow on purchase; inventory asset increases)
    restock_cost = money(restock_units * state["component_unit_cost"])
    if restock_units > 0:
        state["cash"] = money(state["cash"] - restock_cost)
        state["stock_units"] += int(restock_units)
        state["ledger"].append({
            "run_id": run_id,
            "date": sim_date,
            "event_type": "INVENTORY_RESTOCK",
            "category": "Inventory Purchase",
            "quantity": int(restock_units),
            "unit_price": state["component_unit_cost"],
            "amount": -restock_cost,
            "state_version": state["state_version"],
        })

    # 2. Deterministic ROB capacity & fulfillment algorithm
    derived_cap = math.floor(staff_hours / hours_per_unit) if hours_per_unit > 0 else 0
    effective_cap = int(capacity_override) if capacity_override is not None else derived_cap
    attempted = min(int(requested), effective_cap, int(state["stock_units"]))
    failed = math.floor(attempted * defect_rate)
    sold = attempted - failed
    unserved = max(0, int(requested) - attempted)

    # 3. Revenue and costs (Robotics consumes components and non-component var costs on ATTEMPTED kits)
    revenue = money(sold * price)
    consumed_component_cost = money(attempted * state["component_unit_cost"])
    noncomponent_var_total = money(attempted * state["noncomponent_var_cost"])
    total_variable_expense = money(consumed_component_cost + noncomponent_var_total)
    fixed_expense = money(state["fixed_monthly_cost"])
    marketing_expense = money(ad_cost)

    operating_profit = money(revenue - total_variable_expense - fixed_expense - marketing_expense)

    # Cash outflow excludes consumed startup/existing inventory (already paid at purchase)
    cash_delta = money(revenue - noncomponent_var_total - fixed_expense - marketing_expense)
    state["cash"] = money(state["cash"] + cash_delta)
    state["stock_units"] -= attempted
    state["retained_earnings"] = money(state["retained_earnings"] + operating_profit)

    # 4. Record ledger entries
    state["ledger"].append({
        "run_id": run_id,
        "date": sim_date,
        "event_type": "MONTHLY_OPERATIONS",
        "category": "Kit Sales & Operations",
        "requested": int(requested),
        "attempted": attempted,
        "failed_kits": failed,
        "sold": sold,
        "unserved_demand": unserved,
        "revenue": revenue,
        "component_expense": consumed_component_cost,
        "noncomponent_var_expense": noncomponent_var_total,
        "fixed_expense": fixed_expense,
        "marketing_expense": marketing_expense,
        "operating_profit": operating_profit,
        "ending_cash": state["cash"],
        "ending_stock_units": state["stock_units"],
        "state_version": state["state_version"],
    })

    state["processed_run_ids"].append(run_id)
    state["state_version"] += 1
    state["snapshot_id"] = f"SNAP-{state['state_version']:03d}"
    state["simulation_date"] = sim_date
    return True, (
        f"Run {run_id} approved (v{state['state_version']}): Attempted={attempted}, "
        f"Failed={failed}, Sold={sold}, Profit=${operating_profit:,.2f}, Cash=${state['cash']:,.2f}"
    )


# --- HEADER ---
st.title("ROB-3 | Robotics Kit & Repair Studio (Stage 2 Dashboard)")
st.caption(
    f"Team: {biz['team_id']} | Course: {biz['course']} ({biz['selected_level']}) | "
    f"State: v{biz['state_version']} ({biz['snapshot_id']}) | Simulation Only (Fictional Data)"
)

# --- SIDEBAR: STATE & SNAPSHOT CONTROL ---
with st.sidebar:
    st.header("State & Snapshot Control")
    biz["team_id"] = st.text_input("Team ID", value=biz["team_id"])
    biz["selected_level"] = st.selectbox(
        "Challenge Level (Teacher Approved)",
        ["Foundation", "Applied", "Advanced"],
        index=["Foundation", "Applied", "Advanced"].index(biz["selected_level"]),
    )

    st.download_button(
        label="Export Snapshot JSON",
        data=json.dumps(biz, indent=2),
        file_name=f"{biz['team_id']}_v{biz['state_version']}_snapshot.json",
        mime="application/json",
    )

    uploaded_json = st.file_uploader("Restore / Import Snapshot JSON", type=["json"])
    if uploaded_json is not None:
        try:
            incoming = json.load(uploaded_json)
            if incoming.get("team_id") != biz["team_id"]:
                st.error(f"Import rejected: Team ID mismatch ('{incoming.get('team_id')}' != '{biz['team_id']}').")
            elif incoming.get("state_version", 0) < biz["state_version"]:
                st.error(
                    f"Import rejected: Stale state_version v{incoming.get('state_version')} "
                    f"(current is v{biz['state_version']})."
                )
            else:
                st.session_state.biz = incoming
                st.success(f"Snapshot v{incoming['state_version']} restored.")
                st.rerun()
        except Exception as exc:
            st.error(f"Invalid JSON file: {exc}")

    if st.button("Reset to Opening Baseline"):
        st.session_state.biz = default_state()
        st.rerun()

# --- TOP KPI METRICS ---
inv_value = money(biz["stock_units"] * biz["component_unit_cost"])
total_assets = money(biz["cash"] + inv_value + biz["equipment_assets"])
total_equity = money(biz["owner_contribution"] + biz["retained_earnings"])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Spendable Cash", f"${biz['cash']:,.2f}")
c2.metric("Component Stock", f"{biz['stock_units']} sets (${inv_value:,.2f})")
c3.metric("Equipment Assets", f"${biz['equipment_assets']:,.2f}")
c4.metric("Retained Earnings", f"${biz['retained_earnings']:,.2f}")
c5.metric("Balance Check (A - L&E)", f"${money(total_assets - biz['debt'] - total_equity):,.2f}")

tabs = st.tabs([
    "1. Inputs & Simulation Step",
    "2. Math Skills (AP Calculus)",
    "3. Report Center & Decisions",
    "4. Costed Marketing Studio",
    "5. AI Recommendations Handoff",
    "6. Ledger & Acceptance Tests",
])

# --- TAB 1: INPUTS & SIMULATION ENGINE ---
with tabs[0]:
    st.subheader("Monthly Operating Inputs & Execution (Normal Operating Mode)")
    col_in, col_cost = st.columns(2)

    with col_in:
        run_id = st.text_input("Unique Run ID", value=f"RUN-2027-{biz['state_version']:02d}")
        sim_date = st.text_input("Simulation Date (YYYY-MM-DD)", value="2027-01-31")
        price = st.number_input("Kit Price ($)", min_value=1.0, value=float(biz["base_price"]), step=5.0)
        requested = st.number_input("Requested Demand (kits)", min_value=0, value=int(biz["D0"]), step=1)
        staff_hours = st.number_input("Staff Hours / Month", min_value=0.0, value=float(biz["staff_hours"]), step=5.0)
        hours_per_unit = st.number_input("Build Hours / Kit", min_value=0.5, value=float(biz["hours_per_unit"]), step=0.5)
        restock_units = st.number_input("Restock Component Sets (paid now)", min_value=0, value=0, step=5)
        defect_rate = st.slider("Defect Rate (failed builds)", min_value=0.0, max_value=0.50, value=float(biz["defect_rate"]), step=0.01)

        approved_unspent_ads = sum(
            c["total_cost"] for c in biz["campaigns"] if c["status"] == "Launched" and not c["charged_to_ledger"]
        )
        ad_cost = st.number_input(
            "Approved Own-Business Ad Spend ($)",
            min_value=0.0,
            value=float(approved_unspent_ads),
            step=25.0,
            help="Automatically pulls any launched, uncharged campaigns from Tab 4, or enter manually.",
        )

    with col_cost:
        st.markdown("**Editable Cost Structure (ROB-3 Defaults)**")
        comp_cost = st.number_input("Component Unit Cost ($/set)", min_value=0.0, value=float(biz["component_unit_cost"]), step=1.0)
        noncomp_cost = st.number_input(
            "Non-Component Variable Cost ($/attempted kit: labor+pkg+warranty)",
            min_value=0.0,
            value=float(biz["noncomponent_var_cost"]),
            step=1.0,
        )
        fixed_cost = st.number_input("Monthly Fixed Expense ($/mo)", min_value=0.0, value=float(biz["fixed_monthly_cost"]), step=25.0)

        biz["component_unit_cost"] = comp_cost
        biz["noncomponent_var_cost"] = noncomp_cost
        biz["fixed_monthly_cost"] = fixed_cost

        derived_cap = math.floor(staff_hours / hours_per_unit) if hours_per_unit > 0 else 0
        est_attempted = min(int(requested), derived_cap, int(biz["stock_units"]) + int(restock_units))
        est_failed = math.floor(est_attempted * defect_rate)
        est_sold = est_attempted - est_failed

        st.info(
            f"**Scenario Preview (Not Committed):**\n"
            f"- Derived Staff Capacity: **{derived_cap} kits**\n"
            f"- Available Stock After Restock: **{biz['stock_units'] + int(restock_units)} sets**\n"
            f"- Attempted: **{est_attempted}** | Failed: **{est_failed}** | Sold: **{est_sold}**\n"
            f"- Total Unit Variable Cost: **${comp_cost + noncomp_cost:,.2f}/kit**"
        )

    if st.button("Approve & Advance Simulation Step", type="primary"):
        ok, msg = run_month_step(
            biz,
            run_id=run_id,
            sim_date=sim_date,
            requested=int(requested),
            price=price,
            staff_hours=staff_hours,
            hours_per_unit=hours_per_unit,
            restock_units=int(restock_units),
            defect_rate=defect_rate,
            ad_cost=ad_cost,
        )
        if ok:
            for c in biz["campaigns"]:
                if c["status"] == "Launched" and not c["charged_to_ledger"]:
                    c["charged_to_ledger"] = True
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

# --- TAB 2: AP CALCULUS PANEL ---
with tabs[1]:
    st.subheader(f"Math Skills Panel | AP Calculus ({biz['selected_level']} Mode)")

    D0 = biz["D0"]
    p0 = biz["base_price"]
    v = money(biz["component_unit_cost"] + biz["noncomponent_var_cost"])
    F = biz["fixed_monthly_cost"]
    cap = math.floor(biz["staff_hours"] / biz["hours_per_unit"])

    a = 2.0 * D0
    b = D0 / p0
    p_max = 2.0 * p0
    p_corner = (a - cap) / b if b > 0 else 0.0
    p_unconstrained_opt = (a + b * v) / (2.0 * b)

    st.markdown(
        f"**Business Question:** What kit price $p$ maximizes monthly operating profit $P(p)$ given demand "
        f"$q(p) = {a:.2f} - {b:.5f}p$ on domain $0 \\le p \\le {p_max:.2f}$ and capacity limit $q \\le {cap}$ kits?"
    )

    p_grid = np.linspace(0, p_max, 400)
    q_unconstrained = np.maximum(0.0, a - b * p_grid)
    s_constrained = np.minimum(float(cap), q_unconstrained)

    prof_unconstrained = (p_grid - v) * q_unconstrained - F
    prof_constrained = (p_grid - v) * s_constrained - F

    dprof_constrained = np.where(p_grid < p_corner, float(cap), a + b * v - 2.0 * b * p_grid)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10,
        subplot_titles=(
            "Continuous Profit P(p) vs. Price p ($/kit)",
            "Marginal Profit Rate P'(p) ($ per $1 price change)",
        ),
    )

    fig.add_trace(
        go.Scatter(x=p_grid, y=prof_constrained, name="Constrained Profit P(p)", line=dict(color="#1f77b4", width=3)),
        row=1,
        col=1,
    )
    if biz["selected_level"] == "Foundation":
        fig.add_trace(
            go.Scatter(
                x=p_grid,
                y=prof_unconstrained,
                name="Unconstrained Profit (Foundation)",
                line=dict(color="#ff7f0e", dash="dash"),
            ),
            row=1,
            col=1,
        )

    fig.add_hline(y=0, line_dash="dot", line_color="black", row=1, col=1)
    fig.add_vline(x=p_corner, line_dash="dash", line_color="#d62728", annotation_text=f"Capacity Corner p=${p_corner:.2f}", row=1, col=1)

    fig.add_trace(
        go.Scatter(x=p_grid, y=dprof_constrained, name="Derivative P'(p)", line=dict(color="#2ca02c", width=2)),
        row=2,
        col=1,
    )
    fig.add_hline(y=0, line_dash="dot", line_color="black", row=2, col=1)
    fig.add_vline(x=p_corner, line_dash="dash", line_color="#d62728", row=2, col=1)
    fig.add_trace(
        go.Scatter(
            x=[p_corner],
            y=[float(cap)],
            mode="markers",
            marker=dict(size=10, color="white", line=dict(color="#d62728", width=2)),
            name="Corner (P'(p) undefined)",
        ),
        row=2,
        col=1,
    )

    fig.update_layout(height=550, xaxis2_title="Kit Price p ($/kit)", yaxis_title="Profit ($)", yaxis2_title="P'(p) ($/($/kit))")
    st.plotly_chart(fig, use_container_width=True)

    candidates = sorted(set([0.0, round(p_corner, 2), round(p_unconstrained_opt, 2), round(p_max, 2)]))
    rows = []
    for cand_p in candidates:
        if 0 <= cand_p <= p_max:
            q_val = max(0.0, a - b * cand_p)
            s_cont = min(float(cap), q_val)
            s_int = min(cap, math.floor(q_val))
            rows.append({
                "Candidate Price ($)": cand_p,
                "Continuous Demand q(p)": round(q_val, 2),
                "Constrained Sales s(p) [Continuous]": round(s_cont, 2),
                "Continuous Profit ($)": round((cand_p - v) * s_cont - F, 2),
                "Whole-Unit Sales (Floor)": s_int,
                "Integer Profit ($)": round((cand_p - v) * s_int - F, 2),
            })
    st.markdown("**Boundary, Corner & Critical Point Comparison (Continuous vs. Whole Units):**")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    if biz["selected_level"] == "Advanced":
        st.divider()
        st.markdown("### Advanced Integration Module: Accumulated Campaign Profit Rate")
        st.markdown(
            "Models time-dependent daily revenue rate $r(t) = r_0 + r_1 t$ and cost rate $c(t) = c_0 + c_1 t$ "
            "($/day) over campaign window $0 \\le t \\le T$ days (isolated rate exercise; separate from monthly ledger):"
        )
        ic1, ic2, ic3, ic4, ic5 = st.columns(5)
        r0 = ic1.number_input("r0 ($/day)", value=100.0)
        r1 = ic2.number_input("r1 ($/day^2)", value=20.0)
        c0 = ic3.number_input("c0 ($/day)", value=60.0)
        c1 = ic4.number_input("c1 ($/day^2)", value=5.0)
        T = ic5.number_input("Horizon T (days)", min_value=1.0, value=10.0)

        acc_rev = r0 * T + 0.5 * r1 * (T ** 2)
        acc_cost = c0 * T + 0.5 * c1 * (T ** 2)
        acc_prof = acc_rev - acc_cost
        st.success(
            f"**Definite Integral Results on [0, {T:.0f}] days:** "
            f"Accumulated Revenue = **${acc_rev:,.2f}** | "
            f"Accumulated Cost = **${acc_cost:,.2f}** | "
            f"Net Accumulated Profit = **${acc_prof:,.2f}**"
        )

# --- TAB 3: REPORT CENTER & DECISION MEMO ---
with tabs[2]:
    st.subheader(f"Reconciled Report Center | Snapshot {biz['snapshot_id']} (v{biz['state_version']})")
    ops_entries = [e for e in biz["ledger"] if e["event_type"] == "MONTHLY_OPERATIONS"]
    restock_entries = [e for e in biz["ledger"] if e["event_type"] == "INVENTORY_RESTOCK"]

    if not ops_entries:
        st.info("No completed months in the ledger yet. Commit at least one month in Tab 1 to generate reconciled reports.")
    else:
        df_ops = pd.DataFrame(ops_entries)
        tot_rev = money(df_ops["revenue"].sum())
        tot_comp = money(df_ops["component_expense"].sum())
        tot_noncomp = money(df_ops["noncomponent_var_expense"].sum())
        tot_var = money(tot_comp + tot_noncomp)
        tot_fixed = money(df_ops["fixed_expense"].sum())
        tot_mkt = money(df_ops["marketing_expense"].sum())
        tot_profit = money(df_ops["operating_profit"].sum())
        tot_restock_cash = money(sum(-r["amount"] for r in restock_entries))

        r1, r2 = st.columns(2)
        with r1:
            st.markdown("### 1. Income Statement (Actual Ledger)")
            inc_df = pd.DataFrame([
                {"Line Item": "Kit Sales Revenue", "Amount ($)": tot_rev},
                {"Line Item": "Consumed Component Expense", "Amount ($)": -tot_comp},
                {"Line Item": "Non-Component Variable Expense", "Amount ($)": -tot_noncomp},
                {"Line Item": "Gross Profit", "Amount ($)": money(tot_rev - tot_var)},
                {"Line Item": "Monthly Fixed Operating Expense", "Amount ($)": -tot_fixed},
                {"Line Item": "Own-Business Marketing Expense", "Amount ($)": -tot_mkt},
                {"Line Item": "Net Operating Profit", "Amount ($)": tot_profit},
            ])
            st.dataframe(inc_df, use_container_width=True, hide_index=True)

            st.markdown("### 2. Simplified Balance Sheet (Reconciled)")
            bs_df = pd.DataFrame([
                {"Account": "Assets: Spendable Cash", "Amount ($)": biz["cash"]},
                {"Account": f"Assets: Component Inventory ({biz['stock_units']} sets)", "Amount ($)": inv_value},
                {"Account": "Assets: Tools & Test Equipment", "Amount ($)": biz["equipment_assets"]},
                {"Account": "Total Assets", "Amount ($)": total_assets},
                {"Account": "Liabilities: Simulated Debt", "Amount ($)": biz["debt"]},
                {"Account": "Equity: Owner Contribution", "Amount ($)": biz["owner_contribution"]},
                {"Account": "Equity: Retained Earnings", "Amount ($)": biz["retained_earnings"]},
                {"Account": "Total Liabilities & Equity", "Amount ($)": money(biz["debt"] + total_equity)},
            ])
            st.dataframe(bs_df, use_container_width=True, hide_index=True)

        with r2:
            st.markdown("### 3. Cash-Flow Summary (Actual Ledger)")
            cf_df = pd.DataFrame([
                {"Cash Flow Item": "Opening Post-Startup Cash", "Amount ($)": biz["opening_cash"]},
                {"Cash Flow Item": "Cash Inflows from Kit Sales", "Amount ($)": tot_rev},
                {"Cash Flow Item": "Cash Outflows: Non-Component Variable", "Amount ($)": -tot_noncomp},
                {"Cash Flow Item": "Cash Outflows: Fixed Operating", "Amount ($)": -tot_fixed},
                {"Cash Flow Item": "Cash Outflows: Marketing", "Amount ($)": -tot_mkt},
                {"Cash Flow Item": "Cash Outflows: Inventory Restocks", "Amount ($)": -tot_restock_cash},
                {"Cash Flow Item": "Closing Cash Balance", "Amount ($)": biz["cash"]},
            ])
            st.dataframe(cf_df, use_container_width=True, hide_index=True)

            st.markdown("### 4. Operations & Quality Summary")
            ops_sum_df = pd.DataFrame([
                {"Metric": "Total Requested Demand (kits)", "Value": int(df_ops["requested"].sum())},
                {"Metric": "Total Attempted Builds (kits)", "Value": int(df_ops["attempted"].sum())},
                {"Metric": "Total Failed / Defective Kits", "Value": int(df_ops["failed_kits"].sum())},
                {"Metric": "Total Completed & Sold Kits", "Value": int(df_ops["sold"].sum())},
                {"Metric": "Total Unserved Demand (kits)", "Value": int(df_ops["unserved_demand"].sum())},
            ])
            st.dataframe(ops_sum_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Scenario Forecast (Baseline 1.00x / Upside 1.10x / Downside 0.90x)")
    st.caption("Scenario assumptions only (not confidence bounds and not written to the actual ledger).")
    base_d = biz["D0"]
    cur_p = biz["base_price"]
    cur_v = money(biz["component_unit_cost"] + biz["noncomponent_var_cost"])
    cur_f = biz["fixed_monthly_cost"]
    cur_cap = math.floor(biz["staff_hours"] / biz["hours_per_unit"])
    scen_rows = []
    for label, mult in [("Downside (0.90x)", 0.90), ("Baseline (1.00x)", 1.00), ("Upside (1.10x)", 1.10)]:
        req_s = math.floor(base_d * mult)
        sold_s = min(req_s, cur_cap, biz["stock_units"])
        rev_s = money(sold_s * cur_p)
        prof_s = money(rev_s - sold_s * cur_v - cur_f)
        scen_rows.append({
            "Scenario": label,
            "Projected Demand": req_s,
            "Capacity & Stock Capped Sales": sold_s,
            "Projected Revenue ($)": rev_s,
            "Projected Operating Profit ($)": prof_s,
        })
    st.dataframe(pd.DataFrame(scen_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Two-Report Decision Memo Log")
    with st.form("decision_memo_form"):
        d_q = st.text_input("Decision Question", placeholder="Should we raise kit price from $120 to $150 or add staff hours?")
        d_reports = st.multiselect(
            "Reports Cited (Select at least 2)",
            ["Income Statement", "Cash-Flow Summary", "Operations Summary", "Simplified Balance Sheet", "Scenario Forecast"],
        )
        d_choice = st.text_input("Chosen Action & Alternatives Compared")
        d_pred = st.text_input("Measurable Prediction (with units)")
        d_owner = st.text_input("Owner & Independent Student Checker")
        if st.form_submit_button("Save Decision Memo"):
            if len(d_reports) < 2:
                st.error("Please cite at least two reports before saving your Decision Memo.")
            else:
                biz["decisions"].append({
                    "decision_id": f"DEC-{len(biz['decisions']) + 1:02d}",
                    "snapshot_id": biz["snapshot_id"],
                    "state_version": biz["state_version"],
                    "question": d_q,
                    "reports_cited": ", ".join(d_reports),
                    "chosen_action": d_choice,
                    "prediction": d_pred,
                    "owner_and_checker": d_owner,
                })
                st.success("Decision Memo saved to snapshot.")
                st.rerun()

    if biz["decisions"]:
        st.dataframe(pd.DataFrame(biz["decisions"]), use_container_width=True)

# --- TAB 4: COSTED MARKETING STUDIO ---
with tabs[3]:
    st.subheader("Costed Marketing Studio (Fictional Simulation Only)")
    st.caption("Drafts require student review before simulated launch. Each Campaign ID is charged once.")

    mc1, mc2 = st.columns(2)
    with mc1:
        camp_id = st.text_input("Unique Campaign ID", value=f"CAMP-ROB-{len(biz['campaigns']) + 1:02d}")
        offering = st.selectbox(
            "ROB-3 Offering",
            ["Introductory robot kit", "Sensor upgrade", "Repair service"],
        )
        audience = st.text_input("Target Audience", value="High school robotics clubs & STEM hobbyists")
        headline = st.text_input("Approved Truthful Claim / Headline", value="Build & calibrate real ultrasonic sensors with step-by-step kits")
        design_hrs = st.number_input("Design Labor Hours", min_value=0.0, value=2.0, step=0.5)
        design_rate = st.number_input("Design Hourly Rate ($/hr)", min_value=0.0, value=15.0, step=5.0)
        assets_cost = st.number_input("Licensed Assets Cost ($)", min_value=0.0, value=10.0, step=5.0)
        print_qty = st.number_input("Print Quantity (flyers)", min_value=0, value=100, step=25)
        print_unit = st.number_input("Print Unit Cost ($/flyer)", min_value=0.0, value=0.25, step=0.05)
        dist_place = st.number_input("Distribution & Digital Placement ($)", min_value=0.0, value=35.0, step=5.0)

    with mc2:
        total_camp_cost = money(design_hrs * design_rate + assets_cost + print_qty * print_unit + dist_place)
        st.metric("Total Itemized Campaign Cost", f"${total_camp_cost:,.2f}")
        st.markdown("**Printable Flyer Preview:**")
        flyer_text = (
            f"=== DEMONSTRATION FLYER (NO REAL OFFERS) ===\n"
            f"Studio: {biz['team_id']} Robotics Kit & Repair Studio\n"
            f"Offering: {offering} (${biz['base_price']:,.2f})\n"
            f"Audience: {audience}\n"
            f"Message: {headline}\n"
            f"Contact: demo-robotics@school-sim.example\n"
            f"============================================"
        )
        st.code(flyer_text, language="text")

        reviewer_ok = st.checkbox("Independent Reviewer checked truthful claims, accessibility, and itemized budget")
        if st.button("Approve & Launch Simulated Campaign", type="primary"):
            if any(c["campaign_id"] == camp_id for c in biz["campaigns"]):
                st.error(f"Duplicate campaign_id '{camp_id}' rejected. A campaign can only be launched once.")
            elif not reviewer_ok:
                st.error("Reviewer verification checkbox must be checked before launching.")
            else:
                biz["campaigns"].append({
                    "campaign_id": camp_id,
                    "offering": offering,
                    "audience": audience,
                    "total_cost": total_camp_cost,
                    "status": "Launched",
                    "charged_to_ledger": False,
                    "state_version": biz["state_version"],
                })
                st.success(
                    f"Campaign {camp_id} (${total_camp_cost:,.2f}) approved! "
                    f"It is now queued in Tab 1 'Approved Own-Business Ad Spend' for your next simulation step."
                )
                st.rerun()

    if biz["campaigns"]:
        st.markdown("**Campaign Log:**")
        st.dataframe(pd.DataFrame(biz["campaigns"]), use_container_width=True)

# --- TAB 5: AI RECOMMENDATIONS HANDOFF ---
with tabs[4]:
    st.subheader("Departmental AI Assistants Handoff (Manual Import & Student Approval)")
    st.caption(
        "Workflow: Export Snapshot JSON (Sidebar) -> Paste into Finance / Operations / Marketing / Reviewer Gem -> "
        "Record recommendation below -> Verify math -> Approve or Reject."
    )

    with st.form("ai_handoff_form"):
        ai_role = st.selectbox("Departmental Role", ["Finance", "Operations", "Market and Marketing", "Independent Reviewer"])
        rec_snap_ver = st.number_input("Snapshot State Version Cited by AI", min_value=1, value=int(biz["state_version"]), step=1)
        ai_question = st.text_input("Question Asked", value="Compare current $120 price with a 10% price increase.")
        ai_summary = st.text_area("AI Proposed Changes & Calculations Summary")
        student_check = st.text_input("Independent Student Math Check (Required before approval)")
        action_choice = st.radio("Human Decision", ["Approve Proposal", "Reject Proposal"], horizontal=True)

        if st.form_submit_button("Log & Validate AI Recommendation"):
            if rec_snap_ver != biz["state_version"]:
                st.error(
                    f"Stale or mismatched version rejected! AI cited v{rec_snap_ver}, "
                    f"but current business state is v{biz['state_version']}."
                )
            elif action_choice == "Approve Proposal" and not student_check.strip():
                st.error("You must enter an independent student math check before approving any AI proposal.")
            else:
                status_label = "Approved" if action_choice == "Approve Proposal" else "Rejected"
                biz["recommendations"].append({
                    "role": ai_role,
                    "state_version": rec_snap_ver,
                    "question": ai_question,
                    "proposed_changes": ai_summary,
                    "student_verification": student_check,
                    "approval_status": status_label,
                })
                st.success(f"{ai_role} recommendation logged as {status_label} for state v{rec_snap_ver}.")
                st.rerun()

    if biz["recommendations"]:
        st.dataframe(pd.DataFrame(biz["recommendations"]), use_container_width=True)

# --- TAB 6: LEDGER & ACCEPTANCE TESTS ---
with tabs[5]:
    st.subheader("Dated Event Ledger")
    if biz["ledger"]:
        df_ledger = pd.DataFrame(biz["ledger"])
        st.dataframe(df_ledger, use_container_width=True)
        st.download_button(
            "Export Ledger CSV",
            data=df_ledger.to_csv(index=False),
            file_name=f"{biz['team_id']}_ledger_v{biz['state_version']}.csv",
            mime="text/csv",
        )
    else:
        st.write("No simulation steps committed yet. Run a month in Tab 1 or run the Acceptance Checks below.")

    st.divider()
    st.subheader("Automated Acceptance & Fixture Checks")
    if st.button("Run All Acceptance Checks"):
        results = []

        # Test 1: Zero sales check
        s0 = default_state()
        run_month_step(s0, "T-ZERO", "2027-01-31", requested=0, price=120.0, staff_hours=90.0, hours_per_unit=3.0, restock_units=0, defect_rate=0.0, ad_cost=0.0)
        last0 = s0["ledger"][-1]
        results.append({
            "Test": "Zero Sales (requested=0)",
            "Expected": "Rev=$0, Var=$0, Profit=-$600",
            "Actual": f"Rev=${last0['revenue']:.0f}, Var=${last0['component_expense'] + last0['noncomponent_var_expense']:.0f}, Profit=${last0['operating_profit']:.0f}",
            "Status": "PASS" if (last0["revenue"] == 0 and last0["operating_profit"] == -600.0) else "FAIL",
        })

        # Test 2: ROB Business-Specific Stock & Defect Test
        s_rob = default_state()
        s_rob["stock_units"] = 10
        run_month_step(s_rob, "T-ROB", "2027-01-31", requested=40, price=120.0, staff_hours=90.0, hours_per_unit=3.0, restock_units=0, defect_rate=0.0, ad_cost=0.0)
        last_rob = s_rob["ledger"][-1]
        results.append({
            "Test": "ROB Stock Cap (stock=10, restock=0)",
            "Expected": "Sold=10, Rev=$1200, Profit=-$50, Stock=0",
            "Actual": f"Sold={last_rob['sold']}, Rev=${last_rob['revenue']:.0f}, Profit=${last_rob['operating_profit']:.0f}, Stock={s_rob['stock_units']}",
            "Status": "PASS" if (last_rob["sold"] == 10 and last_rob["operating_profit"] == -50.0 and s_rob["stock_units"] == 0) else "FAIL",
        })

        # Test 3: 3-Month Fixture Replay
        s_fix = default_state()
        fixture_rows = [
            ("2027-01", 40, 30, 0, 3600.0, 2550.0, 1050.0, 6950.0, 70),
            ("2027-02", 44, 30, 100, 3600.0, 2650.0, 950.0, 8800.0, 40),
            ("2027-03", 36, 22, 0, 2640.0, 2030.0, 610.0, 10070.0, 18),
        ]
        fixture_ok = True
        for m, req, cap_ov, ad, exp_rev, exp_tot_exp, exp_prof, exp_cash, exp_stk in fixture_rows:
            run_month_step(s_fix, f"FIX-{m}", f"{m}-28", requested=req, price=120.0, staff_hours=90.0, hours_per_unit=3.0, restock_units=0, defect_rate=0.0, ad_cost=ad, capacity_override=cap_ov)
            row_l = s_fix["ledger"][-1]
            tot_exp = money(row_l["component_expense"] + row_l["noncomponent_var_expense"] + row_l["fixed_expense"] + row_l["marketing_expense"])
            if not (
                row_l["revenue"] == exp_rev
                and tot_exp == exp_tot_exp
                and row_l["operating_profit"] == exp_prof
                and s_fix["cash"] == exp_cash
                and s_fix["stock_units"] == exp_stk
            ):
                fixture_ok = False
        results.append({
            "Test": "ROB 3-Month Fixture Replay",
            "Expected": "M3 Cash=$10,070, Stock=18",
            "Actual": f"M3 Cash=${s_fix['cash']:,.2f}, Stock={s_fix['stock_units']}",
            "Status": "PASS" if fixture_ok else "FAIL",
        })

        # Test 4: Duplicate run_id protection
        dup_ok, _ = run_month_step(s_fix, "FIX-2027-03", "2027-03-28", requested=36, price=120.0, staff_hours=90.0, hours_per_unit=3.0, restock_units=0, defect_rate=0.0, ad_cost=0, capacity_override=22)
        results.append({
            "Test": "Duplicate Run ID Rejection",
            "Expected": "Rejected (False)",
            "Actual": f"Accepted={dup_ok}",
            "Status": "PASS" if not dup_ok else "FAIL",
        })

        # Test 5: AP Calculus Course Acceptance Check
        a_t, b_t, v_t, F_t, cap_t = 120.0, 2.0, 10.0, 500.0, 40.0
        p_corn_t = (a_t - cap_t) / b_t
        prof_corn_t = (p_corn_t - v_t) * cap_t - F_t
        int_prof_t = (100 * 10 + 0.5 * 20 * 100) - (60 * 10 + 0.5 * 5 * 100)
        results.append({
            "Test": "AP Calculus Constrained Opt & Integral Fixture",
            "Expected": "Opt p=$40, Profit=$700, Integral=$1150",
            "Actual": f"Opt p=${p_corn_t:.0f}, Profit=${prof_corn_t:.0f}, Integral=${int_prof_t:.0f}",
            "Status": "PASS" if (p_corn_t == 40.0 and prof_corn_t == 700.0 and int_prof_t == 1150.0) else "FAIL",
        })

        st.table(pd.DataFrame(results))
