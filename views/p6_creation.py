import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import random
from utils.utils import load_csv, DATA_DIR

# --- CONSTANTS & PATHS ---
FLEET_PATH = os.path.join(DATA_DIR, "fleet_status.csv")
MASTER_PATH = os.path.join(DATA_DIR, "supermaster_project_list.csv")
SCHEDULE_PATH = os.path.join(DATA_DIR, "schedules.csv")
TEMPLATE_PATH = os.path.join(DATA_DIR, "p6_templates.csv")

# --- UID MAPPING ---
UID_TYPE_MAP = {
    "Planned - Major Overhaul": "MO",
    "Planned - Hot Gas Path": "HGP",
    "Planned - Combustion Inspection": "CI",
    "Steam Turbine Minor": "STM",
    "Generator Robotic Inspection": "GRI",
    "Forced - Exciter Diode Failure": "F_EDF" 
}

# --- CONTRACTOR LIST (Approved Vendors) ---
CONTRACTORS = [
    "GE Vernova", "Siemens Energy", "EthosEnergy", 
    "BrandSafway", "United Rentals", "Mistras Group", 
    "Local Union 55", "FieldCore", "APM"
]

# --- OUTAGE CONFIGURATION (Rules from SME) ---
OUTAGE_METADATA = {
    "Planned - Major Overhaul": {
        "ExecDuration": 75,
        "Phases": {
            "T-24": (-730, 0.02), "T-18": (-540, 0.10), "T-12": (-365, 0.15), 
            "T-6": (-180, 0.05), "T-3": (-90, 0.03), "T-1": (-30, 0.05), 
            "Execution": (0, 0.55), "T+1": (75, 0.05)
        }
    },
    "Planned - Hot Gas Path": {
        "ExecDuration": 45,
        "Phases": {
            "T-24": (-730, 0.02), "T-18": (-540, 0.15), "T-12": (-365, 0.20), 
            "T-6": (-180, 0.05), "T-3": (-90, 0.03), "T-1": (-30, 0.05), 
            "Execution": (0, 0.45), "T+1": (45, 0.05)
        }
    },
    "Planned - Combustion Inspection": {
        "ExecDuration": 28,
        "Phases": {
            "T-12": (-365, 0.15), "T-6": (-180, 0.05), "T-3": (-90, 0.02), 
            "T-1": (-30, 0.03), "Execution": (0, 0.70), "T+1": (28, 0.05)
        }
    },
    "Forced - Exciter Diode Failure": {
        "ExecDuration": 7,
        "Phases": {
            "Execution": (0, 0.95), "T+1": (7, 0.05)
        }
    }
}

# --- HELPER: CRITICAL PATH ENGINE (TIER 3) ---
def schedule_from_template(df_template, start_date):
    """Calculates detailed activity dates for schedules.csv"""
    df_sched = df_template.copy()
    start_map, finish_map = {}, {}

    def schedule_activity(act_id):
        if act_id in start_map: return
        row_series = df_sched[df_sched["ActivityID"] == act_id]
        if row_series.empty: return 
        row = row_series.iloc[0]
        
        preds = str(row.get("Predecessors", "")).strip()
        if preds and preds.lower() != "nan" and preds != "":
            pred_ids = [p.strip() for p in preds.replace(';', ',').split(",") if p.strip()]
            for p in pred_ids: schedule_activity(p)
            est = max([finish_map.get(p, datetime.combine(start_date, datetime.min.time())) for p in pred_ids], default=datetime.combine(start_date, datetime.min.time()))
        else:
            est = datetime.combine(start_date, datetime.min.time())
            
        dur = int(row.get("DurationDays", 0))
        start_map[act_id] = est
        finish_map[act_id] = est + timedelta(days=dur)

    for act_id in df_sched["ActivityID"]:
        schedule_activity(act_id)

    df_sched["EarlyStart"] = df_sched["ActivityID"].map(start_map)
    df_sched["EarlyFinish"] = df_sched["ActivityID"].map(finish_map)
    return df_sched

