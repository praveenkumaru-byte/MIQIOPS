# views/inventory.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

def render(access_code: str = "R") -> None:
    """
    Supply Chain > Inventory Management
    
    Features:
    - Real-time stock monitoring vs Safety Stock.
    - Purchase Order tracking.
    - RW Access: Allows triggering 'Reorder' workflows.
    """
    st.markdown("### Inventory & Supply Chain")

    # --- 1. SESSION STATE (Mock Data Persistence) ---
    if "inventory_db" not in st.session_state:
        st.session_state.inventory_db = [
            {"Part #": "XG-112", "Desc": "Gasket, High Temp", "Category": "Consumables", "Stock": 45, "Safety Stock": 20, "On Order": 0, "UnitCost": 150},
            {"Part #": "BL-441", "Desc": "Turbine Blade L-1", "Category": "Spares", "Stock": 4, "Safety Stock": 12, "On Order": 20, "UnitCost": 12500},
            {"Part #": "FL-992", "Desc": "Lube Oil Filter", "Category": "Consumables", "Stock": 15, "Safety Stock": 10, "On Order": 5, "UnitCost": 85},
            {"Part #": "VAL-303", "Desc": "Control Valve, 3-Way", "Category": "Valves", "Stock": 1, "Safety Stock": 2, "On Order": 0, "UnitCost": 4200},
            {"Part #": "SEN-001", "Desc": "Vibration Sensor", "Category": "I&C", "Stock": 8, "Safety Stock": 5, "On Order": 0, "UnitCost": 1200}
        ]

    if "po_db" not in st.session_state:
        st.session_state.po_db = [
            {"PO #": "PO-9921", "Vendor": "General Electric", "Value": 125000, "Status": "Approved", "ETA": "2026-02-15"},
            {"PO #": "PO-9925", "Vendor": "Grainger", "Value": 4200, "Status": "Shipped", "ETA": "2026-01-28"},
            {"PO #": "PO-9930", "Vendor": "Emerson", "Value": 18500, "Status": "Pending", "ETA": "TBD"}
        ]

    df_inv = pd.DataFrame(st.session_state.inventory_db)
    df_po = pd.DataFrame(st.session_state.po_db)

    # --- 2. KPI CALCULATIONS ---
    # Logic: Identify "Critical" items (Stock < Safety Stock)
    low_stock_df = df_inv[df_inv["Stock"] < df_inv["Safety Stock"]]
    low_stock_count = len(low_stock_df)
    
    total_value = (df_inv["Stock"] * df_inv["UnitCost"]).sum()
    open_po_value = df_po[df_po["Status"] != "Received"]["Value"].sum()

    # --- 3. KPI CARDS ---
    k1, k2, k3, k4 = st.columns(4)
    
    with k1:
        st.markdown(f"""
        <div class="miq-kpi-card">
            <div class="miq-kpi-label">Total Inventory Value</div>
            <div class="miq-kpi-value">${total_value:,.0f}</div>
            <div class="miq-kpi-sub">{len(df_inv)} Unique SKUs</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        # Red card if items are critical
        card_style = "kpi-red" if low_stock_count > 0 else "kpi-green"
        st.markdown(f"""
        <div class="miq-kpi-card {card_style}">
            <div class="miq-kpi-label">Low Stock Alerts</div>
            <div class="miq-kpi-value">{low_stock_count}</div>
            <div class="miq-kpi-sub">Items below Safety Stock</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="miq-kpi-card">
            <div class="miq-kpi-label">Open PO Value</div>
            <div class="miq-kpi-value">${open_po_value:,.0f}</div>
            <div class="miq-kpi-sub">{len(df_po)} Active Orders</div>
        </div>
        """, unsafe_allow_html=True)
        
    with k4:
        st.markdown(f"""
        <div class="miq-kpi-card kpi-blue">
            <div class="miq-kpi-label">Service Level</div>
            <div class="miq-kpi-value">94.5%</div>
            <div class="miq-kpi-sub">Order Fill Rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # --- 4. TABS ---
    tab1, tab2, tab3 = st.tabs(["Stock Levels", "Purchase Orders", "Parts Transaction"])
    
    # TAB 1: INVENTORY LEVELS
    with tab1:
        st.subheader("Warehouse Levels vs Safety Stock")
        
        col_chart, col_action = st.columns([3, 1])
        
        with col_chart:
            # Sort by "Criticality" (Ratio of Stock to Safety) to show worst items first
            df_inv["Coverage"] = df_inv["Stock"] / df_inv["Safety Stock"]
            df_chart = df_inv.sort_values("Coverage")
            
            fig = px.bar(
                df_chart, 
                x="Part #", 
                y=["Stock", "Safety Stock"], 
                barmode="group",
                title="Stock vs. Safety Threshold (Sorted by Criticality)",
                color_discrete_map={"Stock": "#3b82f6", "Safety Stock": "#ef4444"}
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_action:
            if low_stock_count > 0:
                st.error(f"⚠️ {low_stock_count} Critical Items")
                for _, row in low_stock_df.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['Part #']}**")
                        st.caption(f"{row['Desc']}")
                        st.markdown(f"Stock: **{row['Stock']}** / {row['Safety Stock']}")
                        
                        if access_code == "RW":
                            if st.button("Reorder", key=f"reorder_{row['Part #']}"):
                                st.toast(f"Purchase Requisition generated for {row['Part #']}!")
                        else:
                            st.caption("🔒 Read-only")

        # Full Table
        st.dataframe(
            df_inv, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "UnitCost": st.column_config.NumberColumn("Unit Cost", format="$%.2f"),
                "Coverage": None # Hide helper column
            }
        )

    # TAB 2: PURCHASE ORDERS
    with tab2:
        st.subheader("Active Purchase Orders")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(
                df_po, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Value": st.column_config.NumberColumn("Value", format="$%.2f")
                }
            )
        with c2:
            if access_code == "RW":
                with st.container(border=True):
                    st.markdown("**Actions**")
                    st.button("➕ Create PO", use_container_width=True)
                    st.button("📥 Receive Goods", use_container_width=True)

    # TAB 3: TRANSACTIONS (Placeholder)
    with tab3:
        st.subheader("Recent Parts Movement")
        st.info("✅ No new goods receipts or issues in the last 24 hours.")
        
        # Mock Transaction Log
        transactions = [
            {"Date": "2026-02-02 09:15", "Type": "Issue", "Part #": "XG-112", "Qty": -5, "Ref": "WO-4412"},
            {"Date": "2026-02-01 14:30", "Type": "Receipt", "Part #": "FL-992", "Qty": 10, "Ref": "PO-9918"}
        ]
        st.dataframe(pd.DataFrame(transactions), use_container_width=True, hide_index=True)