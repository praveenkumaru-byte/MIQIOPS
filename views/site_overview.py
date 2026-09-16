# views/site_overview.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from utils.utils import load_csv

# Cache data loading
@st.cache_data
def load_site_data():
    fleet = load_csv("fleet_status.csv")
    projects = load_csv("supermaster_project_list.csv")
    labor = load_csv("labor_history.csv")
    return fleet, projects, labor

def render(access_code: str):
    st.title("Site Level Overview")

    # 1. LOAD DATA
    fleet_df, proj_df, labor_df = load_site_data()

    if proj_df.empty or fleet_df.empty:
        st.error("Data Error: Missing 'fleet_status.csv' or 'supermaster_project_list.csv'.")
        return

    # 2. DATE PARSING & CONFIG
    SIMULATED_TODAY = datetime(2026, 2, 4)

    for df in [fleet_df, proj_df, labor_df]:
        for col in ["Start Date", "End Date", "Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    
    # Ensure numeric types
    for col in ["Budget", "Actual Cost"]:
        if col in proj_df.columns:
            proj_df[col] = pd.to_numeric(proj_df[col], errors="coerce").fillna(0)

    # Initialize Session State for Safety Toggle
    if "show_site_late_safety" not in st.session_state:
        st.session_state.show_site_late_safety = False

    # 3. SITE SELECTION
    all_sites = sorted(fleet_df["Site Name"].dropna().unique())
    if not all_sites:
        st.warning("No sites found in Fleet Status.")
        return

    selected_site = st.selectbox("Select Facility / Site:", all_sites)

    # 4. FILTER DATA FOR SELECTED SITE
    site_fleet = fleet_df[fleet_df["Site Name"] == selected_site].copy()
    site_projects = proj_df[proj_df["Site Name"] == selected_site].copy()
    
    # Filter Labor
    site_labor = pd.DataFrame()
    if not labor_df.empty:
        if "Site Name" in labor_df.columns:
            site_labor = labor_df[labor_df["Site Name"] == selected_site]
        elif "Site" in labor_df.columns:
             site_labor = labor_df[labor_df["Site"] == selected_site]

    # ==========================================================================
    # SECTION 1: SITE HEADER & KPIs
    # ==========================================================================
    
    # Status Logic
    current_outage = site_fleet[site_fleet["Status"] == "Execution"]
    if not current_outage.empty:
        status_label = "⚠️ IN OUTAGE"
        status_color = "red"
        active_outage_name = current_outage.iloc[0]["Outage Type"]
    else:
        status_label = "✅ OPERATIONAL"
        status_color = "green"
        active_outage_name = "Normal Operations"

    # Financials
    site_budget = site_projects["Budget"].sum()
    site_actual = site_projects["Actual Cost"].sum()
    site_util = (site_actual / site_budget * 100) if site_budget > 0 else 0
    
    # Safety Stats (BROAD FILTER: Asset OR Description)
    safety_mask = site_projects["Asset"].str.contains("Safety", case=False, na=False) | site_projects["Description"].str.contains("Safety", case=False, na=False)
    safety_cnt = len(site_projects[safety_mask])
    
    # KPI Layout
    k1, k2, k3, k4 = st.columns(4)
    
    with k1:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Plant Status</div><div class="miq-kpi-value" style="color:{status_color}; font-size:1.4rem;">{status_label}</div><div class="miq-kpi-sub">{active_outage_name}</div></div>""", unsafe_allow_html=True)
        
    with k2:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Active Projects</div><div class="miq-kpi-value">{len(site_projects)}</div><div class="miq-kpi-sub">Total Line Items</div></div>""", unsafe_allow_html=True)

    with k3:
        st.markdown(f"""<div class="miq-kpi-card kpi-green"><div class="miq-kpi-label">Budget vs Actual</div><div class="miq-kpi-value">${site_actual/1e6:.1f}M</div><div class="miq-kpi-sub">of ${site_budget/1e6:.1f}M ({site_util:.0f}%)</div></div>""", unsafe_allow_html=True)

    with k4:
        st.markdown(f"""<div class="miq-kpi-card kpi-amber"><div class="miq-kpi-label">Safety Scope</div><div class="miq-kpi-value">{safety_cnt}</div><div class="miq-kpi-sub">Safety Projects</div></div>""", unsafe_allow_html=True)
        
        # --- BUTTON: View Late Safety ---
        btn_label = "Hide Late Safety" if st.session_state.show_site_late_safety else "View Late Safety"
        if st.button(btn_label, key="btn_site_safety"):
            st.session_state.show_site_late_safety = not st.session_state.show_site_late_safety

    # --- CONDITIONAL TABLE: LATE SAFETY ---
    if st.session_state.show_site_late_safety:
        st.markdown("#### ⚠️ Late Safety Projects")
        late_safety_df = site_projects[safety_mask & (site_projects["TollgateLateFlag"] == True)]
        
        if late_safety_df.empty:
            st.success("✅ No safety projects are currently flagged as late for this site.")
        else:
            cols = ["Project ID", "Description", "OutageUID", "Status", "End Date", "Project Manager"]
            st.dataframe(
                late_safety_df[cols].sort_values("End Date"),
                use_container_width=True,
                hide_index=True
            )

    st.markdown("---")

    # ==========================================================================
    # SECTION 2: SITE SCHEDULE (GANTT)
    # ==========================================================================
    st.subheader(f"Schedule: {selected_site}")
    
    if not site_fleet.empty:
        site_fleet = site_fleet.sort_values("Start Date")
        
        fig_gantt = px.timeline(
            site_fleet,
            x_start="Start Date", x_end="End Date", y="Outage Type", color="Status",
            hover_data=["Duration (Days)", "Total Budget ($M)", "Plant Manager"],
            color_discrete_map={"Execution": "#2563eb", "Completed": "#10b981", "Planned": "#f97316"}
        )
        today_ts = SIMULATED_TODAY.timestamp() * 1000
        fig_gantt.add_vline(x=today_ts, line_width=2, line_dash="dot", line_color="red", annotation_text="Today")
        fig_gantt.update_yaxes(autorange="reversed")
        fig_gantt.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.info("No outages scheduled for this site.")

    # ==========================================================================
    # SECTION 3: FINANCIAL & LABOR
    # ==========================================================================
    # c_fin, c_labor = st.columns(2)
    
    # with c_fin:
    #    st.subheader("$ Spend by Outage Event")
    #    if not site_projects.empty:
    #        fin_group = site_projects.groupby("OutageUID").agg(Budget=("Budget", "sum"), Actual=("Actual Cost", "sum")).reset_index()
    #        fleet_map = fleet_df.set_index("OutageUID")["Outage Type"].to_dict()
    #        fin_group["Event"] = fin_group["OutageUID"].map(fleet_map).fillna(fin_group["OutageUID"])
    #        
    #        fin_melt = fin_group.melt(id_vars=["Event", "OutageUID"], value_vars=["Budget", "Actual"], var_name="Type", value_name="Amount")
    #        
    #        fig_fin = px.bar(fin_melt, x="Event", y="Amount", color="Type", barmode="group",
    #                         color_discrete_map={"Budget": "#94a3b8", "Actual": "#10b981"})
    #        fig_fin.update_layout(height=400, yaxis_tickformat="$.2s")
    #        st.plotly_chart(fig_fin, use_container_width=True)
    #    else:
    #        st.info("No project financial data available.")

    #with c_labor:
    #    st.subheader("Labor Trend (Site)")
    #    if not site_labor.empty:
    #       site_labor["Date"] = pd.to_datetime(site_labor["Date"], errors="coerce")
    #        daily_labor = site_labor.groupby("Date")["Total Cost"].sum().reset_index()
    #        fig_lab = px.area(daily_labor, x="Date", y="Total Cost", title="Daily Labor Burn Rate", line_shape="spline")
    #        fig_lab.update_traces(line_color="#3b82f6", fillcolor="rgba(59, 130, 246, 0.2)")
    #        fig_lab.update_layout(height=400, yaxis_tickformat="$.2s")
    #        st.plotly_chart(fig_lab, use_container_width=True)
    #    else:
    #        st.info(f"No labor history found specifically linked to {selected_site}.")

    #st.markdown("---")

    # ==========================================================================
    # SECTION 3: FINANCIAL & LABOR
    # ==========================================================================
    c_fin, c_labor = st.columns(2)

    with c_fin:
        st.subheader("Spend by Outage Event")

        if not site_projects.empty:
            # 1) Build outage list for this site
            site_outages = sorted(site_projects["OutageUID"].dropna().unique())
            outage_options = ["All Outages"] + site_outages

            sel_fin_outage = st.selectbox(
                "Filter by Outage (UID)",
                outage_options,
                key="fin_outage_sel",
            )

            # 2) Filter projects for selected outage (if any)
            fin_df = site_projects.copy()
            if sel_fin_outage != "All Outages":
                fin_df = fin_df[fin_df["OutageUID"] == sel_fin_outage]

            if fin_df.empty:
                st.info("No project financial data for the selected outage.")
            else:
                # 3) Aggregate Budget / Actual by OutageUID
                fin_group = (
                    fin_df.groupby("OutageUID")
                    .agg(Budget=("Budget", "sum"), Actual=("Actual Cost", "sum"))
                    .reset_index()
                )

                # 4) Map to human-friendly outage label using fleet_df
                fleet_map = (
                    fleet_df.set_index("OutageUID")["Outage Type"].to_dict()
                    if not fleet_df.empty and "OutageUID" in fleet_df.columns
                    else {}
                )
                fin_group["Event"] = fin_group["OutageUID"].map(fleet_map).fillna(
                    fin_group["OutageUID"]
                )

                # 5) Melt for grouped bar chart
                fin_melt = fin_group.melt(
                    id_vars=["Event", "OutageUID"],
                    value_vars=["Budget", "Actual"],
                    var_name="Type",
                    value_name="Amount",
                )

                fig_fin = px.bar(
                    fin_melt,
                    x="Event",
                    y="Amount",
                    color="Type",
                    barmode="group",
                    color_discrete_map={"Budget": "#94a3b8", "Actual": "#10b981"},
                )
                fig_fin.update_layout(height=400, yaxis_tickformat="$.2s")
                st.plotly_chart(fig_fin, use_container_width=True)
        else:
            st.info("No project financial data available.")

    with c_labor:
        st.subheader("Labor Trend (Site)")
        if not site_labor.empty:
            site_labor["Date"] = pd.to_datetime(site_labor["Date"], errors="coerce")
            daily_labor = (
                site_labor.groupby("Date")["Total Cost"].sum().reset_index()
            )
            fig_lab = px.area(
                daily_labor,
                x="Date",
                y="Total Cost",
                title="Daily Labor Burn Rate",
                line_shape="spline",
            )
            fig_lab.update_traces(
                line_color="#3b82f6", fillcolor="rgba(59, 130, 246, 0.2)"
            )
            fig_lab.update_layout(height=400, yaxis_tickformat="$.2s")
            st.plotly_chart(fig_lab, use_container_width=True)
        else:
            st.info(f"No labor history found specifically linked to {selected_site}.")

    st.markdown("---")


    # ==========================================================================
    # SECTION 4: ASSET BREAKDOWN (FIXED LOGIC)
    # ==========================================================================
    st.subheader("Asset Analysis Breakdown")
    
    if not site_projects.empty:
        # A. Filters
        ac1, ac2 = st.columns(2)
        with ac1:
            site_outages = sorted(site_projects["OutageUID"].unique())
            outage_opts = ["All Outages"] + site_outages
            sel_asset_outage = st.selectbox("Select Scope/Outage:", outage_opts, key="asset_outage_sel")
        with ac2:
            metric_opt = st.radio("Select Metric:", ["Project Count", "Budget ($)"], horizontal=True)

        # B. Prepare Data
        asset_viz_df = site_projects.copy()
        if sel_asset_outage != "All Outages":
            asset_viz_df = asset_viz_df[asset_viz_df["OutageUID"] == sel_asset_outage]

        # --- FIX: Apply the same "Safety Logic" as the KPI Card ---
        # Any row with "Safety" in Description or Asset gets re-labeled as "Safety & Compliance"
        chart_safety_mask = asset_viz_df["Asset"].str.contains("Safety", case=False, na=False) | asset_viz_df["Description"].str.contains("Safety", case=False, na=False)
        asset_viz_df.loc[chart_safety_mask, "Asset"] = "Safety & Compliance"
        # ----------------------------------------------------------

        asset_viz_df["Asset"] = asset_viz_df["Asset"].fillna("General / Other")
        
        # C. Aggregate
        asset_group = asset_viz_df.groupby("Asset").agg(
            Count=("Project ID", "count"),
            Budget=("Budget", "sum")
        ).reset_index()

        # D. Render
        y_col = "Count" if metric_opt == "Project Count" else "Budget"
        color_seq = px.colors.qualitative.Prism

        fig_asset = px.bar(
            asset_group,
            x="Asset",
            y=y_col,
            color="Asset",
            text=y_col,
            title=f"{metric_opt} by Asset ({sel_asset_outage})",
            color_discrete_sequence=color_seq
        )
        
        if metric_opt == "Budget ($)":
            fig_asset.update_traces(texttemplate='$%{text:.2s}', textposition='outside')
            fig_asset.update_layout(yaxis_tickformat="$.2s")
        else:
            fig_asset.update_traces(texttemplate='%{text}', textposition='outside')
            
        fig_asset.update_layout(height=450, showlegend=False)
        st.plotly_chart(fig_asset, use_container_width=True)
        
    else:
        st.info("No data available for asset analysis.")

    st.markdown("---")

    # ==========================================================================
    # SECTION 5: PROJECT REGISTER (Drill Down)
    # ==========================================================================
    st.subheader(f"Project Register: {selected_site}")
    
    if not site_projects.empty:
        c_filt1, c_filt2 = st.columns(2)
        with c_filt1:
            outages = ["All"] + sorted(site_projects["OutageUID"].unique())
            sel_outage = st.selectbox("Filter by Outage:", outages, key="reg_outage")
        with c_filt2:
            statuses = ["All"] + sorted(site_projects["Status"].unique())
            sel_status = st.selectbox("Filter by Status:", statuses, key="reg_status")
        
        filtered_df = site_projects.copy()
        if sel_outage != "All":
            filtered_df = filtered_df[filtered_df["OutageUID"] == sel_outage]
        if sel_status != "All":
            filtered_df = filtered_df[filtered_df["Status"] == sel_status]
            
        show_cols = ["Project ID", "Description", "OutageUID", "Tollgate", "Status", "Start Date", "End Date", "Budget", "Actual Cost", "Project Manager"]
        valid_cols = [c for c in show_cols if c in filtered_df.columns]
        
        st.dataframe(
            filtered_df[valid_cols].sort_values("Start Date"),
            use_container_width=True,
            hide_index=True
        )