def render(access_code: str = "R"):
    st.markdown("### 🏗️ Oracle Primavera P6 Integration")
    st.markdown("#### Create New Fleet Outage Event")

    if access_code != "RW":
        st.error("⛔ **Access Denied**: You do not have permission to schedule new outages.")
        return

    # 1. LOAD DATA
    try:
        df_fleet = load_csv("fleet_status.csv")
        df_templates = pd.read_csv(TEMPLATE_PATH) if os.path.exists(TEMPLATE_PATH) else pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return

    # Data Prep
    site_lookup = df_fleet[["Site Name", "Code", "Region", "Plant Manager"]].drop_duplicates("Site Name").set_index("Site Name")
    available_templates = sorted(df_templates["TemplateName"].dropna().unique().tolist()) if not df_templates.empty else []

    # 2. UI INPUTS
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            # --- FIX: DATA CLEANING FOR SITE LIST ---
            # Get unique values, filter out NaNs/Floats, ensure they are strings
            raw_sites = site_lookup.index.unique().tolist()
            existing_sites = sorted([str(s) for s in raw_sites if pd.notna(s) and str(s).strip() != ""])
            
            sel_site = st.selectbox("Select Facility / Site", existing_sites)
            
            if not site_lookup.empty and sel_site in site_lookup.index:
                site_data = site_lookup.loc[sel_site]
                site_details = site_data.iloc[0] if isinstance(site_data, pd.DataFrame) else site_data
                st.caption(f"📍 Region: {site_details['Region']} | Code: {site_details['Code']}")
            else:
                st.error("Site data not found.")
                return

        with c2:
            sel_template = st.selectbox("Select P6 Template", available_templates)
            
        st.divider()
        c3, c4 = st.columns(2)
        with c3:
            today = datetime.today().date()
            start_date = st.date_input("Outage Execution Start", value=today + timedelta(days=365))
        with c4:
            budget_input = st.number_input("Total Approved Budget ($M)", min_value=0.0, value=5.0, step=0.1)

        submit_btn = st.button("🚀 Generate Outage (Triple-Write)", type="primary", use_container_width=True)

        if submit_btn and sel_template:
            with st.spinner("Calculating Critical Path & Syncing Databases..."):
                time.sleep(1)

                # --- STEP 1: GENERATE OUTAGE UID ---
                short_type = UID_TYPE_MAP.get(sel_template, "UNK")
                outage_uid = f"{site_details['Code']}_{short_type}_{start_date.year}"
                
                subset = df_templates[df_templates["TemplateName"] == sel_template].copy()
                if subset.empty:
                    st.error("No template data found for this outage type.")
                    return

                # --- STEP 2: CALCULATE DATES & BUDGETS ---
                meta = OUTAGE_METADATA.get(sel_template, {})
                exec_duration = meta.get("ExecDuration", 30)
                phase_rules = meta.get("Phases", {})
                
                phase_counts = subset['Phase'].value_counts().to_dict()
                
                new_master_rows = []
                
                for _, row in subset.iterrows():
                    phase = row['Phase']
                    asset = row['Responsibility'] 
                    desc = row['ActivityName']
                    
                    # Defaults
                    task_start = start_date
                    budget_alloc = 0.0
                    
                    # Apply Logic
                    if phase in phase_rules:
                        offset_days, budget_pct = phase_rules[phase]
                        
                        # Date Logic: Relative to Execution Start
                        task_start = start_date + timedelta(days=offset_days)
                        # Random Jitter (0-3 days)
                        task_start = task_start + timedelta(days=random.randint(0, 3))
                        task_end = task_start + timedelta(days=int(row['DurationDays']))
                        
                        # Budget Logic
                        total_phase_budget = (budget_input * 1_000_000) * budget_pct
                        count = phase_counts.get(phase, 1)
                        base_budget = total_phase_budget / count
                        budget_alloc = base_budget * random.uniform(0.8, 1.2)
                    else:
                        task_end = start_date + timedelta(days=int(row['DurationDays']))

                    proj_id = f"PRJ-{site_details['Code']}-{row['ActivityID']}"

                    new_master_rows.append({
                        "OutageUID": outage_uid,
                        "Site Name": sel_site,
                        "Project ID": proj_id,
                        "Description": desc,
                        "Asset": asset,
                        "Sub-System": "",
                        "Status": "Planned",
                        "Tollgate": phase,
                        "Start Date": task_start.strftime("%d-%m-%Y"),
                        "End Date": task_end.strftime("%d-%m-%Y"),
                        "Budget": round(budget_alloc, 2),
                        "Actual Cost": 0.0,
                        "Contractor": random.choice(CONTRACTORS),
                        "Project Manager": site_details["Plant Manager"],
                        "TollgateLateFlag": False
                    })
                
                # --- FIX: FLEET STATUS DATES ---
                f_start_dt = start_date
                f_end_dt = start_date + timedelta(days=exec_duration)

                # --- STEP 3: WRITE DATA ---

                # A. FLEET STATUS
                new_fleet_row = {
                    "Site Name": sel_site,
                    "Code": site_details["Code"],
                    "Region": site_details["Region"],
                    "Status": "Planned",
                    "Outage Type": sel_template,
                    "Start Date": f_start_dt.strftime("%d-%m-%Y"),
                    "End Date": f_end_dt.strftime("%d-%m-%Y"),
                    "Duration (Days)": exec_duration,
                    "Total Budget ($M)": budget_input,
                    "Plant Manager": site_details["Plant Manager"],
                    "OutageUID": outage_uid
                }

                # B. SUPERMASTER
                df_master_new = pd.DataFrame(new_master_rows)
                schema_cols = ["OutageUID", "Site Name", "Project ID", "Description", "Asset", 
                               "Sub-System", "Status", "Tollgate", "Start Date", "End Date", 
                               "Budget", "Actual Cost", "Contractor", "Project Manager", "TollgateLateFlag"]
                
                for c in schema_cols:
                    if c not in df_master_new.columns: df_master_new[c] = ""
                df_master_new = df_master_new[schema_cols]

                try:
                    # 1. Fleet
                    if os.path.exists(FLEET_PATH):
                        pd.DataFrame([new_fleet_row]).to_csv(FLEET_PATH, mode='a', header=False, index=False)
                    else:
                        pd.DataFrame([new_fleet_row]).to_csv(FLEET_PATH, mode='w', header=True, index=False)

                    # 2. Master
                    if os.path.exists(MASTER_PATH):
                        df_master_new.to_csv(MASTER_PATH, mode='a', header=False, index=False)
                    else:
                        df_master_new.to_csv(MASTER_PATH, mode='w', header=True, index=False)
                    
                    # 3. Schedule
                    sched_result = schedule_from_template(subset, start_date)
                    sched_result["OutageUID"] = outage_uid
                    sched_result["ProjectID"] = f"{outage_uid}-EXEC"
                    sched_result["Status"] = "Planned"
                    if os.path.exists(SCHEDULE_PATH):
                        sched_result.to_csv(SCHEDULE_PATH, mode='a', header=False, index=False)
                    else:
                        sched_result.to_csv(SCHEDULE_PATH, mode='w', header=True, index=False)
                        # Inside p6_creation.py, after the .to_csv() lines:
                    st.cache_data.clear()
                    st.success(f"✅ Outage {outage_uid} created and Tollgates updated!")

                    st.balloons()
                    st.success(f"✅ Outage **{outage_uid}** created successfully!")
                    st.success(f"📅 Execution Window: {f_start_dt.strftime('%d-%b-%Y')} to {f_end_dt.strftime('%d-%b-%Y')} ({exec_duration} days)")
                    st.info(f"📊 Generated {len(new_master_rows)} project lines (T-24 through T+1) with Contractor Assignments.")

                except Exception as e:
                    st.error(f"Write Error: {e}")