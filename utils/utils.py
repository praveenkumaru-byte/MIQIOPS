import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, GridUpdateMode
import base64
from github import Github, GithubException

# ==============================================================================
# 1. FILESYSTEM & SETUP
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
ASSETS_DIR = BASE_DIR / "assets"
SIMULATED_TODAY = datetime(2026, 1, 30)

@st.cache_data
def load_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)

# ==============================================================================
# 2. DATA LOADING & LOGIC ENGINE (The Hybrid)
# ==============================================================================

def enrich_project_data(df_projects):
    """
    CENTRAL LOGIC ENGINE:
    - Fixes data types (str -> float) for financials
    - Calculates Risk (High/Medium/Low)
    - Calculates Variance & Burn %
    """
    if df_projects.empty: return df_projects

    # A. Sanitize Financials
    for col in ["Budget", "Actual Cost", "Variance Amount"]:
        if col in df_projects.columns:
            df_projects[col] = pd.to_numeric(df_projects[col], errors="coerce").fillna(0)

    # B. Calculate Derivatives
    if "Variance Amount" not in df_projects.columns:
        df_projects["Variance Amount"] = df_projects["Actual Cost"] - df_projects["Budget"]
    
    df_projects["Over Budget"] = df_projects["Actual Cost"] > df_projects["Budget"]
    
    # Avoid Div/0
    df_projects["Burn %"] = (df_projects["Actual Cost"] / df_projects["Budget"] * 100).fillna(0)
    df_projects["Burn %"] = df_projects["Burn %"].replace([float('inf'), -float('inf')], 0)

    # C. Risk Calculation
    def get_risk(row):
        is_late = False
        if pd.notna(row.get("End Date")) and row.get("Status") != "Completed":
            try:
                # We assume End Date is already datetime from load_all_data
                if row["End Date"] < SIMULATED_TODAY: is_late = True
            except: pass
        
        is_over = row["Over Budget"]
        
        if is_late and is_over: return "High"
        if is_late or is_over: return "Medium"
        return "Low"

    df_projects["Risk Level"] = df_projects.apply(get_risk, axis=1)
    
    # Backward compatibility flags for older views
    df_projects["Late"] = df_projects["Risk Level"].isin(["High", "Medium"])
    df_projects["TollgateLateFlag"] = df_projects["Risk Level"].isin(["High", "Medium"]) 
    
    return df_projects

