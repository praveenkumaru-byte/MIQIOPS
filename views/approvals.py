# views/approvals.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

def render(access_code: str = "R") -> None:
    """
    Budget & Tracking > Approvals & Notification Center
    
    Features:
    - Real-time interaction: Approved items vanish and move to History.
    - Session State: Persists changes during the user session.
    """
    st.markdown("### Approvals & Notification Center")

    # --- 1. SESSION STATE INITIALIZATION (The "Real-time" Magic) ---
    if "approval_queue" not in st.session_state:
        # Load mock data only once
        st.session_state.approval_queue = [
            {
                "id": "REQ-101", 
                "type": "Financial", 
                "item": "Turbine Blade Replacement Set", 
                "requester": "Sarah Connor", 
                "value": "$55,000", 
                "threshold_flag": True, 
                "submitted_date": datetime.now() - timedelta(days=6), 
                "status": "Pending Level 2 Signoff"
            },
            {
                "id": "REQ-102", 
                "type": "Schedule", 
                "item": "Generator 4 Overhaul", 
                "requester": "Kyle Reese", 
                "value": "N/A", 
                "threshold_flag": False, 
                "submitted_date": datetime.now() - timedelta(days=2), 
                "status": "Pending PM Review"
            },
            {
                "id": "REQ-103", 
                "type": "Special", 
                "item": "MagParticle Inspection", 
                "requester": "T-800", 
                "value": "$2,000", 
                "threshold_flag": True, 
                "submitted_date": datetime.now() - timedelta(days=1), 
                "status": "Pending Safety Officer"
            }
        ]

    if "approval_history" not in st.session_state:
        st.session_state.approval_history = [
            {"id": "REQ-099", "date": "2026-03-10", "item": "Site Access: Contractor Crew", "action": "Approved", "user": "Harvey Specter"},
            {"id": "REQ-098", "date": "2026-03-09", "item": "Budget Increase: Unit 2", "action": "Denied", "user": "Louis Litt", "comment": "Insufficient justification provided."}
        ]

    # --- 2. KPI CALCULATIONS ---
    queue = st.session_state.approval_queue
    history = st.session_state.approval_history
    
    stale_count = sum(1 for x in queue if (datetime.now() - x['submitted_date']).days > 5)
    
    # --- 3. KPI DISPLAY ---
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="miq-kpi-card">
            <div class="miq-kpi-label">Pending My Action</div>
            <div class="miq-kpi-value">{len(queue)}</div>
            <div class="miq-kpi-sub">Requests waiting for you</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        # Dynamic color based on urgency
        card_class = "kpi-red" if stale_count > 0 else "kpi-amber"
        st.markdown(f"""
        <div class="miq-kpi-card {card_class}">
            <div class="miq-kpi-label">Urgent (>5 Days)</div>
            <div class="miq-kpi-value">{stale_count}</div>
            <div class="miq-kpi-sub">{stale_count} Item(s) need attention</div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="miq-kpi-card kpi-green">
            <div class="miq-kpi-label">Processed (Session)</div>
            <div class="miq-kpi-value">{len(history)}</div>
            <div class="miq-kpi-sub">Total decisions logged</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # --- 4. TABS ---
    tab1, tab2, tab3 = st.tabs(["Action Required", "Watchlist (Sent)", "Approval History"])

    # TAB 1: INBOX (Interactive)
    with tab1:
        st.markdown("#### Items Awaiting Your Signoff")
        
        if not queue:
            st.success("🎉 You're all caught up! No pending approvals.")
        else:
            # Iterate through a copy so we can modify the original list safely
            for i, req in enumerate(queue):
                days_pending = (datetime.now() - req['submitted_date']).days
                
                with st.container(border=True):
                    # Icons
                    icon = "💲" if req['type'] == "Financial" else "⏱️" if req['type'] == "Schedule" else "👷"
                    
                    c1, c2, c3, c4 = st.columns([1, 4, 3, 2])
                    
                    with c1:
                        st.markdown(f"## {icon}")
                        if days_pending > 5:
                            st.error(f"**{days_pending}d**")
                        else:
                            st.info(f"{days_pending}d")

                    with c2:
                        st.markdown(f"**{req['item']}**")
                        st.caption(f"{req['type']} | Requester: {req['requester']} | ID: {req['id']}")
                        if req.get('threshold_flag'):
                            st.warning("⚠️ High Value / High Risk")

                    with c3:
                        st.markdown(f"**Value:** {req['value']}")
                        st.markdown(f"**Status:** {req['status']}")

                    with c4:
                        # ACTION BUTTONS
                        b1, b2 = st.columns(2)
                        
                        # APPROVE
                        if b1.button("✅", key=f"app_{req['id']}", help="Approve", disabled=access_code!="RW"):
                            # 1. Add to history
                            st.session_state.approval_history.insert(0, {
                                "id": req["id"],
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "item": req["item"],
                                "action": "Approved",
                                "user": req["requester"]
                            })
                            # 2. Remove from queue
                            st.session_state.approval_queue.pop(i)
                            # 3. Toast & Rerun
                            st.toast(f"Approved {req['id']}")
                            st.rerun()
                        
                        # DENY
                        if b2.button("❌", key=f"deny_{req['id']}", help="Deny", disabled=access_code!="RW"):
                            # 1. Add to history
                            st.session_state.approval_history.insert(0, {
                                "id": req["id"],
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "item": req["item"],
                                "action": "Denied",
                                "user": req["requester"]
                            })
                            # 2. Remove from queue
                            st.session_state.approval_queue.pop(i)
                            # 3. Toast & Rerun
                            st.toast(f"Denied {req['id']}")
                            st.rerun()

    # TAB 2: WATCHLIST (Static for now)
    with tab2:
        st.markdown("#### Requests You Sent (Waiting on Others)")
        watchlist = [
            {"id": "PO-992", "type": "Purchase Order", "item": "Emergency Valve Kit", "approver": "Mike Ross (CFO)", "days_open": 8, "status": "Stuck at Finance"},
            {"id": "TS-441", "type": "Timesheet", "item": "Week 12 Crew A", "approver": "Donna Paulsen (HR)", "days_open": 1, "status": "Pending Review"}
        ]
        
        for w in watchlist:
            with st.container(border=True):
                wc1, wc2, wc3, wc4 = st.columns([1, 4, 3, 2])
                with wc1:
                    st.markdown("🔴" if w['days_open'] > 5 else "🟡")
                with wc2:
                    st.markdown(f"**{w['item']}** ({w['id']})")
                    st.caption(f"Type: {w['type']}")
                with wc3:
                    st.markdown(f"**Pending With:** {w['approver']}")
                    st.markdown(f"**Age:** {w['days_open']} Days")
                with wc4:
                    if st.button("🔔 Remind", key=f"remind_{w['id']}", disabled=access_code!="RW"):
                        st.toast(f"Reminder email sent to {w['approver']}!")

    # TAB 3: HISTORY
    with tab3:
        st.markdown("#### Archive of Past Decisions")
        
        df_hist = pd.DataFrame(st.session_state.approval_history)
        
        if not df_hist.empty:
            st.dataframe(
                df_hist,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "date": "Date Decided",
                    "item": "Description",
                    "action": "Decision",
                    "user": "Requester"
                }
            )
        else:
            st.info("No history found.")