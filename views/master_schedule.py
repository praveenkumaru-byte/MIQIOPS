# views/master_schedule.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from utils.utils import load_csv

def render(access_code: str = "R"):
    """
    Planning & Portfolio > Master Schedule (P6)
    Cleaned version: View-only dashboard tabs (Analytics, Gantt, Risk, Rates).
    P6 Creation logic moved to separate module.
    """

    # ==============================================================================
    # 1. DATA LOADING & SETUP
    # ==============================================================================
    df_fleet = load_csv("fleet_status.csv")
    df_projects = load_csv("supermaster_project_list.csv")
    df_rates = load_csv("contractor_rates.csv")

    if df_projects.empty or df_fleet.empty:
        st.error("🚨 Critical Error: Could not load required planning data files.")
        return

    # Simulated 'Today' for calculation logic
    SIMULATED_TODAY = datetime(2026, 1, 30)

    # Date Normalization
    for df in [df_fleet, df_projects]:
        for col in ["Start Date", "End Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # Deriving Risk Flags
    df_projects["Is_Late"] = (df_projects["Status"] == "In Progress") & (df_projects["End Date"] < SIMULATED_TODAY)
    df_projects["Over_Budget"] = df_projects["Actual Cost"] > df_projects["Budget"]
    
    # Fill missing values for cleaner UI
    df_projects["Description"] = df_projects["Description"].fillna("Untitled Project")
    df_projects["Project Manager"] = df_projects["Project Manager"].fillna("Unassigned")

    # ==============================================================================
    # 2. TOP HEADER & GLOBAL FILTERS
    # ==============================================================================
    st.markdown("### Master Schedule & Planning Portfolio")

    if access_code == "R":
        st.info(" Read-Only View enabled.")
    
    # Context Filters
    with st.container(border=True):
        f_col1, f_col2, f_col3 = st.columns([2, 1, 1])
        with f_col1:
            site_list = ["All Sites"] + sorted(df_fleet["Site Name"].unique().tolist())
            selected_site = st.selectbox("Planning Context / Site", site_list)
        with f_col2:
            all_mgrs = ["All Managers"] + sorted(df_projects["Project Manager"].unique().tolist())
            sel_pm = st.selectbox("Project Manager", all_mgrs)
        with f_col3:
            all_tgs = ["All Tollgates"] + ["T-24", "T-12", "T-6", "T-3", "T-1", "Execution", "T+1"]
            sel_tg = st.selectbox("Tollgate Phase", all_tgs)

    # Apply Filtering Logic
    filtered_df = df_projects.copy()
    if selected_site != "All Sites":
        filtered_df = filtered_df[filtered_df["Site Name"] == selected_site]
    if sel_pm != "All Managers":
        filtered_df = filtered_df[filtered_df["Project Manager"] == sel_pm]
    if sel_tg != "All Tollgates":
        filtered_df = filtered_df[filtered_df["Tollgate"] == sel_tg]

    # ==============================================================================
    # 3. CORE VIEW TABS
    # ==============================================================================
    t1, t2, t3, t4 = st.tabs([
        "📊 Portfolio Analytics", 
        "📅 Gantt Schedule", 
        "⚠️ Risk & Tollgates",
        "👷 Labor & Rates"
    ])

    # --- TAB 1: ANALYTICS ---
    with t1:
        st.markdown("#### Portfolio Performance")
        m1, m2, m3, m4 = st.columns(4)
        tot_b = filtered_df["Budget"].sum()
        tot_a = filtered_df["Actual Cost"].sum()
        late_n = len(filtered_df[filtered_df["Is_Late"]])
        over_n = len(filtered_df[filtered_df["Over_Budget"]])

        m1.metric("Total Budget", f"${tot_b/1e6:,.1f}M")
        m2.metric("Actual Spend", f"${tot_a/1e6:,.1f}M", f"{(tot_a/tot_b*100):.1f}%" if tot_b > 0 else "0%")
        m3.metric("Late Projects", late_n, delta=f"{late_n} Delayed", delta_color="inverse")
        m4.metric("Over Budget", over_n, delta=f"{over_n} Overrun", delta_color="inverse")

        st.divider()
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            fig_bva = go.Figure()
            fig_bva.add_trace(go.Bar(name="Budget", x=filtered_df["Project ID"], y=filtered_df["Budget"], marker_color="#94a3b8"))
            fig_bva.add_trace(go.Bar(name="Actual", x=filtered_df["Project ID"], y=filtered_df["Actual Cost"], marker_color="#1e3a8a"))
            fig_bva.update_layout(title="Financial Variance by Project ID", barmode='group', height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_bva, use_container_width=True)
        with c_chart2:
            if not filtered_df.empty:
                fig_pie = px.pie(filtered_df, names="Status", title="Project Status Mix", color_discrete_sequence=px.colors.qualitative.Safe)
                fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_pie, use_container_width=True)

    # --- TAB 2: GANTT SCHEDULE ---
    with t2:
        st.markdown("#### Integrated Master Schedule")
        if filtered_df.empty:
            st.info("No projects found matching the current filters.")
        else:
            fig_gantt = px.timeline(
                filtered_df, x_start="Start Date", x_end="End Date", y="Description", color="Tollgate",
                hover_data=["Project ID", "Status", "Project Manager"],
                color_discrete_map={"T-24": "#cbd5e1", "T-12": "#94a3b8", "T-6": "#64748b", "T-3": "#475569", "T-1": "#334155", "Execution": "#1e3a8a", "T+1": "#0f172a"}
            )
            fig_gantt.update_yaxes(autorange="reversed")
            fig_gantt.update_layout(height=600, margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_gantt, use_container_width=True)

    # --- TAB 3: RISK & TOLLGATES ---
    with t3:
        st.markdown("#### Tollgate Compliance & Risk Register")
        risk_df = filtered_df[(filtered_df["TollgateLateFlag"] == True) | (filtered_df["Is_Late"] == True) | (filtered_df["Over_Budget"] == True)].copy()
        if risk_df.empty:
            st.success("🎉 No critical risks found.")
        else:
            st.warning(f"Total Flagged Items: {len(risk_df)}")
            display_cols = ["Project ID", "Description", "Tollgate", "Status", "Budget", "Actual Cost"]
            valid_cols = [c for c in display_cols if c in risk_df.columns]
            st.dataframe(risk_df[valid_cols].sort_values("Tollgate"), use_container_width=True, hide_index=True)

    # --- TAB 4: LABOR & RATES ---
    with t4:
        st.markdown("#### Contractor Rate Schedule")
        if df_rates.empty:
            st.info("No contractor rate data available.")
        else:
            st.dataframe(df_rates, use_container_width=True, hide_index=True)