@st.cache_data
def load_all_data():
    """
    Robust Loader that:
    1. Loads CSVs
    2. DROPS empty rows (Fixes the TypeError crash)
    3. Formats Dates
    4. Enriches with Risk/Financial math
    """
    try:
        # 1. Load Files
        df_projects = load_csv("supermaster_project_list.csv")
        df_fleet = load_csv("fleet_status.csv")

        try:
            df_labor = load_csv("labor_history.csv")
            if not df_labor.empty:
                df_labor["Date"] = pd.to_datetime(df_labor["Date"], format="mixed", errors="coerce")
        except:
            df_labor = pd.DataFrame()

        # 2. CRITICAL FIX: Sanitize "Site Name" to prevent 'float' vs 'str' sort error
        # This removes rows where Site Name is NaN, or converts them to string
        if not df_fleet.empty:
            df_fleet = df_fleet.dropna(subset=["Site Name"]) 
            df_fleet["Site Name"] = df_fleet["Site Name"].astype(str)
        
        if not df_projects.empty:
            df_projects = df_projects.dropna(subset=["Site Name"])
            df_projects["Site Name"] = df_projects["Site Name"].astype(str)

        # 3. Date Parsing & Cleanup (Restored from utils4.py)
        for df in [df_fleet, df_projects]:
            if df.empty: continue
            for col in ["Start Date", "End Date"]:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], format="mixed", dayfirst=True, errors="coerce")
            
            # Drop invalid dates (Essential for Gantt charts)
            df.dropna(subset=["Start Date", "End Date"], inplace=True)

        # 4. Fleet Tollgate Calculation
        if not df_fleet.empty:
            def get_current_tollgate(row):
                if row["End Date"] < SIMULATED_TODAY: return "T+1"
                elif row["Start Date"] <= SIMULATED_TODAY <= row["End Date"]: return "T0"
                else:
                    days_until = (row["Start Date"] - SIMULATED_TODAY).days
                    months_until = days_until / 30
                    if months_until <= 1: return "T-1"
                    elif months_until <= 3: return "T-3"
                    elif months_until <= 6: return "T-6"
                    elif months_until <= 12: return "T-12"
                    else: return "T-24"
            df_fleet["Current Toll Gate"] = df_fleet.apply(get_current_tollgate, axis=1)

        # 5. Project Enrichment (Risk Engine)
        if not df_projects.empty:
            df_projects = enrich_project_data(df_projects)

        return df_fleet, df_projects, df_labor, pd.DataFrame(), SIMULATED_TODAY

    except Exception as e:
        st.error(f"Data Load Error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), datetime.now()

# ==============================================================================
# 3. RBAC & PERMISSION LOGIC (Restored)
# ==============================================================================
@st.cache_data
def load_rbac() -> pd.DataFrame:
    return load_csv("RBAC.csv")

def get_persona_columns(rbac_df: pd.DataFrame):
    return list(rbac_df.columns[3:]) if not rbac_df.empty else []

def get_persona_access_map(rbac_df: pd.DataFrame, persona: str):
    if rbac_df.empty or persona not in rbac_df.columns:
        return {}
    access = {}
    for _, row in rbac_df.iterrows():
        page_id = row["PageID"]
        access_code = str(row[persona]).strip()
        access[page_id] = access_code
    return access

def get_access_label(code: str) -> str:
    if code == "RW": return "Write"
    if code == "R": return "Read-only"
    if code == "X": return "Restricted"
    return "Unknown"

# ==============================================================================
# 4. STYLING & ASSETS (Restored Full CSS)
# ==============================================================================
def load_logo():
    path = ASSETS_DIR / "MIQ-Logo.jpg"
    return str(path) if path.exists() else "https://via.placeholder.com/150x50?text=MaverickIQ"

def inject_global_css():
    st.markdown(
        """
        <style>
        /* A. GLOBAL RESET */
        .main { background-color: #f5f7fb; color: #111827; }
        header[data-testid="stHeader"] { visibility: hidden; }
        .block-container { padding-top: 1rem !important; padding-bottom: 3rem !important; }

        /* B. SIDEBAR STYLING */
        section[data-testid="stSidebar"] {
            background-color: #dfe4ea; 
        }

        /* C. CARD CONTAINERS */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            background-color: #dfe4ea;   
            border: 1px solid #1e3a8a;   
            border-radius: 10px;
            padding: 0.75rem 1rem;
        }

        /* D. FORM ELEMENTS */
        div[data-testid="stSelectbox"] > div > div {
            background-color: #ffffff !important; 
            border: 1px solid #94a3b8 !important; 
            color: #1e293b !important;
            border-radius: 6px;
        }
        
        /* E. LEGACY METRIC CARDS (For budget.py) */
        .metric-card {
            background-color: #ffffff; padding: 20px; border-radius: 8px;
            border-left: 5px solid #007bff; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }
        .card-header { color: #6c757d; font-size: 12px; text-transform: uppercase; font-weight: 700; }
        .card-value { font-size: 24px; font-weight: 800; color: #212529; }
        .card-delta { font-size: 12px; font-weight: 600; margin-left: 8px; }
        .card-critical { border-left: 5px solid #dc3545 !important; }
        .card-warning { border-left: 5px solid #ffc107 !important; }
        .card-success { border-left: 5px solid #28a745 !important; }
        .card-info { border-left: 5px solid #17a2b8 !important; }
        .card-secondary { border-left: 5px solid #6c757d !important; }

        /* F. MODERN KPI CARDS */
        .miq-kpi-card { background-color: #ffffff; border-radius: 12px; padding: 0.9rem 1.1rem; box-shadow: 0 4px 10px rgba(15, 23, 42, 0.06); border-left: 4px solid #2563eb; }
        .miq-kpi-card.kpi-green { border-left-color: #16a34a; }
        .miq-kpi-card.kpi-amber { border-left-color: #f97316; }
        .miq-kpi-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; color: #6b7280; margin-bottom: 0.35rem; }
        .miq-kpi-value { font-size: 1.4rem; font-weight: 700; color: #111827; margin-bottom: 0.15rem; }
        
        </style>
        """,
        unsafe_allow_html=True,
    )

def apply_standard_styles():
    """Alias for backward compatibility"""
    inject_global_css()

def render_styled_aggrid(df, key=None, height=350):
    """
    Reusable component to render a styled AgGrid table.
    """
    # Standard JS for coloring cells (Green/Blue/Orange gradients)
    avail_style = JsCode("""function(params) { return {'background': 'linear-gradient(90deg, rgba(32, 201, 151, 0.3) ' + params.value + '%, transparent ' + params.value + '%)', 'backgroundRepeat': 'no-repeat', 'backgroundPosition': 'center', 'backgroundSize': '100% 50%', 'textAlign': 'center', 'color': '#099268', 'fontWeight': 'bold'}; }""")
    rel_style = JsCode("""function(params) { return {'background': 'linear-gradient(90deg, rgba(77, 171, 247, 0.3) ' + params.value + '%, transparent ' + params.value + '%)', 'backgroundRepeat': 'no-repeat', 'backgroundPosition': 'center', 'backgroundSize': '100% 50%', 'textAlign': 'center', 'color': '#1971c2', 'fontWeight': 'bold'}; }""")
    eff_style = JsCode("""function(params) { return {'background': 'linear-gradient(90deg, rgba(253, 126, 20, 0.3) ' + params.value + '%, transparent ' + params.value + '%)', 'backgroundRepeat': 'no-repeat', 'backgroundPosition': 'center', 'backgroundSize': '100% 50%', 'textAlign': 'center', 'color': '#e8590c', 'fontWeight': 'bold'}; }""")

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True)
    
    # Auto-detect columns to style if they exist
    if "Availability" in df.columns:
        gb.configure_column("Availability", type=["numericColumn"], valueFormatter="x.toFixed(1) + '%'", cellStyle=avail_style)
    if "Reliability" in df.columns:
        gb.configure_column("Reliability", type=["numericColumn"], valueFormatter="x.toFixed(1) + '%'", cellStyle=rel_style)
    if "Efficiency" in df.columns:
        gb.configure_column("Efficiency", type=["numericColumn"], valueFormatter="x.toFixed(1) + '%'", cellStyle=eff_style)

    # Pin first column (usually Site Name)
    first_col = df.columns[0]
    gb.configure_column(first_col, pinned="left", cellStyle={'fontWeight': '600'})

    grid_options = gb.build()
    
    return AgGrid(
        df, 
        gridOptions=grid_options, 
        height=height, 
        theme="alpine", 
        allow_unsafe_jscode=True,
        key=key
    )

