# views/timesheets.py

import time
from datetime import datetime

import pandas as pd
import streamlit as st

from utils.utils import load_csv  # aligned with fleet_dashboard/master_schedule


def render(access_code: str = "R") -> None:
    """
    Execution & Labor > Timesheets & Labor

    access_code:
        "R"  -> read-only (can view but not change data)
        "RW" -> can simulate writes (manual entry, bulk import, sync)
        other -> view only with an access warning
    """

    # ---------- ACCESS BANNER ----------
    st.markdown("### Timesheets & Labor")

    if access_code not in ("R", "RW"):
        st.warning("Access level does not allow changes on this view (Timesheets & Labor).")
    elif access_code == "R":
        st.info("Access level: Read-only – timesheet entries are locked.")
    else:
        st.success("Access level: Read / Write – timesheet interactions are enabled.")

    # ---------- STEP 1: INITIALIZE SESSION STATE ----------
    if "timesheet_db" not in st.session_state:
        # Load correct files based on your new data structure
        df_fleet = load_csv("fleet_status.csv")              
        df_projects = load_csv("supermaster_project_list.csv")  # UPDATED from master_project_list_p6demo
        df_rates = load_csv("contractor_rates.csv")             # UPDATED from labor_rates.csv

        initial_data = {
            "EMP_ID": ["TMS-101", "TMS-102", "HVC-301"],
            "Project_ID": ["PRJ-NS-001", "PRJ-NS-001", "PRJ-NS-002"],
            "Hours": [40, 40, 32],
            "Cost": [2000, 2000, 2400],
        }

        st.session_state["timesheet_db"] = pd.DataFrame(initial_data)
        st.session_state["df_fleet"] = df_fleet
        st.session_state["df_projects"] = df_projects
        st.session_state["df_rates"] = df_rates

    # Access data from session state
    df_ts = st.session_state["timesheet_db"]
    df_projects = st.session_state["df_projects"]
    df_rates = st.session_state["df_rates"]
    df_fleet = st.session_state["df_fleet"]

    # ---------- STEP 2: TOP METRIC STRIP ----------
    st.markdown("#### Project labor impact")

    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    total_hours = df_ts["Hours"].sum()
    total_cost = df_ts["Cost"].sum()
    unique_workers = df_ts["EMP_ID"].nunique()
    project_count = df_ts["Project_ID"].nunique()

    with col_m1:
        st.metric("Total man-hours logged", f"{total_hours:,.0f} hrs")

    with col_m2:
        st.metric("Total labor spend", f"${total_cost:,.0f}")

    with col_m3:
        st.metric("Active contractors", f"{unique_workers}", f"Across {project_count} projects")

    with col_m4:
        if total_hours > 200:
            st.success("Data is synchronized with ERP.")
        else:
            st.warning("ERP synchronization pending.")

    st.divider()

    # ---------- STEP 3: TABS ----------
    ts1, ts2, ts3, ts4 = st.tabs(
        [
            "Manual entry",
            "Bulk upload",
            "ERP sync",
            "Cloud drive",
        ]
    )

    # --- TAB 1: MANUAL ENTRY ---
    with ts1:
        st.markdown("#### Supervisor daily log")

        c_sup_1, c_sup_2 = st.columns([1, 2])

        with c_sup_1:
            with st.container(border=True):
                # Site Selection
                site_list = ["All Sites"] + sorted(df_fleet["Site Name"].dropna().unique().tolist())
                selected_site_ts = st.selectbox("Select site context", site_list, index=0)
                st.caption(f"Context: {selected_site_ts}")

                # Contractor Selection (Mapped to 'Firm')
                # Check if 'Firm' exists, else fall back to 'Contractor' or empty list
                firm_col = "Firm" if "Firm" in df_rates.columns else "Contractor"
                firms = df_rates[firm_col].dropna().unique() if firm_col in df_rates.columns else []
                
                sel_firm_manual = st.selectbox("Contracting firm", firms)

                # ID Generation Logic preserved
                if "Turbo" in str(sel_firm_manual):
                    ids = [f"TMS-{i}" for i in range(101, 110)]
                elif "Grid" in str(sel_firm_manual):
                    ids = [f"GFS-{i}" for i in range(201, 210)]
                else:
                    # Generic IDs if match not found
                    ids = [f"HVC-{i}" for i in range(301, 310)]

                sel_cont_id = st.selectbox("Worker ID", ids)

        with c_sup_2:
            with st.container(border=True):
                st.markdown("##### Time entry details")

                with st.form("manual_entry_form"):
                    c_a, c_b = st.columns(2)

                    # Project Selection Logic
                    if selected_site_ts != "All Sites":
                        avail_projs = (
                            df_projects[df_projects["Site Name"] == selected_site_ts]["Project ID"]
                            .dropna()
                            .unique()
                        )
                    else:
                        avail_projs = df_projects["Project ID"].dropna().unique()

                    proj_id = c_a.selectbox("Project charge code", avail_projs)
                    
                    # Role Selection (Filtered by Firm if possible)
                    if firm_col in df_rates.columns and "Role" in df_rates.columns:
                        role_options = df_rates[df_rates[firm_col] == sel_firm_manual]["Role"].dropna().unique()
                    else:
                        role_options = []
                        
                    role_id = c_b.selectbox("Worker role", role_options)

                    date_val = c_a.date_input("Date", value=datetime.today())

                    c_h1, c_h2 = st.columns(2)
                    reg_h = c_h1.number_input("Regular hours", 0.0, 12.0, 8.0, 0.5)
                    ot_h = c_h2.number_input("Overtime hours", 0.0, 12.0, 0.0, 0.5)

                    disabled = access_code != "RW"

                    submitted = st.form_submit_button(
                        "Submit time card",
                        disabled=disabled,
                    )

                    if submitted:
                        total_h = reg_h + ot_h
                        
                        # Lookup Rate from new CSV structure
                        # Expected columns: Firm, Role, Standard Rate ($/hr)
                        try:
                            rate_row = df_rates[
                                (df_rates[firm_col] == sel_firm_manual) & 
                                (df_rates["Role"] == role_id)
                            ]
                            if not rate_row.empty:
                                rate = float(rate_row.iloc[0]["Standard Rate ($/hr)"])
                            else:
                                rate = 55.0 # Fallback
                        except:
                            rate = 55.0 # Fallback on error

                        new_row = {
                            "EMP_ID": sel_cont_id,
                            "Project_ID": proj_id,
                            "Hours": total_h,
                            "Cost": total_h * rate,
                            "Role": role_id,
                            "Date": date_val,
                        }

                        st.session_state["timesheet_db"] = pd.concat(
                            [st.session_state["timesheet_db"], pd.DataFrame([new_row])],
                            ignore_index=True,
                        )

                        st.success(f"Saved: {sel_cont_id} | {proj_id} | {total_h} hrs | Est Cost: ${total_h * rate:.2f}")
                        time.sleep(0.4)
                        st.rerun()

    # --- TAB 2: BULK UPLOAD ---
    with ts2:
        st.markdown("#### Bulk timesheet import")

        with st.container(border=True):
            st.markdown("##### 1. Download template")

            template_data = {
                "EMP_ID": ["TMS-101", "GFS-205"],
                "Project_ID": ["PRJ-NS-001", "PRJ-NS-002"],
                "Date": ["2026-03-01", "2026-03-01"],
                "Reg_Hours": [8, 8],
                "OT_Hours": [2, 0],
            }

            st.download_button(
                label="Download CSV template",
                data=pd.DataFrame(template_data).to_csv(index=False).encode("utf-8"),
                file_name="timesheet_template.csv",
                mime="text/csv",
            )

            st.divider()
            st.markdown("##### 2. Upload completed file(s)")
            
            # CHANGED: Added accept_multiple_files=True
            up_files = st.file_uploader(
                "Drag and drop CSV file(s) here",
                type=["csv"],
                accept_multiple_files=True,
                disabled=access_code != "RW",
            )

            # CHANGED: Logic to handle list of files
            if up_files:
                st.success(f"{len(up_files)} file(s) staged for upload.")
                
                # Combine all uploaded files into one preview dataframe
                combined_upload = []
                for f in up_files:
                    try:
                        df = pd.read_csv(f)
                        combined_upload.append(df)
                    except Exception as e:
                        st.error(f"Error reading {f.name}: {e}")
                
                if combined_upload:
                    preview_df = pd.concat(combined_upload, ignore_index=True)
                    st.dataframe(preview_df.head(10), use_container_width=True)
                    st.caption(f"Previewing first 10 of {len(preview_df)} total records from {len(up_files)} files.")

                    if st.button(
                        f"Process and merge {len(preview_df)} records",
                        disabled=access_code != "RW",
                    ):
                        with st.spinner(f"Validating {len(preview_df)} records against master data..."):
                            time.sleep(1.2)

                        # SIMULATION LOGIC: Creating dummy data to represent the merged rows
                        # In production, you would process 'preview_df' directly.
                        # For simulation, we generate equivalent dummy records to update the DB.
                        new_data = {
                            "EMP_ID": [f"BULK-{i}" for i in range(1, len(preview_df) + 1)],
                            "Project_ID": ["PRJ-NS-001"] * len(preview_df),
                            "Hours": [8] * len(preview_df),
                            "Cost": [450] * len(preview_df),
                        }

                        st.session_state["timesheet_db"] = pd.concat(
                            [st.session_state["timesheet_db"], pd.DataFrame(new_data)],
                            ignore_index=True,
                        )

                        st.success("Database synchronized successfully.")
                        time.sleep(0.8)
                        st.rerun() # Forces top metrics to update immediately

    # --- TAB 3: DB SYNC ---
    with ts3:
        st.markdown("#### Enterprise connector (ERP sync)")

        c_erp1, c_erp2 = st.columns(2)

        with c_erp1:
            with st.container(border=True):
                st.markdown("##### Pending transactions")

                st.metric("Approved records", f"{len(df_ts)}", "Ready for export")
                st.caption("Last successful sync: Today 06:00")

                if st.button(
                    "Push to ERP gateway",
                    disabled=access_code != "RW",
                ):
                    my_bar = st.progress(0, text="Connecting to ERP gateway...")
                    for percent_complete in range(100):
                        time.sleep(0.02)
                        my_bar.progress(percent_complete + 1, text="Connecting to ERP gateway...")
                    st.success(f"Data pushed successfully. Batch ID: #99{len(df_ts)}")

        with c_erp2:
            with st.container(border=True):
                st.markdown("##### Sync logs")

                log_data = pd.DataFrame(
                    {
                        "Batch ID": ["#99237", "#99236", "#99235"],
                        "Timestamp": ["Yesterday 18:00", "Yesterday 12:00", "Yesterday 06:00"],
                        "Status": ["Success", "Success", "Warning"],
                        "Records": [320, 115, 84],
                    }
                )
                st.dataframe(log_data, use_container_width=True, hide_index=True)

    # --- TAB 4: CLOUD DRIVE ---
    with ts4:
        st.markdown("#### Cloud storage import (SharePoint / OneDrive)")

        with st.container(border=True):
            c_tree, c_files = st.columns([1, 2])

            with c_tree:
                st.markdown("Select folder")
                folder_sel = st.radio(
                    "Directory",
                    [
                        "/Shared/Outages_2026/Timesheets",
                        "/Shared/Contractors/TurboMech",
                        "/Shared/Contractors/GridFix",
                    ],
                    index=0,
                )

            with c_files:
                st.markdown(f"Files in {folder_sel}")
                st.markdown("Site_Consolidated_Week12.xlsx (Last modified: 2 minutes ago)")
                st.caption("Contains 150+ records from TurboMech and GridFix crews.")

            st.divider()

            if st.button(
                "Import and process data",
                key="cloud_btn",
                disabled=access_code != "RW",
            ):
                with st.spinner("Connecting to SharePoint API..."):
                    time.sleep(1.0)
                with st.spinner("Parsing schemas and validating rates..."):
                    time.sleep(1.0)

                new_data = {
                    "EMP_ID": [f"TMS-{i}" for i in range(110, 160)],
                    "Project_ID": ["PRJ-NS-001"] * 50,
                    "Hours": [10] * 50,
                    "Cost": [650] * 50,
                }

                st.session_state["timesheet_db"] = pd.concat(
                    [st.session_state["timesheet_db"], pd.DataFrame(new_data)],
                    ignore_index=True,
                )

                st.success("Imported records from SharePoint.")
                time.sleep(1.0)
                st.rerun()