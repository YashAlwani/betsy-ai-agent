import time

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(
    page_title="Betsy - Procurement Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)


def fetch(path: str):
    try:
        r = httpx.get(f"{API}{path}", timeout=3.0)
        r.raise_for_status()
        return r.json()
    except httpx.ConnectError:
        st.error("Cannot reach Betsy mock server at localhost:8000. Is it running?")
        return None
    except Exception as e:
        st.error(f"API error on {path}: {e}")
        return None


def post(path: str):
    try:
        r = httpx.post(f"{API}{path}", timeout=3.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"POST error on {path}: {e}")
        return None


# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.title("Betsy Control Panel")

scenario_info = fetch("/api/scenario") or {}
active = scenario_info.get("active", "unknown")
st.sidebar.markdown(f"**Active scenario:** `{active}`")

st.sidebar.markdown("---")
scenario_options = ["reset", "stockout_warning", "price_spike", "duplicate_invoice", "supplier_oos"]
selected = st.sidebar.selectbox("Select Scenario", scenario_options)

if st.sidebar.button("Inject Scenario", type="primary"):
    result = post(f"/api/scenario/{selected}")
    if result:
        st.sidebar.success(result.get("description") or result.get("message", "Done"))
        st.rerun()

st.sidebar.markdown("---")
auto_refresh = st.sidebar.toggle("Auto-refresh (5s)", value=False)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Betsy — Procurement Intelligence Dashboard")
st.caption(f"Mock server: {API}  |  Scenario: **{active}**")

# ── Load data ─────────────────────────────────────────────────────────────────
inventory = fetch("/api/inventory")
suppliers = fetch("/api/suppliers")
orders = fetch("/api/purchase-orders")
invoices = fetch("/api/invoices")
duplicates = fetch("/api/invoices/duplicates")
agent_log = fetch("/api/agent-log")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Inventory Health",
    "Supplier Scoreboard",
    "Purchase Orders",
    "Invoice Reconciliation",
    "Agent Decision Log",
])

