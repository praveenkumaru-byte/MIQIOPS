import streamlit as st
import streamlit_antd_components as sac
import pandas as pd

# ==============================================================================
# 1. IMPORTS & SETUP
# ==============================================================================
from utils.utils import (
    load_rbac,
    get_persona_columns,
    get_persona_access_map,
    get_access_label,
    load_logo,
    inject_global_css,
)

# --- IMPORT VIEWS ---
from views import (
    fleet_dashboard,
    site_overview,    
    master_schedule,
    p6_creation,
    outage_calendar,    
    timesheets,         
    budget,
    approvals,
    cbm_dashboard,
    inventory,             
    ehs_dashboard,
    admin_rbac,      
    admin_settings,     
)

st.set_page_config(
    page_title="Maverick IQ – Outage Planning & Scheduling",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject Global CSS (Slate Background, etc.)
inject_global_css()

# --- CSS OVERRIDES (Icons & Sizes) ---
st.markdown(
    """
    <style>
    /* 1. TINY BULLET for Read-Write (RW) */
    i.bi-circle-fill {
        font-size: 6px !important;
        margin-top: 3px !important;
        color: #334155; /* Dark Slate */
    }

    /* 2. LOCK ICON for Read-Only (R) */
    i.bi-lock-fill {
        font-size: 13px !important;
        color: #475569 !important; /* Slate Grey - Visible but distinct */
    }
    
    /* 3. SLASH ICON for No Access (X) */
    i.bi-slash-circle {
        font-size: 13px !important;
        color: #94a3b8 !important;  /* Lighter Grey to indicate disabled */
    }
    
    /* --- NEW FIXES BELOW --- */

    /* 4. HIDE SIDEBAR COLLAPSE BUTTON (<<) */
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* 5. FORCE EXPAND BUTTON VISIBILITY (Fallback) */
    [data-testid="collapsedControl"] {
        display: flex !important;
        opacity: 1 !important;
        visibility: visible !important;
        z-index: 999999 !important;
    }

    /* 6. HIDE HEADER ANCHOR LINKS GLOBALLY */
    [data-testid="stHeaderActionElements"], 
    a.header-anchor {
        display: none !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# 2. DATA LOADING & SESSION STATE
# ==============================================================================
rbac_df = load_rbac()
personas = get_persona_columns(rbac_df)

DEFAULT_USER_NAME = "admin"
DEFAULT_PERSONA = "System Admin" if "System Admin" in personas else (personas[0] if personas else "")

if "persona" not in st.session_state:
    st.session_state.persona = DEFAULT_PERSONA
if "user_name" not in st.session_state:
    st.session_state.user_name = DEFAULT_USER_NAME

# --- MAP FOR ROUTING (Label -> ID) ---
PAGE_MAP = dict(zip(rbac_df["Page"], rbac_df["PageID"]))

# ==============================================================================
# 3. SIDEBAR NAVIGATION
# ==============================================================================
def build_sac_menu(df, current_persona):
    """
    Builds the menu dynamically:
    - RW (Write): Tiny Bullet (circle-fill)
    - R  (Read) : Lock Icon (lock-fill) -> Clickable (View Only)
    - X  (No)   : Slash Icon (slash-circle) -> Disabled
    """
    menu_structure = []
    
    # Get access map: {'fleet_dashboard': 'RW', 'site_overview': 'R', ...}
    access_map = get_persona_access_map(df, current_persona)

    module_icons = {
        "Fleet & CXO": "speedometer2",
        "Planning & Portfolio": "kanban",
        "Scheduling (P6 / IAM)": "calendar-week",
        "Strategy & Planning": "compass",
        "Work Management": "tools",
        "Financials": "currency-dollar",
        "Supply Chain": "box-seam",
        "Quality & Compliance": "clipboard-check",
        "EHS": "shield-check",
        "Admin & Settings": "sliders",
    }

    modules = df["Module"].unique().tolist()

    for mod in modules:
        df_mod = df[df["Module"] == mod]
        children = []
        
        # --- FIX MODULE ACRONYMS ---
        module_label = str(mod)
        module_fixes = {
            "Fleet & Cxo": "Fleet & CXO",
            "Ehs": "EHS",
            "Cbm": "CBM",
            # add any other exact module strings you need to protect
        }
        module_label = module_fixes.get(module_label, module_label)



        for _, row in df_mod.iterrows():
            page_id = row["PageID"]
            page_label = row["Page"]
            
            # --- CHECK ACCESS ---
            access_code = access_map.get(page_id, "X")
            is_restricted = (access_code == "X") or (pd.isna(access_code))
            is_readonly = (access_code == "R")
            
            # --- ICON & STATE LOGIC ---
            if is_restricted:
                item_icon = "slash-circle"   # No Access
                description = "No Access"
                is_disabled = True
            elif is_readonly:
                item_icon = "lock-fill"      # Read Only (Locked for editing)
                description = "View Only"
                is_disabled = False          # Still clickable!
            else:
                item_icon = "circle-fill"    # Full Access
                description = None
                is_disabled = False

            children.append(sac.MenuItem(
                label=page_label,
                icon=item_icon,
                disabled=is_disabled, 
                description=description 
            ))
        
        icon_name = module_icons.get(mod, "folder") 
        menu_structure.append(sac.MenuItem(
            label=module_label,
            icon=icon_name,
            children=children
        ))
        
    return menu_structure

with st.sidebar:
    logo_path = load_logo()
    st.image(logo_path, width=180)
    st.markdown("---")

    # RENDER MENU
    selected_label = sac.menu(
        items=build_sac_menu(rbac_df, st.session_state.persona),
        index=0,
    #    format_func='title',
        size='sm',      
        indent=20,      
        open_all=True,  
        color='blue',   
    )
    
    if selected_label in PAGE_MAP:
        st.session_state.selected_page_id = PAGE_MAP[selected_label]

current_page_id = st.session_state.get("selected_page_id", rbac_df.iloc[0]["PageID"])

# ==============================================================================
# ==============================================================================
# 4. TOP HEADER (3-CARD SYSTEM)
# ==============================================================================
col_about, col_persona, col_role_select = st.columns([3, 2.7, 2])

persona_access = get_persona_access_map(rbac_df, st.session_state.persona)
current_access_code = persona_access.get(current_page_id, "X")
current_access_label = get_access_label(current_access_code)

# --- Card 1: Dashboard Info ---
with col_about:
    with st.container(border=True): # <--- NATIVE CONTAINER (Keeps content inside)
        st.markdown('<div class="miq-card-title">Dashboard – Executive Overview</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="miq-card-body">
                <div style="font-weight:700; font-size:1.1rem; margin-bottom:0.25rem;">IOPS Dashboard</div>
                <div style="color:#4b5563;">Enterprise Integrated Outage Planning System </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# --- Card 2: User Persona Info (Large Icon) ---
# --- Card 2: User Persona Info ---
with col_persona:
    with st.container(border=True):
        # 1. Prepare clean strings
        raw_name = st.session_state.user_name if st.session_state.user_name else "User"
        raw_role = st.session_state.persona
        raw_initial = raw_name[0].upper()
        
        # 2. Create the HTML string separately
        # We use simple string concatenation or basic f-string here
        html_content = f"""
        <div style="display: flex; align-items: center; height: 100%; gap: 1.5rem;">
            <div style="
                width: 85px; height: 85px; min-width: 85px;
                border-radius: 50%; border: 3px solid #1e3a8a;
                display: flex; align-items: center; justify-content: center;
                font-size: 2.8rem; font-weight: 800;
                color: #1e3a8a; background-color: #ffffff;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
                {raw_initial}
            </div>
            <div style="display: flex; flex-direction: column; justify-content: center;">
                <div style="font-size: 1.2rem; font-weight: 800; color: #1e3a8a; line-height: 1.2;">
                    {raw_name}
                </div>
                <div style="font-size: 0.9rem; color: #334155; margin-top: 4px;">
                    <strong>Role:</strong> {raw_role}
                </div>
                <div style="font-size: 0.9rem; color: #334155;">
                    <strong>Access:</strong> {current_access_label}
                </div>
            </div>
        </div>
        """
        
        # 3. Render with explicit unsafe_allow_html
        st.markdown(html_content, unsafe_allow_html=True)

# --- Card 3: Role Selector (Now Inside the Box) ---
with col_role_select:
    with st.container(border=True):
        st.markdown('<div class="miq-card-title">Select a role</div>', unsafe_allow_html=True)
        
        # MOCK NAMES Logic
        MOCK_USER_NAMES = {
            "System Admin": "Admin",
            "Plant Manager": "Plant Manager",
            "Outage Manager": "Outage Lead",
            "Planner": "Planner",
            "Scheduler": "Scheduler",
            "Execution Lead": "Execution Lead",
            "CFO": "Chief Financial Officer",
            "EH&S": "Safety Officer",
            "Timekeeper": "Timekeeper",
            "CBM Engineer": "CBM Eng",
            "Chief Engineer": "Chief Eng"
        }

        previous_persona = st.session_state.persona
        
        # The Dropdown (Now visually inside because of st.container)
        selected_persona = st.selectbox(
            label="Persona", # Hidden by CSS
            options=personas,
            index=personas.index(st.session_state.persona) if st.session_state.persona in personas else 0,
            label_visibility="collapsed",
        )
        
        if selected_persona != previous_persona:
            st.session_state.persona = selected_persona
            st.session_state.user_name = MOCK_USER_NAMES.get(selected_persona, selected_persona)
            st.rerun()

# ==============================================================================
# 5. ROUTING
# ==============================================================================
def render_restricted(page_id: str, access_label: str) -> None:
    st.error(f"⛔ **Access Denied**\n\nThis page is **{access_label}** for the **{st.session_state.persona}** persona.")

def route_to_view(page_id: str, access_code: str) -> None:
    # 1. Security Check
    if access_code == "X" or pd.isna(access_code):
        render_restricted(page_id, "Restricted")
        return

    # 2. View Dispatcher
    if page_id == "fleet_dashboard": fleet_dashboard.render(access_code); return
    if page_id == "site_overview": site_overview.render(access_code); return
    if page_id == "master_schedule": master_schedule.render(access_code); return
    if page_id == "p6_creation": p6_creation.render(access_code); return    
    if page_id == "outage_calendar": outage_calendar.render(access_code); return
    if page_id == "timesheets": timesheets.render(access_code); return
    if page_id == "budget": budget.render(access_code); return
    if page_id == "approvals": approvals.render(access_code); return
    if page_id == "cbm_dashboard": cbm_dashboard.render(access_code); return
    if page_id == "inventory": inventory.render(access_code); return
    if page_id == "ehs_dashboard": ehs_dashboard.render(access_code); return
    if page_id == "admin_rbac": admin_rbac.render(access_code); return
    if page_id == "admin_settings": admin_settings.render(access_code); return
    
    # 3. Fallback
    st.subheader(f"🚧 Page: {page_id.replace('_', ' ').title()}")
    st.caption(f"Access Level: {get_access_label(access_code)}")
    st.info("Access Denied: Do not have permission to view this page.")

route_to_view(current_page_id, current_access_code)