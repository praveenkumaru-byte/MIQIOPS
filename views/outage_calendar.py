# views/outage_calendar.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from utils.utils import load_csv

def render(access_code: str = "R"):
    """
    Planning & Scheduling > Outage Calendar
    
    Updates:
    1. Fleet View: Execution Only (Machine Down).
    2. Lifecycle View: Breaks down T-24, T-18... based on actual project dates + Real Execution Window.
    3. Detail View: Filters by Site -> Tollgate -> Shows Projects on Y-Axis.
    """
    st.markdown("### Integrated Outage & Tollgate Calendar")

    # 1. LOAD DATA
    df_fleet = load_csv("fleet_status.csv")
    df_projects = load_csv("supermaster_project_list.csv")

    if df_fleet.empty or df_projects.empty:
        st.warning("⚠️ Data missing. Please verify 'fleet_status.csv' and 'supermaster_project_list.csv'.")
        return

    # 2. DATE PARSING
    SIMULATED_TODAY = datetime(2026, 2, 3)
    today_ts = SIMULATED_TODAY.timestamp() * 1000
    
    for df in [df_fleet, df_projects]:
        for col in ["Start Date", "End Date"]:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors="coerce")

    # ==========================================================================
    # SECTION 1: FLEET OUTAGE EXECUTION (Machine Status)
    # ==========================================================================
    st.subheader("1. Fleet Outage Execution Windows")
    st.caption("Strict 'Breaker Open' to 'Breaker Closed' timeline.")
    
    if not df_fleet.empty:
        gantt_df = df_fleet.sort_values("Start Date").copy()

        # Smart Label Logic
        def get_smart_label(row):
            status = row["Status"]
            if status == "Execution": return "T-0 (Active)"
            if status == "Completed": return "Complete"
            
            # Future Logic based on Today
            if pd.notna(row["Start Date"]) and row["Start Date"] > SIMULATED_TODAY:
                days_until = (row["Start Date"] - SIMULATED_TODAY).days
                if days_until < 30: return "T-1 (Mob)"
                if days_until < 90: return "T-3"
                if days_until < 180: return "T-6"
                if days_until < 365: return "T-12"
                return "T-24"
            return "Planned"

        gantt_df["Label"] = gantt_df.apply(get_smart_label, axis=1)

        fig_fleet = px.timeline(
            gantt_df, 
            x_start="Start Date", x_end="End Date", 
            y="Site Name", color="Status", text="Label",
            hover_data=["Outage Type", "Plant Manager"],
            color_discrete_map={"Execution": "#ef4444", "Completed": "#10b981", "Planned": "#3b82f6"}
        )
        fig_fleet.add_vline(x=today_ts, line_width=2, line_dash="dot", line_color="red", annotation_text="Today")
        fig_fleet.update_yaxes(autorange="reversed")
        fig_fleet.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_fleet, use_container_width=True)

    st.markdown("---")

    # ==========================================================================
    # SECTION 2: TOLLGATE LIFECYCLE (The "8 Tollgates" View)
    # ==========================================================================
    st.subheader("2. Portfolio Tollgate Lifecycle (-2Y to +3Y)")
    st.caption("Visualizes the actual span of each Tollgate Phase based on project dates. 'Execution' reflects the full outage duration.")

    # Data Prep for Lifecycle
    lifecycle_rows = []
    
    # Iterate through each defined Outage in Fleet Status
    for _, outage in df_fleet.iterrows():
        uid = outage["OutageUID"]
        site = outage["Site Name"]
        
        # A. THE EXECUTION BAR (Source: Fleet Status - guarantees full length)
        lifecycle_rows.append({
            "Site": site,
            "OutageUID": uid,
            "Phase": "Execution (T-0)",
            "Start": outage["Start Date"],
            "End": outage["End Date"],
            "Color": "Execution"
        })

        # B. THE PLANNING/CLOSEOUT BARS (Source: Supermaster)
        # We group all projects for this outage by Tollgate
        outage_projects = df_projects[df_projects["OutageUID"] == uid]
        
        if not outage_projects.empty:
            tg_groups = outage_projects.groupby("Tollgate").agg(
                Min_Start=("Start Date", "min"),
                Max_End=("End Date", "max")
            ).reset_index()
            
            for _, tg_row in tg_groups.iterrows():
                tg_name = tg_row["Tollgate"]
                
                # Skip 'Execution' here because we used the robust Fleet Status dates above
                if tg_name == "Execution":
                    continue
                
                # Determine Color/Category
                if tg_name == "T+1":
                    color_grp = "Closeout"
                else:
                    color_grp = "Planning"

                lifecycle_rows.append({
                    "Site": site,
                    "OutageUID": uid,
                    "Phase": tg_name,
                    "Start": tg_row["Min_Start"],
                    "End": tg_row["Max_End"],
                    "Color": color_grp
                })

    # Plotting
    if lifecycle_rows:
        df_life = pd.DataFrame(lifecycle_rows)
        
        # Filter Window (Past 2Y to Future 3Y)
        start_window = SIMULATED_TODAY - timedelta(days=365*2)
        end_window = SIMULATED_TODAY + timedelta(days=365*3)
        df_viz = df_life[
            (df_life["End"] >= start_window) & 
            (df_life["Start"] <= end_window)
        ].copy()

        # Custom Color Map for Clarity
        # Planning = Blues, Execution = Red, Closeout = Green
        phase_colors = {
            "T-24": "#bfdbfe", # Very Light Blue
            "T-18": "#93c5fd",
            "T-12": "#60a5fa",
            "T-6":  "#3b82f6",
            "T-3":  "#2563eb",
            "T-1":  "#1d4ed8", # Dark Blue
            "Execution (T-0)": "#ef4444", # Red
            "T+1":  "#10b981"  # Green
        }

        # We map the specific Phase names to colors manually or use a discrete map
        fig_life = px.timeline(
            df_viz,
            x_start="Start", x_end="End",
            y="Site", 
            color="Phase",
            hover_data=["Phase", "Start", "End"],
            color_discrete_map=phase_colors,
            opacity=0.9
        )
        
        # Order the Legend logically
        legend_order = ["T-24", "T-18", "T-12", "T-6", "T-3", "T-1", "Execution (T-0)", "T+1"]
        fig_life.update_traces(legendgroup="Phase") 
        
        fig_life.add_vline(x=today_ts, line_width=2, line_dash="dot", line_color="red", annotation_text="Today")
        fig_life.update_yaxes(categoryorder="category ascending")
        fig_life.update_layout(
            height=500, 
            xaxis_title="Timeline", 
            yaxis_title="Site",
            legend_title="Tollgate Phase",
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_life, use_container_width=True)
    else:
        st.info("No lifecycle data available.")

    st.markdown("---")

    # ==========================================================================
    # SECTION 3 & 4 CONFIGURATION: DRILL-DOWN FILTERS
    # ==========================================================================
    st.subheader("3. System Execution Drill-Down")
    st.markdown("Select a specific Site and Outage to analyze system health.")

    # 1. CASCADING FILTERS (Site -> Outage -> System)
    f1, f2, f3 = st.columns(3)

    # --- FILTER 1: SITE ---
    with f1:
        st.caption("Select Site")
        # Use df_fleet (Matches your variable name)
        if "Site Name" in df_fleet.columns:
            all_sites = sorted(df_fleet["Site Name"].dropna().unique())
            
            # Default to "North Substation"
            default_site_idx = all_sites.index("North Substation") if "North Substation" in all_sites else 0
            selected_site = st.radio("Site", all_sites, index=default_site_idx, label_visibility="collapsed", key="dd_site")
        else:
            st.error("Column 'Site Name' missing in fleet data.")
            selected_site = None

    # --- FILTER 2: OUTAGE (Dependent on Site) ---
    with f2:
        st.caption("Select Outage Event")
        if selected_site:
            # Filter fleet for this site
            site_outages = df_fleet[df_fleet["Site Name"] == selected_site].copy()
            
            if not site_outages.empty:
                site_outages = site_outages.sort_values("Start Date")
                outage_options = site_outages["OutageUID"].unique()
                selected_outage_uid = st.radio("Outage", outage_options, index=0, label_visibility="collapsed", key="dd_outage")
            else:
                st.warning("No outages.")
                selected_outage_uid = None
        else:
            selected_outage_uid = None

    # --- PREPARE DATA FOR SELECTED OUTAGE ---
    if selected_outage_uid:
        # Get projects for this specific outage using df_projects
        drill_projects = df_projects[df_projects["OutageUID"] == selected_outage_uid].copy()
        
        # Detect Column Name (System vs Asset)
        group_col = "System" if "System" in drill_projects.columns else "Asset"
    else:
        drill_projects = pd.DataFrame()
        group_col = "System"

    # --- FILTER 3: SYSTEM (Dependent on Outage) ---
    with f3:
        st.caption(f"Select {group_col}")
        if not drill_projects.empty and group_col in drill_projects.columns:
            unique_systems = sorted(drill_projects[group_col].dropna().unique())
            
            # Default to "BOP" if available
            default_sys_idx = unique_systems.index("BOP") if "BOP" in unique_systems else 0
            
            if len(unique_systems) > 0:
                selected_system = st.radio("System", unique_systems, index=default_sys_idx, label_visibility="collapsed", key="dd_system")
            else:
                selected_system = None
        else:
            st.write("No systems found.")
            selected_system = None

    st.markdown("---")

    if not drill_projects.empty and selected_system:
        
        # ==========================================================================
        # SECTION 3 VIEW: SYSTEM HEALTH TABLE (Math Force)
        # ==========================================================================
        st.markdown(f"#####  {selected_site} - {selected_outage_uid} Health")

        # 1. Group by System for the summary table
        system_stats = drill_projects.groupby(group_col).agg(
            Total_Projects=("Project ID", "count"),
            Completed_Projects=("Status", lambda x: (x == "Completed").sum()),
            Budget=("Budget", "sum"),
            Actual=("Actual Cost", "sum")
        ).reset_index()

        # 2. THE FIX: Multiply by 1.0 to force float division
        # This prevents the "Integer Division" 0% error
        system_stats["Progress"] = (system_stats["Completed_Projects"] * 100.0) / system_stats["Total_Projects"]
        
        # Fill any NaNs with 0 in case a system has 0 projects
        system_stats["Progress"] = system_stats["Progress"].fillna(0)

        # 3. RENDER
        st.dataframe(
            system_stats,
            column_config={
                group_col: st.column_config.TextColumn("System", width="medium"),
                "Progress": st.column_config.ProgressColumn(
                    "Completion %",
                    format="%.0f%%", # Changed to 1 decimal place to verify it's moving
                    min_value=0.0,
                    max_value=100.0,
                ),
                "Budget": st.column_config.NumberColumn("Budget", format="$%d"),
                "Actual": st.column_config.NumberColumn("Actual", format="$%d"),
                "Total_Projects": st.column_config.NumberColumn("# Tasks"),
            },
            hide_index=True,
            use_container_width=True
        )

        # ==========================================================================
        # SECTION 4 VIEW: COMPRESSED GANTT
        # ==========================================================================
        st.markdown("---")
        st.markdown(f"#####  Timeline: {selected_system}")

        # Filter for the specific system selected in Radio Button 3
        final_drill_df = drill_projects[drill_projects[group_col] == selected_system].copy()
        
        if not final_drill_df.empty:
            if "Start Date" in final_drill_df.columns:
                final_drill_df = final_drill_df.sort_values("Start Date")

            # Compressed Height
            dynamic_height = max(60, len(final_drill_df) * 14 + 20)

            fig_gantt = px.timeline(
                final_drill_df,
                x_start="Start Date",
                x_end="End Date",
                y="Description", 
                color="Status",
                hover_data=["Project ID", "Project Manager", "Budget"],
                color_discrete_map={
                    "Completed": "#10b981",    
                    "In Progress": "#3b82f6", 
                    "Planned": "#94a3b8"       
                },
                height=dynamic_height
            )

            # ZERO PADDING LAYOUT
            fig_gantt.update_layout(
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis=dict(
                    title=None,
                    side="top",
                    tickformat="%d-%b",
                    showgrid=True,
                    gridcolor='rgba(0,0,0,0.1)'
                ),
                yaxis=dict(
                    title=None,
                    automargin=True,
                    tickfont=dict(size=10) # Small Task Labels
                ),
                legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, font=dict(size=10)),
                bargap=0.7
            )
            
            fig_gantt.update_yaxes(autorange="reversed")

            st.plotly_chart(fig_gantt, use_container_width=True)
        else:
            st.info(f"No timeline data for {selected_system}")

    else:
        st.info("Select a System above to view details.")