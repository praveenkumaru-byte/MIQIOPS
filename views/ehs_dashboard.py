# views/ehs_dashboard.py

import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta
from utils.utils import load_csv

def render(access_code: str = "R") -> None:
    """
    EHS > EHS Dashboard (Hybrid Model - Full Feature)
    
    Integrates:
    1. Leading Indicators (Planned Safety Tasks) from 'supermaster_project_list.csv'
    2. Lagging Indicators (Incidents) from 'ehs_incidents.csv'
    3. RESTORED: Late Item Analysis & Time Window Filters
    """
    st.markdown("### EHS Command Center")

    # --- 1. DATA INGESTION & UNIFICATION ---
    
    # A. Load Incidents (Lagging)
    try:
        df_inc = load_csv("ehs_incidents.csv")
        df_inc["Type"] = "Incident"
        df_inc["Unified_Date"] = pd.to_datetime(df_inc["Event Date"], errors="coerce")
        df_inc = df_inc.rename(columns={"Incident ID": "ID", "Category": "Category", "Status": "Status"})
        if "Severity" not in df_inc.columns: df_inc["Severity"] = "Medium"
        # Incidents don't usually have a 'Target Date' for closure in this CSV, but if they did, we'd use it.
        # For now, we assume Incidents are 'Late' if they are Open and > 30 days old.
        df_inc["Target_Date"] = df_inc["Unified_Date"] + pd.Timedelta(days=30)
    except Exception:
        df_inc = pd.DataFrame()

    # B. Load Planned Tasks (Leading)
    try:
        df_master = load_csv("supermaster_project_list.csv")
        df_plan = df_master[df_master["Asset"] == "Safety"].copy()
        
        if not df_plan.empty:
            df_plan["Type"] = "Planned Task"
            df_plan["Unified_Date"] = pd.to_datetime(df_plan["End Date"], errors="coerce")
            df_plan["Target_Date"] = df_plan["Unified_Date"] # Project End Date is the target
            
            df_plan["Status"] = df_plan["Status"].apply(lambda x: "Closed" if x == "Completed" else "Open")
            df_plan["Category"] = df_plan["Sub-System"].fillna("General Safety")
            df_plan["Severity"] = "Planned"
            df_plan = df_plan.rename(columns={"Project ID": "ID", "Project Manager": "Owner"})
            
            cols_to_keep = ["ID", "OutageUID", "Site Name", "Unified_Date", "Target_Date", "Category", "Severity", "Status", "Description", "Type", "Owner"]
            df_plan = df_plan[cols_to_keep]
        else:
            df_plan = pd.DataFrame()
            
    except Exception:
        df_plan = pd.DataFrame()

    # C. Merge
    if df_inc.empty and df_plan.empty:
        st.error("No Safety Data Found.")
        return

    common_cols = ["ID", "OutageUID", "Site Name", "Unified_Date", "Target_Date", "Category", "Severity", "Status", "Description", "Type", "Owner"]
    for c in common_cols:
        if c not in df_inc.columns: df_inc[c] = None
            
    df_all = pd.concat([df_inc[common_cols], df_plan], ignore_index=True)
    df_all["Unified_Date"] = pd.to_datetime(df_all["Unified_Date"])
    df_all["Target_Date"] = pd.to_datetime(df_all["Target_Date"])

    # Calculate LATE FLAG (Global)
    today = pd.Timestamp.now()
    df_all["LateFlag"] = (df_all["Status"] == "Open") & (df_all["Target_Date"] < today)

    # --- 2. FILTERS (RESTORED Time Window) ---
    
    f1, f2, f3, f4 = st.columns(4)
    
    with f1:
        sites = ["All Sites"] + sorted(df_all["Site Name"].dropna().unique().tolist())
        sel_site = st.selectbox("Site", sites)
        
    with f2:
        outages = ["All Outages"] + sorted(df_all["OutageUID"].dropna().unique().tolist())
        sel_outage = st.selectbox("Outage", outages)
        
    with f3:
        types = ["All Types", "Incident", "Planned Task"]
        sel_type = st.selectbox("Type", types)

    with f4:
        # RESTORED: Time Window
        window = st.selectbox("Lookback", ["All Time", "30 Days", "90 Days", "1 Year"], index=0)

    # Apply Filters
    df_view = df_all.copy()
    if sel_site != "All Sites": df_view = df_view[df_view["Site Name"] == sel_site]
    if sel_outage != "All Outages": df_view = df_view[df_view["OutageUID"] == sel_outage]
    if sel_type != "All Types": df_view = df_view[df_view["Type"] == sel_type]
    
    if window != "All Time":
        days = 30 if window == "30 Days" else 90 if window == "90 Days" else 365
        cutoff = today - timedelta(days=days)
        df_view = df_view[df_view["Unified_Date"] >= cutoff]

    st.divider()

    # --- 3. KPI STRIP ---
    
    incidents_only = df_view[df_view["Type"] == "Incident"]
    
    # Days Incident Free
    days_stat = "N/A"
    if not incidents_only.empty:
        last_incident = incidents_only["Unified_Date"].max()
        if pd.notna(last_incident):
            delta = (datetime.now() - last_incident).days
            days_stat = f"{delta} Days"

    late_count = df_view["LateFlag"].sum()
    late_pct = (late_count / len(df_view) * 100) if len(df_view) > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Days Incident Free", days_stat)
    k2.metric("Open Incidents", len(incidents_only[incidents_only["Status"] == "Open"]), delta_color="inverse")
    k3.metric("Late Items", f"{late_count}", f"{late_pct:.1f}% of total", delta_color="inverse")
    k4.metric("Total Volume", len(df_view))

    st.divider()

    # --- 4. CHARTS ---
    
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Activity Timeline")
        if not df_view.empty:
            timeline = df_view.copy()
            timeline["Month"] = timeline["Unified_Date"].dt.to_period("M").astype(str)
            counts = timeline.groupby(["Month", "Type"]).size().reset_index(name="Count")
            color_map = {"Incident": "#FF4B4B", "Planned Task": "#1C83E1"}
            fig_time = px.bar(counts, x="Month", y="Count", color="Type", color_discrete_map=color_map, barmode="group")
            st.plotly_chart(fig_time, use_container_width=True)
    
    with c2:
        st.markdown("#### Risk Distribution")
        if not df_view.empty:
            fig_pie = px.pie(df_view, names="Category", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

    # --- 5. RESTORED: LATE DRILLDOWN ---
    
    if late_count > 0:
        st.divider()
        st.markdown("#### ⚠️ Late Item Analysis")
        
        df_late = df_view[df_view["LateFlag"] == True]
        
        l1, l2 = st.columns(2)
        
        with l1:
            st.markdown("**Late by Owner**")
            late_owner = df_late["Owner"].value_counts().reset_index()
            late_owner.columns = ["Owner", "Count"]
            fig_own = px.bar(late_owner, x="Owner", y="Count", color="Count", color_continuous_scale="Reds")
            st.plotly_chart(fig_own, use_container_width=True)
            
        with l2:
            st.markdown("**Late by Site**")
            late_site = df_late["Site Name"].value_counts().reset_index()
            late_site.columns = ["Site", "Count"]
            fig_site = px.bar(late_site, x="Site", y="Count", color="Count", color_continuous_scale="Reds")
            st.plotly_chart(fig_site, use_container_width=True)

    # --- 6. UNIFIED REGISTER ---
    st.markdown("#### Detailed Register")
    
    def highlight_row(row):
        if row['Type'] == 'Incident': return ['background-color: #ffe6e6'] * len(row)
        if row['LateFlag']: return ['color: #ff4b4b; font-weight: bold'] * len(row)
        return [''] * len(row)

    cols_show = ["ID", "Unified_Date", "Type", "Category", "Status", "LateFlag", "Description", "Owner"]
    
    st.dataframe(
        df_view[cols_show].sort_values("Unified_Date", ascending=False).style.apply(highlight_row, axis=1),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Unified_Date": st.column_config.DateColumn("Date"),
            "LateFlag": st.column_config.CheckboxColumn("Late?"),
        }
    )