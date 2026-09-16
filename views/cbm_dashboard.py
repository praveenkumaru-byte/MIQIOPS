# views/cbm.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def render(access_code: str = "R") -> None:
    """
    Quality & Compliance > Condition Based Maintenance (CBM)
    
    Modules:
    - Departures (Non-Conformances)
    - CBMO (Condition Based Maintenance Optimization)
    - CBRL (Component Repair)
    - Rotor EOL (End of Life)
    """
    st.markdown("### 🧬 Condition Based Maintenance (CBM)")

    # --- 1. MOCK DATA ---
    if "cbm_data" not in st.session_state:
        st.session_state.cbm_data = [
            {"ID": "DEP-001", "Asset": "Gas Turbine 1", "Type": "Departure", "Component": "Combustor Basket", "Issue": "Thermal cracking > 2mm", "Status": "Open", "Criticality": "High", "Date": "2026-01-15"},
            {"ID": "DEP-002", "Asset": "Steam Turbine A", "Type": "Departure", "Component": "L-0 Blade", "Issue": "Erosion leading edge", "Status": "Review", "Criticality": "Medium", "Date": "2026-01-20"},
            {"ID": "INSP-104", "Asset": "Generator 2", "Type": "Inspection", "Component": "Rotor Windings", "Issue": "Short turn detected", "Status": "Closed", "Criticality": "Low", "Date": "2025-12-10"},
            {"ID": "EOL-99", "Asset": "Gas Turbine 1", "Type": "Rotor EOL", "Component": "Compressor Rotor", "Issue": "End of Life Limit Reached", "Status": "Pending CXO", "Criticality": "Critical", "Date": "2026-02-01"}
        ]

    df_cbm = pd.DataFrame(st.session_state.cbm_data)

    # --- 2. KPI HEADER ---
    active_deps = len(df_cbm[(df_cbm["Type"] == "Departure") & (df_cbm["Status"] != "Closed")])
    crit_eol = len(df_cbm[df_cbm["Type"] == "Rotor EOL"])
    
    k1, k2, k3 = st.columns(3)
    with k1:
        st.markdown(f"""
        <div class="miq-kpi-card kpi-amber">
            <div class="miq-kpi-label">Active Departures</div>
            <div class="miq-kpi-value">{active_deps}</div>
            <div class="miq-kpi-sub">Open Non-Conformances</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="miq-kpi-card">
            <div class="miq-kpi-label">Inspections (YTD)</div>
            <div class="miq-kpi-value">14</div>
            <div class="miq-kpi-sub">CBMO Rounds Complete</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        # Dynamic styling for Critical EOL
        card_style = "kpi-red" if crit_eol > 0 else "kpi-green"
        st.markdown(f"""
        <div class="miq-kpi-card {card_style}">
            <div class="miq-kpi-label">Rotor EOL Risks</div>
            <div class="miq-kpi-value">{crit_eol}</div>
            <div class="miq-kpi-sub">Pending Executive Review</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # --- 3. TABS ---
    t1, t2, t3, t4, t5 = st.tabs(["Departures", "CBMO Inspections", "CBMO Dispositions", "CBRL Tracking", "Rotor EOL"])
    
    # TAB 1: DEPARTURES
    with t1:
        st.subheader("Active Departures (Non-Conformances)")
        df_dep = df_cbm[df_cbm["Type"] == "Departure"]
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(
                df_dep, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "ID": st.column_config.TextColumn("Departure ID", width="small"),
                    "Criticality": st.column_config.Column("Risk", width="small")
                }
            )
        with c2:
            # Action Panel for RW users
            if access_code == "RW":
                with st.container(border=True):
                    st.markdown("**Actions**")
                    if st.button("➕ New Departure", use_container_width=True):
                        st.info("Form to log new non-conformance would open here.")
                    if st.button("📥 Export Report", use_container_width=True):
                        st.success("Export started...")

    # TAB 2: INSPECTIONS
    with t2:
        st.subheader("Condition Based Inspections")
        st.dataframe(
            df_cbm[df_cbm["Type"] == "Inspection"], 
            use_container_width=True, 
            hide_index=True
        )

    # TAB 3: DISPOSITIONS
    with t3:
        st.subheader("Engineering Dispositions")
        st.success("✅ All active dispositions have been processed for the current outage window.")
        
        # Simulated list of closed items
        st.markdown("**Recently Closed Dispositions:**")
        st.markdown("- **DISP-202**: GT1 Exhaust Frame Crack - *Weld Repair Approved (12/12/2025)*")
        st.markdown("- **DISP-205**: ST Main Stop Valve Erosion - *Replace Seat (01/05/2026)*")

    # TAB 4: CBRL (Component Repair)
    with t4:
        st.subheader("CBRL (Component Based Repair List)")
        cbrl_data = [
            {"Part": "Nozzle Seg 1", "Serial": "SN-99283", "Repair Vendor": "Sulzer", "Status": "At Vendor", "Exp Return": "2026-03-15"},
            {"Part": "Shroud Block", "Serial": "SN-11223", "Repair Vendor": "GE Verova", "Status": "Scrapped", "Exp Return": "N/A"},
            {"Part": "Transition Piece", "Serial": "SN-77441", "Repair Vendor": "MITS", "Status": "In Transit", "Exp Return": "2026-02-28"}
        ]
        st.dataframe(pd.DataFrame(cbrl_data), use_container_width=True, hide_index=True)

    # TAB 5: ROTOR EOL
    with t5:
        st.subheader("Rotor End-of-Life (EOL) Requests")
        eol_df = df_cbm[df_cbm["Type"] == "Rotor EOL"]
        
        if eol_df.empty:
            st.info("No EOL risks identified.")
        else:
            for _, row in eol_df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1, 5, 2])
                    
                    with c1:
                        st.markdown("# 🛑")
                    
                    with c2:
                        st.markdown(f"**{row['Asset']} - {row['Component']}**")
                        st.caption(f"Reason: {row['Issue']} | Status: {row['Status']}")
                        st.progress(100, text="Life Consumed: 100%")
                    
                    with c3:
                        if st.button("View Technical Report", key=f"btn_{row['ID']}"):
                            st.toast(f"Opening PDF Report for {row['ID']}...")