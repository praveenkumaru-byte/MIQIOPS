# views/admin_rbac.py

import streamlit as st
import pandas as pd
import os
from utils.utils import save_csv_to_github  # <-- Add import

# Path to your CSV (Adjust if your folder structure is different)
RBAC_FILE = "data/RBAC.csv"

def render(access_code: str = "R") -> None:
    """
    Admin & Settings > Users & Roles (RBAC)
    
    Features:
    - Matrix Editor for System Permissions
    - Dropdown selection for access levels (RW, R, X)
    - Saves directly to CSV
    """
    st.markdown("### 👥 User Roles & Access Control")
    st.caption("Manage application permissions. Changes apply immediately after saving.")

    # 1. ACCESS CONTROL CHECK
    if access_code != "RW":
        st.error("⛔ Security Alert: You do not have permission to edit System Roles.")
        st.info("Please contact a System Administrator.")
        return

    # 2. LOAD DATA
    if not os.path.exists(RBAC_FILE):
        st.error(f"Configuration file not found: {RBAC_FILE}")
        return

    try:
        df = pd.read_csv(RBAC_FILE)
    except Exception as e:
        st.error(f"Error loading RBAC file: {e}")
        return

    # 3. UX: FILTERING
    # Let users filter by Module to avoid a giant wall of text
    modules = list(df["Module"].unique())
    selected_modules = st.multiselect(
        "Filter by Module", 
        modules, 
        default=modules,
        help="Select specific modules to edit permissions."
    )
    
    if not selected_modules:
        st.warning("Please select at least one module.")
        return

    # Filter the view (we will merge changes back later)
    df_view = df[df["Module"].isin(selected_modules)].copy()

    # 4. PREPARE EDITOR CONFIG
    # We want columns "Module", "Page", "PageID" to be read-only (disabled)
    # We want Role columns to be Selectboxes ["RW", "R", "X"]
    
    # Identify role columns (all cols except the metadata ones)
    meta_cols = ["Module", "Page", "PageID"]
    role_cols = [c for c in df.columns if c not in meta_cols]

    # Build column config
    column_config = {
        "Module": st.column_config.TextColumn(disabled=True),
        "Page": st.column_config.TextColumn(disabled=True, width="medium"),
        "PageID": st.column_config.TextColumn(disabled=True, width="small"),
    }

    # Apply dropdown config to all role columns
    for role in role_cols:
        column_config[role] = st.column_config.SelectboxColumn(
            label=role,
            options=["RW", "R", "X"],
            help=f"Permissions for {role}",
            required=True,
            width="small"
        )

    # 5. RENDER EDITOR
    st.divider()
    
    edited_df = st.data_editor(
        df_view,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        key="rbac_editor"
    )

    # 6. SAVE LOGIC
    # We need to detect changes and merge them back into the main DataFrame
    # (Because we might be viewing a filtered subset)
    
    col_save, col_cancel = st.columns([1, 5])
    
    with col_save:
        if st.button("💾 Save Changes", type="primary"):
            try:
                # Update the main DF with the edited rows using PageID as the key
                # Set index to PageID for easy update
                df.set_index("PageID", inplace=True)
                edited_df.set_index("PageID", inplace=True)
                
                # Update rows in main DF with values from edited DF
                df.update(edited_df)
                
                # Reset index and save
                df.reset_index(inplace=True)
                success = save_csv_to_github("RBAC.csv", df, "Update RBAC permissions from Admin UI")
                if success:
                    st.success("✅ Permissions updated and synced to GitHub!")
                    st.cache_data.clear()
                
            except Exception as e:
                st.error(f"Failed to save changes: {e}")


    # 7. LEGEND
    with st.expander("ℹ️ Permission Legend"):
        st.markdown("""
        * **RW (Read/Write)**: Full access. User can view data and perform actions (Edit, Delete, Approve).
        * **R (Read Only)**: View access only. Actions and inputs are disabled.
        * **X (No Access)**: Page is hidden from the sidebar menu entirely.
        """)