# ── Tab 1: Inventory ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Inventory Status")

    if inventory:
        df = pd.DataFrame(inventory)
        df["days_until_stockout"] = (df["current_stock"] / df["daily_usage_avg"]).round(1)
        df["status"] = df.apply(
            lambda r: "CRITICAL" if r["current_stock"] < r["reorder_point"]
            else "WARNING" if r["current_stock"] < r["reorder_point"] * 1.2
            else "OK",
            axis=1,
        )

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total SKUs", len(df))
        col2.metric("Below Reorder", int((df["status"] != "OK").sum()))
        col3.metric("Critical", int((df["status"] == "CRITICAL").sum()))
        col4.metric("Avg Days of Stock", f"{df['days_until_stockout'].mean():.1f}")

        st.markdown("---")

        def _color_status(val):
            return {
                "CRITICAL": "background-color: #ffcccc; color: #990000; font-weight: bold",
                "WARNING": "background-color: #fff3cc; color: #664d00",
                "OK": "background-color: #d4edda; color: #155724",
            }.get(val, "")

        display_cols = ["sku_id", "name", "category", "current_stock", "reorder_point",
                        "days_until_stockout", "critical", "status"]
        try:
            styled = df[display_cols].style.map(_color_status, subset=["status"])
        except AttributeError:
            styled = df[display_cols].style.applymap(_color_status, subset=["status"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.markdown("---")
        fig = go.Figure()
        fig.add_bar(
            name="Current Stock",
            x=df["sku_id"],
            y=df["current_stock"],
            marker_color="steelblue",
            hovertext=df["name"],
        )
        fig.add_bar(
            name="Reorder Point",
            x=df["sku_id"],
            y=df["reorder_point"],
            marker_color="crimson",
            opacity=0.55,
        )
        fig.update_layout(
            barmode="overlay",
            title="Current Stock vs Reorder Point",
            xaxis_title="SKU",
            yaxis_title="Units",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Tab 2: Suppliers ──────────────────────────────────────────────────────────
with tab2:
    st.subheader("Supplier Scoreboard")

    if suppliers:
        rows = []
        for sup in suppliers:
            catalog = sup.get("catalog", {})
            avg_price = sum(v["unit_price"] for v in catalog.values()) / len(catalog) if catalog else 0
            avg_lead = sum(v["lead_days"] for v in catalog.values()) / len(catalog) if catalog else 0
            rows.append({
                "ID": sup["supplier_id"],
                "Name": sup["name"],
                "Reliability": sup["reliability_score"],
                "Avg Lead (days)": round(avg_lead, 1),
                "SKUs Supplied": len(catalog),
                "Available": "Yes" if sup["availability"] else "No",
                "Payment Terms": sup["payment_terms"],
            })
        df_sup = pd.DataFrame(rows)

        def _color_avail(val):
            return "color: #155724; font-weight: bold" if val == "Yes" else "color: #990000; font-weight: bold"

        def _color_reliability(val):
            if val >= 0.93:
                return "background-color: #d4edda"
            if val >= 0.85:
                return "background-color: #fff3cc"
            return "background-color: #ffcccc"

        try:
            styled_sup = (
                df_sup.style
                .map(_color_avail, subset=["Available"])
                .map(_color_reliability, subset=["Reliability"])
            )
        except AttributeError:
            styled_sup = (
                df_sup.style
                .applymap(_color_avail, subset=["Available"])
                .applymap(_color_reliability, subset=["Reliability"])
            )
        st.dataframe(styled_sup, use_container_width=True, hide_index=True)

        st.markdown("---")
        fig2 = go.Figure()
        fig2.add_bar(
            name="Reliability Score",
            x=df_sup["Name"],
            y=df_sup["Reliability"],
            marker_color=["#28a745" if v == "Yes" else "#dc3545" for v in df_sup["Available"]],
            text=df_sup["Reliability"].apply(lambda v: f"{v:.0%}"),
            textposition="outside",
        )
        fig2.update_layout(
            title="Supplier Reliability (green = available, red = unavailable)",
            yaxis=dict(range=[0, 1.1], tickformat=".0%"),
            height=360,
        )
        st.plotly_chart(fig2, use_container_width=True)

# ── Tab 3: Purchase Orders ────────────────────────────────────────────────────
with tab3:
    st.subheader("Purchase Orders")

    if orders:
        df_po = pd.DataFrame(orders)

        status_counts = df_po["status"].value_counts()
        cols_po = st.columns(max(len(status_counts), 1))
        for col, (status, count) in zip(cols_po, status_counts.items()):
            col.metric(status.replace("_", " ").title(), int(count))

        st.markdown("---")

        _po_status_colors = {
            "pending_approval": "background-color: #fff3cc",
            "approved": "background-color: #d4edda",
            "in_transit": "background-color: #cce5ff",
            "delivered": "background-color: #e8e8e8",
            "cancelled": "background-color: #f8d7da",
        }

        def _color_po_status(val):
            return _po_status_colors.get(val, "")

        display_po = ["po_id", "supplier_id", "sku_id", "quantity", "total_amount",
                      "order_date", "expected_delivery", "status", "requested_by"]
        avail_cols = [c for c in display_po if c in df_po.columns]
        try:
            styled_po = df_po[avail_cols].style.map(_color_po_status, subset=["status"])
        except AttributeError:
            styled_po = df_po[avail_cols].style.applymap(_color_po_status, subset=["status"])
        st.dataframe(styled_po, use_container_width=True, hide_index=True)

        total_spend = df_po["total_amount"].sum()
        pending_val = df_po[df_po["status"] == "pending_approval"]["total_amount"].sum()
        st.markdown(f"**Total spend:** ${total_spend:,.2f}  |  **Pending approval:** ${pending_val:,.2f}")

# ── Tab 4: Invoice Reconciliation ─────────────────────────────────────────────
with tab4:
    st.subheader("Invoice Reconciliation")

    if invoices and duplicates is not None:
        total_at_risk = sum(d["amount"] for d in duplicates)
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Total Invoices", len(invoices))
        col_b.metric("Duplicates Detected", len(duplicates))
        col_c.metric("Amount at Risk", f"${total_at_risk:,.2f}")

        if duplicates:
            st.warning(f"{len(duplicates)} potential duplicate invoice(s) detected — review before payment!")
            df_dupes = pd.DataFrame(duplicates)
            st.dataframe(df_dupes, use_container_width=True, hide_index=True)

        st.markdown("---")

        dup_ids = set()
        for d in (duplicates or []):
            dup_ids.add(d["invoice_1"])
            dup_ids.add(d["invoice_2"])

        df_inv = pd.DataFrame(invoices)
        df_inv["flagged"] = df_inv["invoice_id"].apply(lambda x: "DUPLICATE" if x in dup_ids else "OK")

        def _color_inv_flag(val):
            return "background-color: #ffcccc; font-weight: bold" if val == "DUPLICATE" else ""

        try:
            styled_inv = df_inv.style.map(_color_inv_flag, subset=["flagged"])
        except AttributeError:
            styled_inv = df_inv.style.applymap(_color_inv_flag, subset=["flagged"])
        st.dataframe(styled_inv, use_container_width=True, hide_index=True)

# ── Tab 5: Agent Decision Log ─────────────────────────────────────────────────
with tab5:
    st.subheader("Agent Decision Log")

    if not agent_log:
        st.info("No decisions logged yet. Agent will populate this when running (Week 2+).")
    else:
        st.markdown(f"**{len(agent_log)} decision(s) recorded**")
        for entry in reversed(agent_log):
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            trigger = entry.get("trigger", "unknown")
            with st.expander(f"{ts}  —  {trigger}", expanded=False):
                col_l, col_r = st.columns([4, 1])
                with col_l:
                    st.markdown(f"**Analysis:** {entry.get('analysis', '')}")
                    st.markdown(f"**Decision:** {entry.get('decision', '')}")
                    if entry.get("metadata"):
                        st.json(entry["metadata"])
                with col_r:
                    conf = entry.get("confidence", 0)
                    st.metric("Confidence", f"{conf:.0%}")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(5)
    st.rerun()
