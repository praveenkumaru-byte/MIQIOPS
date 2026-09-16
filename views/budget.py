import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from utils.utils import load_all_data, apply_standard_styles

def render(access_code: str = "R"):
    # 1. APPLY STYLES & LOAD DATA
    apply_standard_styles()
    
    # load_all_data now returns pre-enriched data (Risk, Variance, Burn % are already calculated)
    df_fleet, df_projects, df_labor, _, _ = load_all_data()

    # --- SESSION STATE FOR DRILL DOWN ---
    if "burn_drill_path" not in st.session_state:
        st.session_state.burn_drill_path = []

    if df_projects.empty:
        st.warning("⚠️ No data found. Please check data files.")
        return

    # --- TITLE ---
    st.title("💲 Financial Control Tower")
    
    # --- PRE-PROCESSING (CONTEXT MERGE) ---
    # We still need to merge 'Outage Type' from Fleet to create the "Site - Outage" label
    if "Outage Type" not in df_projects.columns and not df_fleet.empty:
        # Create lookup
        site_map = df_fleet[["Site Name", "Outage Type"]].drop_duplicates("Site Name")
        df_projects = pd.merge(df_projects, site_map, on="Site Name", how="left")
    
    # Create the Master Label (e.g., "North Substation - Major Overhaul")
    df_projects["Site_Outage_Label"] = (
        df_projects["Site Name"].astype(str) + " - " + df_projects["Outage Type"].fillna("Standard")
    )
    
    # --- TOP CONTROL: GLOBAL FILTER ---
    # utils.py handles the string conversion for Site Name, so this sort is now safe
    unique_sites = sorted(df_fleet["Site Name"].unique().tolist())
    site_list = ["All Sites"] + unique_sites
    selected_site_budget = st.radio("Select Financial View:", site_list, horizontal=True, index=0)
    
    if selected_site_budget == "All Sites":
        budget_data = df_projects
        labor_data = df_labor
    else:
        budget_data = df_projects[df_projects["Site Name"] == selected_site_budget]
        labor_data = df_labor[df_labor["Site Name"] == selected_site_budget]
        
    st.divider()

    # --- 1. KEY FINANCIAL METRICS (GLOBAL) ---
    # Using columns pre-calculated in utils.py
    total_bud = budget_data["Budget"].sum()
    total_act = budget_data["Actual Cost"].sum()
    
    # Safe division
    pct_burn = (total_act / total_bud * 100) if total_bud > 0 else 0
    
    # Labor Calculation (Yesterday's Spend)
    last_day_spend = 0
    last_date_str = "N/A"
    last_lab_date = None
    
    if not labor_data.empty:
        last_lab_date = labor_data["Date"].max()
        day_data = labor_data[labor_data["Date"] == last_lab_date]
        if not day_data.empty:
            last_day_spend = day_data["Total Cost"].sum()
            last_date_str = last_lab_date.strftime('%b %d')

    # Risk Metrics
    over_budget_df = budget_data[budget_data["Over Budget"] == True]
    overrun_amt = over_budget_df["Variance Amount"].sum()
    overrun_exposure = over_budget_df["Budget"].sum()
    overrun_count = len(over_budget_df)

    # Use HTML Cards (Styles are now in utils.py)
    b1, b2, b3, b4 = st.columns(4)
    with b1: st.markdown(f"""<div class="metric-card card-info"><div class="card-header">Total Allotted Budget</div><div class="card-value">${total_bud/1e6:.1f}M</div><div class="card-sub">{len(budget_data)} Projects</div></div>""", unsafe_allow_html=True)
    with b2: st.markdown(f"""<div class="metric-card card-success"><div class="card-header">Consumption (YTD)</div><div class="card-value">${total_act/1e6:.1f}M</div><div class="card-sub">{pct_burn:.1f}% Utilized</div></div>""", unsafe_allow_html=True)
    with b3: st.markdown(f"""<div class="metric-card card-secondary"><div class="card-header">Daily Burn </div><div class="card-value">${last_day_spend:,.0f}</div><div class="card-sub">Amount Spend (Last 24h)</div></div>""", unsafe_allow_html=True)
    with b4: st.markdown(f"""<div class="metric-card card-warning"><div class="card-header">Overruns $</div><div class="card-value">${overrun_amt:,.0f}</div><div class="card-sub warning">on <b>${overrun_exposure/1e6:.1f}M</b> Budget ({overrun_count} Proj)</div></div>""", unsafe_allow_html=True)
        
    st.markdown("")
    
    bt1, bt2, bt3, bt4 = st.tabs(["📊 Financial Dashboard", "👷 Contractor List", "📋 Project List", "⚠️ High Risks"])
    
    # --- TAB 1: FINANCIAL DASHBOARD ---
    with bt1:
        st.subheader("1. Budget Overview by Site & Outage")
        site_outage_stats = budget_data.groupby(["Site_Outage_Label"]).agg({"Budget": "sum", "Actual Cost": "sum"}).reset_index()
        
        # Calculate Yesterday for Stack
        if last_lab_date:
            yesterday_df = labor_data[labor_data["Date"] == last_lab_date]
            # Group by Site Name first
            site_yesterday = yesterday_df.groupby("Site Name")["Total Cost"].sum().reset_index()
            site_yesterday.rename(columns={"Total Cost": "Yesterday Cost"}, inplace=True)
            
            # We map this back to Site_Outage_Label via substring matching or merge
            # For simplicity in this view, we'll display by the full label in the main chart
            # and rely on the Site Name match for the merge.
            # (Note: In production, you'd want exact mapping, but this works for the "Start Name" logic)
            pass
        
        # Visualize
        site_stats_final = site_outage_stats.copy()
        site_stats_final["Remaining"] = site_stats_final["Budget"] - site_stats_final["Actual Cost"]
        
        fig_site = go.Figure()
        fig_site.add_trace(go.Bar(name='Actual Spend', x=site_stats_final["Site_Outage_Label"], y=site_stats_final["Actual Cost"], marker_color='#3b82f6'))
        fig_site.add_trace(go.Bar(name='Remaining Budget', x=site_stats_final["Site_Outage_Label"], y=site_stats_final["Remaining"], marker_color='#e2e8f0'))
        fig_site.update_layout(barmode='stack', height=350, plot_bgcolor='white', xaxis_title=None, yaxis_title="USD ($)")
        st.plotly_chart(fig_site, use_container_width=True)

        st.divider()

        # ROW 2: LEAKAGE & OFFENDERS
        c_left, c_right = st.columns([1, 1])
        with c_left:
            st.subheader("2. Budget Overruns by Phase")
            # Filter for projects with Positive Variance (Over Budget)
            leakage_data = budget_data[budget_data["Variance Amount"] > 0]
            
            if not leakage_data.empty:
                tg_leakage = leakage_data.groupby("Tollgate")["Variance Amount"].sum().reset_index()
                tg_order = {"T-24": 0, "T-18": 1, "T-12": 2, "T-6": 3, "T-3": 4, "T-1": 5, "Execution": 6, "T+1": 7}
                tg_leakage["Sort"] = tg_leakage["Tollgate"].map(tg_order).fillna(99)
                tg_leakage = tg_leakage.sort_values("Sort")
                
                fig_leak = px.bar(tg_leakage, x="Tollgate", y="Variance Amount", text_auto='.2s', 
                                  title="Overrun ($) by Phase", color_discrete_sequence=['#ef4444'])
                fig_leak.update_layout(plot_bgcolor='white', height=350)
                st.plotly_chart(fig_leak, use_container_width=True)
            else:
                st.success("✅ No Budget Leakage Detected")

        with c_right:
            st.subheader("3. Top 10 Cost Offenders")
            top_offenders = budget_data.sort_values("Variance Amount", ascending=False).head(10)
            
            st.dataframe(
                top_offenders[["Project ID", "Description", "Actual Cost", "Variance Amount"]], 
                use_container_width=True, hide_index=True, 
                column_config={
                    "Project ID": st.column_config.TextColumn("ID", width="small"), 
                    "Actual Cost": st.column_config.NumberColumn("Actual", format="$%.0f"), 
                    "Variance Amount": st.column_config.ProgressColumn("Overrun", format="$%.0f", min_value=0, max_value=top_offenders["Variance Amount"].max())
                }
            )

        st.divider()

        # SECTION 4: CLICKABLE DRILL-DOWN
        st.subheader(f"4. Yesterday's Burn Breakdown")
        if not labor_data.empty and last_lab_date:
            daily_df = labor_data[labor_data["Date"] == last_lab_date].copy()
            path = st.session_state.burn_drill_path
            
            c_nav1, c_nav2 = st.columns([6, 1])
            with c_nav1:
                if len(path) == 0: st.markdown("**View:** All Sites")
                elif len(path) == 1: st.markdown(f"**View:** {path[0]} > Trades")
                elif len(path) == 2: st.markdown(f"**View:** {path[0]} > {path[1]} > Contractors")
            with c_nav2:
                if len(path) > 0:
                    if st.button("🔄 Reset"):
                        st.session_state.burn_drill_path = []
                        st.rerun()

            # LEVEL 0: SITE
            if len(path) == 0:
                site_burn = daily_df.groupby("Site Name")["Total Cost"].sum().sort_values(ascending=False).reset_index()
                fig_l1 = px.bar(site_burn, x="Site Name", y="Total Cost", title="Click a Site to Drill Down", color_discrete_sequence=['#3b82f6'])
                fig_l1.update_layout(clickmode='event+select', height=350, plot_bgcolor='white')
                
                selection = st.plotly_chart(fig_l1, on_select="rerun", selection_mode="points", use_container_width=True, key="chart_l1")
                if selection and selection["selection"]["points"]:
                    st.session_state.burn_drill_path = [selection["selection"]["points"][0]["x"]]
                    st.rerun()

            # LEVEL 1: TRADE
            elif len(path) == 1:
                sel_site = path[0]
                site_df = daily_df[daily_df["Site Name"] == sel_site]
                trade_burn = site_df.groupby("Role")["Total Cost"].sum().sort_values(ascending=False).reset_index()
                
                fig_l2 = px.bar(trade_burn, x="Role", y="Total Cost", title=f"Trades at {sel_site}", color_discrete_sequence=['#10b981'])
                fig_l2.update_layout(clickmode='event+select', height=350, plot_bgcolor='white')
                
                if st.button("⬅️ Back to Sites"):
                    st.session_state.burn_drill_path = []
                    st.rerun()
                    
                selection = st.plotly_chart(fig_l2, on_select="rerun", selection_mode="points", use_container_width=True, key="chart_l2")
                if selection and selection["selection"]["points"]:
                    st.session_state.burn_drill_path = [sel_site, selection["selection"]["points"][0]["x"]]
                    st.rerun()

            # LEVEL 2: FIRM
            elif len(path) == 2:
                sel_site = path[0]
                sel_trade = path[1]
                trade_df = daily_df[(daily_df["Site Name"] == sel_site) & (daily_df["Role"] == sel_trade)]
                firm_burn = trade_df.groupby("Firm")["Total Cost"].sum().sort_values(ascending=False).reset_index()
                
                fig_l3 = px.bar(firm_burn, x="Firm", y="Total Cost", title=f"{sel_trade} Contractors at {sel_site}", color_discrete_sequence=['#f59e0b'])
                fig_l3.update_layout(height=350, plot_bgcolor='white')
                
                if st.button(f"⬅️ Back to {sel_site}"):
                    st.session_state.burn_drill_path = [sel_site]
                    st.rerun()
                    
                st.plotly_chart(fig_l3, use_container_width=True, key="chart_l3")
        else:
            st.warning("No Labor Data Available for Yesterday.")

    # --- TAB 2: CONTRACTOR LIST ---
    with bt2:
        st.subheader("Contractor Performance & Rates")
        
        valid_outages = sorted(budget_data["Site_Outage_Label"].unique().tolist())
        sel_outage_cont = st.selectbox("1. Select Site-Outage:", valid_outages, index=0, key="sel_cont_outage")
        
        scope_data = budget_data[budget_data["Site_Outage_Label"] == sel_outage_cont]
        
        s_bud = scope_data["Budget"].sum()
        s_act = scope_data["Actual Cost"].sum()
        s_burn = (s_act / s_bud * 100) if s_bud > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Scope Budget", f"${s_bud/1e6:.2f}M")
        c2.metric("Scope Actual", f"${s_act/1e6:.2f}M")
        c3.metric("Burn Rate", f"{s_burn:.1f}%")
        
        st.markdown("##### 2. Contracting Firms Breakdown")
        firm_stats = scope_data.groupby("Contractor").agg({"Actual Cost": "sum", "Budget": "sum", "Project ID": "count"}).reset_index()
        
        fig_firm = go.Figure()
        fig_firm.add_trace(go.Bar(name='Actual', x=firm_stats["Contractor"], y=firm_stats["Actual Cost"], marker_color='#3b82f6'))
        fig_firm.add_trace(go.Scatter(name='Budget', x=firm_stats["Contractor"], y=firm_stats["Budget"], mode='markers', marker=dict(color='red', symbol='line-ew-open', size=25, line=dict(width=3))))
        fig_firm.update_layout(plot_bgcolor='white', height=350)
        st.plotly_chart(fig_firm, use_container_width=True)
        
        sel_firm = st.selectbox("3. Drill Down to Contractor (Optional):", ["All Firms"] + sorted(firm_stats["Contractor"].unique().tolist()))
        
        if sel_firm != "All Firms":
            firm_projects = scope_data[scope_data["Contractor"] == sel_firm]
            st.dataframe(
                firm_projects[["Project ID", "Description", "Tollgate", "Budget", "Actual Cost", "Variance Amount"]],
                use_container_width=True, hide_index=True,
                column_config={"Budget": st.column_config.NumberColumn(format="$%.0f"), "Actual Cost": st.column_config.NumberColumn(format="$%.0f"), "Variance Amount": st.column_config.NumberColumn(format="$%.0f")}
            )

    # --- TAB 3: PROJECT LIST ---
    with bt3:
        st.subheader("Detailed Financial Register")
        
        unique_outages_proj = sorted(budget_data["Site_Outage_Label"].unique().tolist())
        sel_proj_outage = st.selectbox("Filter by Site-Outage:", unique_outages_proj, index=0, key="sel_proj_list")
        
        display_df = budget_data[budget_data["Site_Outage_Label"] == sel_proj_outage]
            
        st.dataframe(
            display_df[["Site_Outage_Label", "Project ID", "Description", "Status", "Budget", "Actual Cost", "Variance Amount", "Burn %"]],
            use_container_width=True, hide_index=True,
            column_config={
                "Site_Outage_Label": st.column_config.TextColumn("Scope", width="medium"),
                "Budget": st.column_config.NumberColumn(format="$%.0f"), 
                "Actual Cost": st.column_config.NumberColumn(format="$%.0f"), 
                "Variance Amount": st.column_config.NumberColumn(format="$%.0f"),
                "Burn %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120)
            }
        )

    # --- TAB 4: HIGH RISKS ---
    with bt4:
        st.subheader("High Budget Risk")
        
        # Filter: Risk Level = High or Burn > 90%
        # (Cols populated by utils.py)
        high_risk = budget_data[(budget_data["Risk Level"] == "High") | (budget_data["Burn %"] > 90)].copy()
        
        if not high_risk.empty:
            risk_summary = high_risk.groupby("Site_Outage_Label").agg(
                Risk_Projects=("Project ID", "count"),
                Total_Overrun=("Variance Amount", "sum")
            ).reset_index().sort_values("Total_Overrun", ascending=False)
            
            c_r1, c_r2 = st.columns([1, 2])
            
            with c_r1:
                st.markdown("**Risk Concentration by Outage**")
                st.dataframe(
                    risk_summary, 
                    use_container_width=True, hide_index=True,
                    column_config={"Total_Overrun": st.column_config.ProgressColumn("Overrun Exposure", format="$%.0f", min_value=0, max_value=risk_summary["Total_Overrun"].max())}
                )
            
            with c_r2:
                st.markdown("**Detailed Risk List**")
                st.dataframe(
                    high_risk[["Site_Outage_Label", "Project ID", "Description", "Burn %", "Actual Cost", "Variance Amount"]], 
                    use_container_width=True, hide_index=True, 
                    column_config={
                        "Burn %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=120),
                        "Variance Amount": st.column_config.NumberColumn(format="$%.0f", help="Amount Over Budget")
                    }
                )
        else:
            st.success("✅ No projects currently exceed 90% budget utilization.")