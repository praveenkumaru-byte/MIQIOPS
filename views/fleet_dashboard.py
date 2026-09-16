# views/fleet_dashboard.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from pandas import to_datetime
from utils.utils import load_csv
import plotly.graph_objects as go #for budget burn rate bar within bar chart
from utils.utils import render_styled_aggrid # AG Grid for performance tables etc.

# Cache data loading
@st.cache_data
def load_fleet_data():
    fleet = load_csv("fleet_status.csv")
    projects = load_csv("supermaster_project_list.csv")
    labor = load_csv("labor_history.csv")
    
    # Load Incidents (Graceful fallback if missing)
    try:
        incidents = load_csv("ehs_incidents.csv")
    except Exception:
        incidents = pd.DataFrame()
        
    return fleet, projects, labor, incidents

def render(access_code: str):
    st.title("Fleet Overview")

    # 1. LOAD DATA
    fleet_df, proj_df, labor_df, inc_df = load_fleet_data()
    #st.expander("Debug: Raw Fleet DF").dataframe(fleetdf, use_container_width=True)

    if proj_df.empty or fleet_df.empty:
        st.error("🚨 Data Error: Missing 'fleet_status.csv' or 'supermaster_project_list.csv'.")
        return

    # 2. DATE PARSING & CONFIG
    SIMULATED_TODAY = datetime(2026, 2, 3)

    for df in [fleet_df, proj_df]:
        for col in ["Start Date", "End Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # ---------- HELPER: UNIQUE LABELS (Preserved) ----------
    def get_unique_outage_label(uid):
        if pd.isna(uid): return "Unknown"
        match = fleet_df[fleet_df["OutageUID"] == uid]
        if match.empty: return uid 
        
        row = match.iloc[0]
        site = row["Site Name"]
        otype = row["Outage Type"] \
            .replace("Planned - ", "") \
            .replace("Forced - ", "Forced: ") \
            .replace("Major Overhaul", "MO") \
            .replace("Hot Gas Path", "HGP") \
            .replace("Combustion Inspection", "CI") \
            .replace("Exciter Diode Failure", "EDF")
        
        year = ""
        if pd.notna(row["Start Date"]):
            year = f" '{str(row['Start Date'].year)[-2:]}"
        
        return f"{site} ({otype}{year})"

    # ---------- INTERACTION FLAGS ----------
    if "show_late_tg" not in st.session_state:
        st.session_state.show_late_tg = False
    if "show_safety_late" not in st.session_state:
        st.session_state.show_safety_late = False
    if "show_safety_active" not in st.session_state:
        st.session_state.show_safety_active = False
    if "show_overrun_projects" not in st.session_state:
        st.session_state.show_overrun_projects = False

    # ==========================================================================
    # ROW 1: FLEET & TOLLGATE KPIs
    # ==========================================================================
    site_count = fleet_df["Site Name"].nunique()
    in_outage = (fleet_df["Status"] == "Execution").sum()
    unplanned_complete = ((fleet_df["Status"] == "Completed") & (fleet_df["Outage Type"].str.contains("Forced", na=False))).sum()
    
    tg_group = proj_df.groupby(["OutageUID", "Tollgate"])
    tg_summary = tg_group.agg(
        Is_Late=("TollgateLateFlag", "any"),
        Is_Complete=("Status", lambda x: (x == "Completed").all())
    ).reset_index()

    total_unique_tollgates = len(tg_summary)
    late_tollgates_count = tg_summary["Is_Late"].sum()
    completed_tollgates_count = tg_summary["Is_Complete"].sum()
    open_tollgates_count = total_unique_tollgates - completed_tollgates_count
    
    on_track_count = total_unique_tollgates - late_tollgates_count
    perf_pct = (on_track_count / total_unique_tollgates * 100) if total_unique_tollgates > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Fleet Status</div><div class="miq-kpi-value">{site_count} Sites</div><div class="miq-kpi-sub">{in_outage} In Execution • {unplanned_complete} Forced (Done)</div></div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Active Tollgates</div><div class="miq-kpi-value">{open_tollgates_count} Open</div><div class="miq-kpi-sub">{perf_pct:.1f}% currently On-Track</div></div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""<div class="miq-kpi-card kpi-green"><div class="miq-kpi-label">Fully Closed</div><div class="miq-kpi-value">{completed_tollgates_count}</div><div class="miq-kpi-sub">Tollgates 100% Complete</div></div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""<div class="miq-kpi-card kpi-amber"><div class="miq-kpi-label">Total Late</div><div class="miq-kpi-value">{late_tollgates_count}</div><div class="miq-kpi-sub">Tollgates with Delays</div></div>""", unsafe_allow_html=True)
        btn_text = "Hide Late Summary" if st.session_state.show_late_tg else "View Late Summary"
        if st.button(btn_text, key="btn_late_view"):
            st.session_state.show_late_tg = not st.session_state.show_late_tg

    if st.session_state.show_late_tg:
        st.markdown("#### ⚠️ Critical Tollgate Delays (Executive Summary)")
        late_projects = proj_df[proj_df["TollgateLateFlag"] == True].copy()
        if late_projects.empty:
            st.success("✅ No critical delays found.")
        else:
            late_projects["Days Overdue"] = (SIMULATED_TODAY - late_projects["End Date"]).dt.days
            summary_table = late_projects.groupby(["Site Name", "OutageUID", "Tollgate"]).agg(
                Count_Projects=("Project ID", "count"),
                Max_Late_Days=("Days Overdue", "max"),
                Managers=("Project Manager", lambda x: ", ".join(sorted(x.unique().astype(str))))
            ).reset_index()
            summary_table.columns = ["Site Name", "Outage ID", "Late Tollgate", "# Projects Late", "Max Late (Days)", "Project Manager(s)"]
            st.dataframe(summary_table.sort_values("Max Late (Days)", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==========================================================================
    # ROW 2: FINANCIAL PERFORMANCE
    # ==========================================================================
    st.markdown("### Financial Performance")
    total_budget = proj_df["Budget"].sum()
    total_actual = proj_df["Actual Cost"].sum()
    utilization_pct = (total_actual / total_budget * 100) if total_budget else 0
    proj_df["Overrun"] = proj_df["Actual Cost"] - proj_df["Budget"]
    overrun_projects = proj_df[proj_df["Overrun"] > 0].copy()
    overrun_total = overrun_projects["Overrun"].sum()
    overrun_base_budget = overrun_projects["Budget"].sum()

    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Total Allotted Budget</div><div class="miq-kpi-value">${total_budget/1e6:.1f}M</div><div class="miq-kpi-sub">{len(proj_df)} Projects</div></div>""", unsafe_allow_html=True)
    with f2:
        st.markdown(f"""<div class="miq-kpi-card kpi-green"><div class="miq-kpi-label">Total Consumption</div><div class="miq-kpi-value">${total_actual/1e6:.1f}M</div><div class="miq-kpi-sub">{utilization_pct:.1f}% Utilized</div></div>""", unsafe_allow_html=True)
    #with f3:
    #   st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Labor Burn Rate</div><div class="miq-kpi-value">$42,500</div><div class="miq-kpi-sub">Est. Daily Spend</div></div>""", unsafe_allow_html=True)
    # ---------------------------------------------------------
    # CARD 3: LABOR BURN RATE (Last Available Day)
    # ---------------------------------------------------------
    # 1. Calculate the spend for the latest date in the file
    last_day_spend = 0
    if not labor_df.empty and "Date" in labor_df.columns and "Total Cost" in labor_df.columns:
        # Ensure dates are datetime objects
        labor_df["Date"] = pd.to_datetime(labor_df["Date"], dayfirst=True, errors="coerce")
        
        # Find the absolute latest date in the file (The "Previous Day" of data)
        max_date = labor_df["Date"].max()
        
        if pd.notna(max_date):
            # Filter for only that day's records
            last_day_df = labor_df[labor_df["Date"] == max_date]
            last_day_spend = last_day_df["Total Cost"].sum()

    # 2. Render the Card
    with f3:
        st.markdown(f"""
            <div class="miq-kpi-card">
                <div class="miq-kpi-label">Labor Burn Rate</div>
                <div class="miq-kpi-value">${last_day_spend:,.0f}</div>
                <div class="miq-kpi-sub">Yesterday's Spend</div>
            </div>
            """, unsafe_allow_html=True)
    
    with f4:
        st.markdown(f"""<div class="miq-kpi-card kpi-amber"><div class="miq-kpi-label">Overruns ($)</div><div class="miq-kpi-value">${overrun_total:,.0f}</div><div class="miq-kpi-sub">on ${overrun_base_budget/1e6:.1f}M Budget</div></div>""", unsafe_allow_html=True)
        if st.button("View Overrun Projects", key="btn_overrun"):
            st.session_state.show_overrun_projects = not st.session_state.show_overrun_projects
    if st.session_state.show_overrun_projects and not overrun_projects.empty:
        st.dataframe(overrun_projects[["Site Name", "Project ID", "Description", "Budget", "Actual Cost", "Overrun"]].sort_values("Overrun", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ==========================================================================
    # REFINED BUDGET ALLOCATION vs. CONSUMPTION (Sleek Bullet Style)
    # ==========================================================================
    st.markdown("### $ Budget Allocation vs. Consumption")

    # 1. Prepare Data with Sorting
    # Group projects to get financials
    budget_summary = proj_df.groupby("OutageUID").agg({
        "Budget": "sum",
        "Actual Cost": "sum"
    }).reset_index()

    # Merge with fleet_df to get 'Start Date' for sorting
    # Ensure fleet_df dates are datetime objects
    fleet_sort = fleet_df[["OutageUID", "Start Date"]].copy()
    fleet_sort["Start Date"] = pd.to_datetime(fleet_sort["Start Date"], dayfirst=True)

    # Merge and Sort: Ascending (Oldest/First Started at the Top)
    budget_dist = budget_summary.merge(fleet_sort, on="OutageUID")
    budget_dist = budget_dist.sort_values("Start Date", ascending=True)

    # Calculate Burn % for labels
    budget_dist["Burn_Pct"] = (budget_dist["Actual Cost"] / budget_dist["Budget"] * 100).fillna(0)

    # 2. Create the Layered "Thin-in-Thick" Bar Chart
    fig_budget = go.Figure()

    # Background: Total Allocated Budget (Thick & Subtle)
    fig_budget.add_trace(go.Bar(
        y=budget_dist["OutageUID"],
        x=budget_dist["Budget"],
        name="Total Budget",
        orientation='h',
        marker=dict(color='rgba(16, 185, 129, 0.15)', line=dict(color='#10b981', width=1)),
        width=0.8, # Thicker background bar
        hoverinfo='x+y'
    ))

    # Foreground: Burned/Actual Cost (Thin & Solid)
    fig_budget.add_trace(go.Bar(
        y=budget_dist["OutageUID"],
        x=budget_dist["Actual Cost"],
        name="Burned (Actual)",
        orientation='h',
        marker=dict(color='#ef4444'), 
        width=0.4, # EXACTLY HALF the height of the budget bar (sleek look)
        text=budget_dist.apply(lambda r: f"${r['Actual Cost']/1e6:.1f}M ({r['Burn_Pct']:.0f}%)", axis=1),
        textposition='outside', # Moved outside for a cleaner look on thin bars
        textfont=dict(color='#374151', size=11),
        hoverinfo='x+y'
    ))

    # 3. Final Styling
    fig_budget.update_layout(
        barmode='overlay',
        height=350 + (len(budget_dist) * 30),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=120, t=50, b=10), # Extra right margin for labels
        xaxis=dict(
            title="Amount ($)", 
            gridcolor='rgba(0,0,0,0.05)',
            showticklabels=True
        ),
        yaxis=dict(
            title=None, 
            autorange="reversed", # Keeps chronological order top-to-bottom
            tickfont=dict(size=12, color='#4b5563')
        ),
        plot_bgcolor='rgba(0,0,0,0)',
    )

    st.plotly_chart(fig_budget, use_container_width=True)

    # ==========================================================================
    # ROW 3: SAFETY & COMPLIANCE (UPDATED LOGIC)
    # ==========================================================================
    st.markdown("### Safety & Compliance")
    
    # --- Data Prep ---
    # 1. Planned Safety (Projects)
    safety_mask = proj_df["Asset"].str.contains("Safety", case=False, na=False) | proj_df["Description"].str.contains("Safety", case=False, na=False)
    safety_projs = proj_df[safety_mask].copy()
    
    # 2. Unplanned Safety (Incidents)
    # Ensure relevant columns exist in incidents
    if not inc_df.empty:
        # Standardize Status to 'Open' / 'Closed' for counting
        inc_df["UnifiedStatus"] = inc_df["Status"].apply(lambda x: "Closed" if str(x).lower() == "closed" else "Open")
    else:
        inc_df = pd.DataFrame(columns=["Incident ID", "Status", "UnifiedStatus", "Site Name", "Description"])

    # --- Metrics Calculation ---
    
    # Card 1: All Safety Work (Planned + Incidents)
    total_safety_count = len(safety_projs) + len(inc_df)
    s_budget = safety_projs["Budget"].sum() # Only projects have budget
    
    # Card 2: Active Work (Planned In-Progress)
    active_projs = safety_projs[safety_projs["Status"] == "In Progress"]
    active_proj_count = len(active_projs)
    
    # Card 3: Active Incidents (Open/Investigating)
    active_incidents = inc_df[inc_df["UnifiedStatus"] == "Open"]
    active_inc_count = len(active_incidents)
    
    # Card 4: Late Safety Work (Late Projects + Open Incidents)
    late_projs = safety_projs[safety_projs["TollgateLateFlag"] == True]
    # For incidents, assume all 'Open' incidents are "Late/Requiring Attention" for this high-level KPI, 
    # or just use the count of Late Projects + Open Incidents. 
    # To match user request "Late Safety Work", we combine them.
    late_safety_count = len(late_projs) # User likely means 'Overdue Tasks' primarily
    
    # --- KPI Cards ---
    s1, s2, s3, s4 = st.columns(4)
    
    # Card 1
    with s1:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">All Safety Work</div><div class="miq-kpi-value">{total_safety_count} Items</div><div class="miq-kpi-sub">Total Budget: ${s_budget/1e6:.2f}M</div></div>""", unsafe_allow_html=True)
    
    # Card 2
    with s2:
        st.markdown(f"""<div class="miq-kpi-card"><div class="miq-kpi-label">Active Work</div><div class="miq-kpi-value">{active_proj_count} Projects</div><div class="miq-kpi-sub">Status: In Progress</div></div>""", unsafe_allow_html=True)
        if st.button("View Active Projects", key="btn_safety_active"):
            st.session_state.show_safety_active = not st.session_state.show_safety_active

    # Card 3
    with s3:
        st.markdown(f"""<div class="miq-kpi-card kpi-amber"><div class="miq-kpi-label">Active Incidents</div><div class="miq-kpi-value">{active_inc_count} Open</div><div class="miq-kpi-sub">In Progress</div></div>""", unsafe_allow_html=True)
    
    # Card 4
    with s4:
        st.markdown(f"""<div class="miq-kpi-card kpi-red"><div class="miq-kpi-label">Late Safety Work</div><div class="miq-kpi-value">{late_safety_count}</div><div class="miq-kpi-sub">Requires attention</div></div>""", unsafe_allow_html=True)
        if st.button("View Late Items", key="btn_safety_late"):
            st.session_state.show_safety_late = not st.session_state.show_safety_late

    # --- Popovers / Drilldowns ---
    
    if st.session_state.show_safety_active and not active_projs.empty:
        st.markdown("#### 🟢 Active Safety Projects")
        st.dataframe(
            active_projs[["Site Name", "Project ID", "Description", "End Date", "Project Manager"]], 
            use_container_width=True, 
            hide_index=True
        )
    elif st.session_state.show_safety_active:
        st.info("No active safety projects found.")

    if st.session_state.show_safety_late:
        st.markdown("#### 🔴 Late Safety Projects")
        if not late_projs.empty:
            st.dataframe(
                late_projs[["Site Name", "Project ID", "Description", "Status", "End Date"]], 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.success("No late safety projects.")

    st.markdown("---")

# ==========================================================================
    # ROW 4: FLEET SCHEDULE TIMELINE
    # ==========================================================================
    st.subheader("Fleet Schedule Timeline")
    
    if not fleet_df.empty:
        # 1. Define the Label Helper (Fixes the NameError)
        def get_smart_gantt_label(row):
            uid = row["OutageUID"]
            status = row["Status"]
            start_date = row["Start Date"]
            if status == "Completed": return "T+1"
            if status == "Execution": return "T-0"
            if pd.isna(start_date): return "Planned"
            
            # Simple Date Math for Labels
            days_diff = (start_date - SIMULATED_TODAY).days
            if days_diff < 0: return "T-0"
            if days_diff < 60: return "T-1"
            if days_diff < 135: return "T-3"
            if days_diff < 270: return "T-6"
            if days_diff < 450: return "T-12"
            return "T-24"


        # Normalize Start/End Date so WV_HGP_2028 keeps its dates
        for col in ["Start Date", "End Date"]:
            if col in fleet_df.columns:
                fleet_df[col] = to_datetime(
                    fleet_df[col],
                    dayfirst=True,
                    errors="coerce",
                )

        # 2. Sort and apply the label
        gantt_df = fleet_df.sort_values("Start Date").copy()
        gantt_df["TG_Label"] = gantt_df.apply(get_smart_gantt_label, axis=1)

        # 3. Create the Timeline with the Scrollable Slider
        fig_gantt = px.timeline(
            gantt_df, 
            x_start="Start Date", 
            x_end="End Date", 
            y="Site Name", 
            color="Status", 
            text="TG_Label",
            hover_data=["Outage Type", "Plant Manager", "OutageUID"],
            color_discrete_map={
                "Execution": "#2563eb", 
                "Completed": "#10b981", 
                "Planned": "#f97316"
            }
        )

        # 4. Range Slider Configuration
        fig_gantt.update_xaxes(
            rangeslider_visible=True,
        #    range=[
        #        SIMULATED_TODAY - timedelta(days=30), 
        #        SIMULATED_TODAY + timedelta(days=365)
        #    ],
            tickformat="%b %Y"
        )

        fig_gantt.update_yaxes(autorange="reversed")
        
        # Today Line
        today_ts = SIMULATED_TODAY.timestamp() * 1000
        fig_gantt.add_vline(x=today_ts, line_width=2, line_color="red", annotation_text="Today")
        
        fig_gantt.update_layout(
            height=500, 
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_title=None,
            yaxis_title=None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        st.plotly_chart(fig_gantt, use_container_width=True)
    else:
        st.info("No schedule data found.")

    # ==========================================================================
    # ROW 5: OUTAGE TOLLGATE STATUS
    # ==========================================================================
    st.subheader("Outage Tollgate Status")
    
    outage_stats = proj_df.groupby("OutageUID").agg(
        Completed=("Status", lambda x: (x == "Completed").sum()),
        In_Progress=("Status", lambda x: (x == "In Progress").sum()),
        Not_Started=("Status", lambda x: (x == "Planned").sum()),
        Late=("TollgateLateFlag", lambda x: (x == True).sum())
    ).reset_index()

    if not outage_stats.empty:
        outage_stats["Label"] = outage_stats["OutageUID"].apply(get_unique_outage_label)

        bar_df = outage_stats.melt(
            id_vars=["Label", "OutageUID"], 
            value_vars=["Not_Started", "In_Progress", "Completed", "Late"], 
            var_name="Status", 
            value_name="Count"
        )
        
        fig_bar = px.bar(
            bar_df, x="Count", y="Label", color="Status", orientation='h', barmode="stack",
            color_discrete_map={"Completed": "#10b981", "In_Progress": "#3b82f6", "Late": "#ef4444", "Not_Started": "#e2e8f0"}
        )
        fig_bar.update_layout(height=500, xaxis_title="Number of Projects/Tollgates", yaxis_title=None,
                              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_bar, use_container_width=True)

        # ---------------------------------------------------------
        # 5. SITE PERFORMANCE METRICS (Native Streamlit)
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("Site Performance Metrics")
        
        # 1. GENERATE DATA (Same as before)
        sites = fleet_df["Site Name"].unique()
        data = []
        for site in sites:
            eff = round(np.random.uniform(35.0, 42.0), 1) if "Peaker" in site else round(np.random.uniform(58.0, 62.0), 1)
            data.append({
                "Site Name": site, 
                "Availability": round(np.random.uniform(94.0, 99.5), 1), 
                "Reliability": round(np.random.uniform(98.0, 99.9), 1), 
                "Efficiency": eff
            })
        df_perf = pd.DataFrame(data)

        # 2. RENDER WITH NATIVE COLUMN CONFIG
        st.dataframe(
            df_perf,
            column_config={
                "Site Name": st.column_config.TextColumn(
                    "Site Name",
                    width="medium",
                ),
                "Availability": st.column_config.ProgressColumn(
                    "Availability",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
                "Reliability": st.column_config.ProgressColumn(
                    "Reliability",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
                "Efficiency": st.column_config.ProgressColumn(
                    "Efficiency",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
            },
            hide_index=True,
            use_container_width=True
        )