def save_csv_to_github(filename: str, df: pd.DataFrame, commit_message: str = "Update data via Streamlit") -> bool:
    """
    Saves a Pandas DataFrame to data/<filename> in both the local runtime 
    and the remote GitHub repository.
    """
    # 1. Local Write (keeps active session immediate)
    local_path = DATA_DIR / filename
    df.to_csv(local_path, index=False)

    # 2. Remote GitHub Write via Secrets
    if "github" not in st.secrets:
        # Fallback for local dev when no github secrets configured
        return True

    try:
        token = st.secrets["github"]["token"]
        repo_name = st.secrets["github"]["repo"]
        branch = st.secrets["github"].get("branch", "main")
        
        g = Github(token)
        repo = g.get_repo(repo_name)
        github_file_path = f"data/{filename}"
        
        csv_content = df.to_csv(index=False)

        try:
            # Check if file already exists on GitHub to obtain its SHA
            remote_file = repo.get_contents(github_file_path, ref=branch)
            repo.update_file(
                path=github_file_path,
                message=commit_message,
                content=csv_content,
                sha=remote_file.sha,
                branch=branch
            )
        except GithubException as ge:
            if ge.status == 404:
                # File does not exist yet; create it
                repo.create_file(
                    path=github_file_path,
                    message=commit_message,
                    content=csv_content,
                    branch=branch
                )
            else:
                raise ge

        return True
    except Exception as e:
        st.error(f"GitHub Sync Error ({filename}): {e}")
        return False