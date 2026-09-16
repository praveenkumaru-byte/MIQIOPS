# views/admin_settings.py

import streamlit as st
import pandas as pd
from utils.utils import load_csv

def render(access_code: str = "R") -> None:
    """
    Admin & Settings > System Settings
    
    Tabs:
    1. My Profile (Updated to System Admin defaults)
    2. Security (Unchanged)
    3. User Management (Dynamic from supermaster.csv)
    4. Integrations (Unchanged)
    """
    st.markdown("### ⚙️ Admin & Settings")

    # --- TABS ---
    t1, t2, t3, t4 = st.tabs(["My Profile", "Security", "User Management", "Integrations"])

    # ==========================================================================
    # TAB 1: MY PROFILE (Updated for System Admin)
    # ==========================================================================
    with t1:
        st.subheader("User Profile")
        
        c1, c2 = st.columns([1, 3])
        
        with c1:
            # Placeholder for profile image
            st.markdown(
                """
                <div style="
                    width: 150px; height: 150px; 
                    background-color: #e2e8f0; 
                    border-radius: 50%; 
                    display: flex; align-items: center; justify-content: center;
                    font-size: 3rem; color: #64748b; font-weight: bold;">
                    SA
                </div>
                """, 
                unsafe_allow_html=True
            )
            st.caption("Profile Picture")
            
        with c2:
            # Updated Defaults for System Admin
            with st.form("profile_form"):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.text_input("First Name", value="System", disabled=(access_code=="R"))
                    st.text_input("Email", value="systemadmin@maverickiq.com", disabled=(access_code=="R"))
                with c_b:
                    st.text_input("Last Name", value="Admin", disabled=(access_code=="R"))
                    st.text_input("Role", value="System Admin", disabled=True)  # Fixed Role
                
                st.text_area("Bio / Responsibilities", value="System Administrator for Maverick IQ IOPS. Managing user access, integrations, and platform configuration.", disabled=(access_code=="R"))
                
                if access_code == "RW":
                    st.form_submit_button("Save Profile Changes")
                else:
                    st.warning("Read-only mode: Cannot edit profile.")

    # ==========================================================================
    # TAB 2: SECURITY (Unchanged)
    # ==========================================================================
    with t2:
        st.subheader("Security Settings")
        
        st.markdown("#### Password Management")
        with st.form("pwd_form"):
            p1, p2 = st.columns(2)
            p1.text_input("Current Password", type="password")
            p2.text_input("New Password", type="password")
            st.text_input("Confirm New Password", type="password")
            
            if access_code == "RW":
                st.form_submit_button("Update Password")
            else:
                st.info("Password updates disabled in read-only mode.")

        st.divider()
        st.markdown("#### Session & MFA")
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.toggle("Enable Two-Factor Authentication (2FA)", value=True, disabled=(access_code=="R"))
            st.toggle("Force Logout on Browser Close", value=False, disabled=(access_code=="R"))
        with col_s2:
            st.selectbox("Session Timeout", ["15 minutes", "30 minutes", "1 Hour", "4 Hours"], index=1, disabled=(access_code=="R"))

    # ==========================================================================
    # TAB 3: USER MANAGEMENT (Dynamic from Supermaster)
    # ==========================================================================
    with t3:
        st.subheader("User Management")
        
        # 1. Action Bar
        col_act, col_search = st.columns([1, 2])
        with col_act:
            if access_code == "RW":
                with st.expander("➕ Invite New User"):
                    with st.form("new_user"):
                        st.text_input("Email Address")
                        st.selectbox("Role", ["Planner", "Scheduler", "Manager", "Admin", "Viewer"])
                        st.form_submit_button("Send Invite")
        with col_search:
            search_q = st.text_input("Search users...", placeholder="Name, Email or Role")

        # 2. Build User List Dynamically
        users_data = []

        # A. Add System Admin (Super Admin)
        users_data.append({
            "Name": "System Admin",
            "Email": "systemadmin@maverickiq.com",
            "Role": "Admin",
            "Status": "Active",
            "Last Login": "Just now"
        })

        # B. Fetch Project Managers from Supermaster CSV
        try:
            df_projects = load_csv("supermaster_project_list.csv")
            if not df_projects.empty and "Project Manager" in df_projects.columns:
                # Get unique names, drop NaNs, sort alphabetically
                unique_pms = sorted(df_projects["Project Manager"].dropna().unique().tolist())
                
                for i, pm_name in enumerate(unique_pms):
                    # Generate a mock email based on name
                    safe_name = pm_name.lower().replace(" ", ".")
                    mock_email = f"{safe_name}@maverickiq.com"
                    
                    # Alternate status for realism
                    status = "Active" if i % 5 != 0 else "Away"
                    
                    users_data.append({
                        "Name": pm_name,
                        "Email": mock_email,
                        "Role": "Plant Manager", # Requested Role
                        "Status": status,
                        "Last Login": "Today" if status == "Active" else "3 days ago"
                    })
        except Exception:
            # Fallback if CSV fails
            st.warning("Could not load Project Managers from file. Showing default admin only.")

        df_users = pd.DataFrame(users_data)

        # 3. Filter (Search)
        if search_q:
            df_users = df_users[
                df_users["Name"].str.contains(search_q, case=False) | 
                df_users["Email"].str.contains(search_q, case=False) |
                df_users["Role"].str.contains(search_q, case=False)
            ]

        # 4. Display Table
        st.dataframe(
            df_users,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Status": st.column_config.SelectboxColumn(
                    "Status",
                    options=["Active", "Inactive", "Away"],
                    required=True,
                    disabled=(access_code=="R")
                ),
                "Role": st.column_config.SelectboxColumn(
                    "Role",
                    options=["Admin", "Plant Manager", "Planner", "Scheduler", "Viewer"],
                    required=True,
                    disabled=(access_code=="R")
                )
            }
        )

    # ==========================================================================
    # TAB 4: INTEGRATIONS (Unchanged)
    # ==========================================================================
    with t4:
        st.subheader("Integrations & API Connections")
        
        st.info("Manage connections to external Enterprise Systems.")
        
        c_i1, c_i2 = st.columns(2)
        
        with c_i1:
            with st.container(border=True):
                st.markdown("### Oracle Primavera P6")
                st.write("Status: 🟢 **Connected**")
                st.write("Last Sync: 10 mins ago")
                st.toggle("Enable Auto-Sync", value=True, key="p6_sync", disabled=(access_code=="R"))
                if access_code == "RW":
                    st.button("Test Connection", key="p6_test")
        
        with c_i2:
            with st.container(border=True):
                st.markdown("### SAP ERP (S/4HANA)")
                st.write("Status: 🔴 **Disconnected**")
                st.write("Last Sync: 24 hours ago")
                st.toggle("Enable Auto-Sync", value=False, key="sap_sync", disabled=(access_code=="R"))
                if access_code == "RW":
                    st.button("Reconnect", key="sap_rec")

        with st.container(border=True):
            st.markdown("### Maximo EAM")
            c_m1, c_m2 = st.columns([3, 1])
            with c_m1:
                st.text_input("API Endpoint", value="https://maximo.maverickiq.internal/api/v2", disabled=(access_code=="R"))
                st.text_input("API Key", value="********************************", type="password", disabled=(access_code=="R"))
            with c_m2:
                st.write("")
                st.write("")
                if access_code == "RW":
                    st.button("Save Config", use_container_width=True)