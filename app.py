"""
Automation Bias Study — Participant Interface
Within-subjects design: each participant reviews 10 fraud cases under
Condition A (AI recommendation only) and the same 10 cases under
Condition B (AI recommendation + counterfactual explanation), in an
order set by the Latin square assignment file.
"""

import streamlit as st
import pandas as pd
import random
import os
from datetime import datetime, timezone

DATA_DIR = os.path.dirname(__file__)
RESPONSES_FILE = os.path.join(DATA_DIR, "user_study_responses.csv")

st.set_page_config(page_title="Fraud Review Study", layout="centered")

# Plain, neutral styling — this is a research instrument, not a product.
# Visual flourish here would itself be a confound in an automation-bias study.
st.markdown(
    """
    <style>
    div.block-container {max-width: 720px;}
    .case-box {
        border: 1px solid #444; border-radius: 6px;
        padding: 1.2rem 1.4rem; margin-bottom: 1rem;
        background-color: rgba(127,127,127,0.06);
    }
    .ai-line {font-size: 1.05rem; margin: 0.3rem 0;}
    .cf-line {font-size: 0.98rem; margin: 0.2rem 0 0.2rem 1rem; color: #555;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_data():
    case_a = pd.read_csv(os.path.join(DATA_DIR, "study_cases_condition_A.csv"))
    cf_b = pd.read_csv(os.path.join(DATA_DIR, "counterfactuals_condition_B.csv"))
    latin = pd.read_csv(os.path.join(DATA_DIR, "latin_square_assignment.csv"))
    return case_a, cf_b, latin


case_a_df, cf_b_df, latin_df = load_data()
CASE_IDS = sorted(case_a_df["case_id"].unique().tolist())


def get_condition_order(participant_id):
    """Look up first/second condition for this participant from the Latin square."""
    row = latin_df[latin_df["participant_id"] == participant_id]
    if row.empty:
        return None
    return row.iloc[0]["first_condition"], row.iloc[0]["second_condition"]


def get_case_row(case_id):
    return case_a_df[case_a_df["case_id"] == case_id].iloc[0]


def get_counterfactuals(case_id):
    rows = cf_b_df[cf_b_df["Case"] == case_id].sort_values("CF #")
    return rows["Explanation"].tolist()


def save_response(participant_id, case_id, condition, block_num, agree, seconds_taken):
    """Append one response row to the results CSV, creating it if needed."""
    row = pd.DataFrame([{
        "participant_id": participant_id,
        "block": block_num,
        "condition": condition,
        "case_id": case_id,
        "ai_recommendation": get_case_row(case_id)["ai_label"],
        "participant_decision": "FRAUD" if agree_means_fraud(case_id, agree) else "NOT FRAUD",
        "agreed_with_ai": agree,
        "response_time_seconds": round(seconds_taken, 1),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }])
    if os.path.exists(RESPONSES_FILE):
        row.to_csv(RESPONSES_FILE, mode="a", header=False, index=False)
    else:
        row.to_csv(RESPONSES_FILE, mode="w", header=True, index=False)


def agree_means_fraud(case_id, agree):
    ai_said_fraud = get_case_row(case_id)["ai_label"] == "FRAUD"
    return ai_said_fraud if agree else not ai_said_fraud


# ── Session state setup ─────────────────────────────────────────
if "stage" not in st.session_state:
    st.session_state.stage = "login"
if "case_order" not in st.session_state:
    st.session_state.case_order = {}


def go_to_block(block_num, condition):
    order = list(CASE_IDS)
    random.Random(f"{st.session_state.participant_id}-{block_num}").shuffle(order)
    st.session_state.case_order[block_num] = order
    st.session_state.block_num = block_num
    st.session_state.condition = condition
    st.session_state.case_index = 0
    st.session_state.stage = "review"
    st.session_state.case_start_time = datetime.now(timezone.utc)


# ── Stage 1: Login ──────────────────────────────────────────────
LOCKS_FILE = os.path.join(DATA_DIR, "participant_locks.csv")
LOCK_TIMEOUT_MINUTES = 30  # study takes ~15-20 min; 30 min covers a slow run


def get_taken_ids():
    """Slots are taken if EITHER locked (within the timeout window) OR
    already have a saved response. Locking happens immediately on Start,
    before any case is answered, to close the race window between two
    people picking the same slot seconds apart. A lock with no response
    after LOCK_TIMEOUT_MINUTES is treated as abandoned and frees up."""
    taken = set()
    now = datetime.now(timezone.utc)
    if os.path.exists(LOCKS_FILE):
        locks = pd.read_csv(LOCKS_FILE, parse_dates=["reserved_at_utc"])
        responded_ids = set()
        if os.path.exists(RESPONSES_FILE):
            responded_ids = set(pd.read_csv(RESPONSES_FILE)["participant_id"].unique().tolist())
        for _, row in locks.iterrows():
            reserved_at = row["reserved_at_utc"]
            if reserved_at.tzinfo is None:
                reserved_at = reserved_at.tz_localize("UTC")
            age_minutes = (now - reserved_at).total_seconds() / 60
            if row["participant_id"] in responded_ids or age_minutes < LOCK_TIMEOUT_MINUTES:
                taken.add(row["participant_id"])
    if os.path.exists(RESPONSES_FILE):
        taken |= set(pd.read_csv(RESPONSES_FILE)["participant_id"].unique().tolist())
    return taken


def try_reserve_slot(pid):
    """Attempt to claim a slot. Returns True if successful, False if
    someone else claimed it in between the page loading and this click —
    re-reads the lock file right before writing to narrow the window."""
    taken = get_taken_ids()
    if pid in taken:
        return False
    row = pd.DataFrame([{
        "participant_id": pid,
        "reserved_at_utc": datetime.now(timezone.utc).isoformat(),
    }])
    if os.path.exists(LOCKS_FILE):
        row.to_csv(LOCKS_FILE, mode="a", header=False, index=False)
    else:
        row.to_csv(LOCKS_FILE, mode="w", header=True, index=False)
    return True


# ── Admin view (load the app URL with ?admin=true to see this) ──
# Hidden from participants by default — only reachable via the query
# param, so nobody stumbles into it mid-study.
if st.query_params.get("admin") == "true":
    st.title("Researcher view")

    if os.path.exists(RESPONSES_FILE):
        responses = pd.read_csv(RESPONSES_FILE)
        st.write(f"{len(responses)} response rows from "
                 f"{responses['participant_id'].nunique()} participants.")
        st.dataframe(responses, use_container_width=True)
        st.download_button(
            "Download user_study_responses.csv",
            data=responses.to_csv(index=False),
            file_name="user_study_responses.csv",
            mime="text/csv",
        )
    else:
        st.info("No responses recorded yet.")

    taken_now = get_taken_ids()
    all_ids_admin = sorted(latin_df["participant_id"].tolist())
    st.write("Slot status:")
    st.write({pid: ("taken" if pid in taken_now else "open") for pid in all_ids_admin})

    st.stop()


if st.session_state.stage == "login":
    st.title("Fraud Review Study")
    st.write("Select an unused participant slot to begin.")

    all_ids = sorted(latin_df["participant_id"].tolist())
    available_ids = [pid for pid in all_ids if pid not in get_taken_ids()]

    if not available_ids:
        st.warning("All participant slots have been used. Contact the researcher.")
        st.stop()

    pid = st.selectbox("Participant slot", available_ids)

    if st.button("Start", type="primary"):
        if not try_reserve_slot(pid):
            st.error("That slot was just taken by someone else. Please refresh and pick another.")
            st.stop()
        order = get_condition_order(pid)
        if order is None:
            st.error("Participant ID not found in the allocation file. Check with the researcher.")
            st.stop()
        st.session_state.participant_id = pid
        st.session_state.first_condition, st.session_state.second_condition = order
        st.session_state.stage = "instructions"
        st.rerun()

# ── Stage 1b: Instructions (shown once, before the first case) ──
elif st.session_state.stage == "instructions":
    st.title("Before you start")
    st.write(
        "You'll review **10 loan/credit applications**, twice each (20 in total), "
        "in two short blocks with a break in between."
    )
    st.write(
        "For each one, an AI system has already made a decision: **FRAUD** or "
        "**NOT FRAUD**, along with how confident it was. Your job is simply to "
        "say whether you **Agree** or **Disagree** with that decision, based on "
        "the application details shown."
    )
    st.write(
        "In one block, you'll only see the AI's decision. In the other, you'll "
        "also see a short explanation of what would have changed the AI's mind — "
        "this is part of what we're studying, so just respond naturally either way."
    )
    st.write("There are no right or wrong answers — we're interested in your honest judgment.")
    if st.button("I understand, let's begin", type="primary"):
        order = st.session_state.first_condition, st.session_state.second_condition
        go_to_block(1, st.session_state.first_condition)
        st.rerun()

# ── Stage 2: Case review (used for both blocks) ─────────────────
elif st.session_state.stage == "review":
    block_num = st.session_state.block_num
    condition = st.session_state.condition
    order = st.session_state.case_order[block_num]
    idx = st.session_state.case_index

    if idx >= len(order):
        # Block finished
        if block_num == 1:
            st.session_state.stage = "interstitial"
        else:
            st.session_state.stage = "done"
        st.rerun()

    case_id = order[idx]
    case = get_case_row(case_id)

    st.progress((idx) / len(order), text=f"Block {block_num} of 2 — Case {idx + 1} of {len(order)}")
    st.caption(f"Condition {condition}")

    st.write("Below is a credit/loan application our AI system reviewed. Read the details, "
              "then decide if you agree with its decision.")

    income_label = f"{case['income']:.1f} (higher = higher income bracket)"
    confidence_pct = f"{case['ai_confidence_score']:.0%}"

    box_html = f"""
    <div class="case-box">
        <p class="ai-line">📄 <b>Application details</b></p>
        <p class="ai-line">Payment type: {case['payment_type']}</p>
        <p class="ai-line">Income level: {income_label}</p>
        <p class="ai-line">Credit risk score: {case['credit_risk_score']:.0f} <i>(lower = riskier)</i></p>
        <p class="ai-line">Requested credit limit: {case['proposed_credit_limit']:.0f}</p>
        <hr style="margin: 0.8rem 0; border-color: #444;">
        <p class="ai-line">🤖 <b>AI decision:</b> {case['ai_label']}</p>
        <p class="ai-line">AI confidence: {confidence_pct}</p>
    """

    if condition == "B":
        box_html += '<p class="ai-line" style="margin-top:0.8rem;"><b>Why the AI decided this — ' \
                     'examples of changes that would flip the decision:</b></p>'
        for cf in get_counterfactuals(case_id):
            box_html += f'<p class="cf-line">• {cf}</p>'

    box_html += "</div>"

    st.markdown(box_html, unsafe_allow_html=True)

    st.write("Do you agree with the AI's recommendation?")
    col1, col2 = st.columns(2)
    agree_clicked = col1.button("Agree", use_container_width=True)
    disagree_clicked = col2.button("Disagree", use_container_width=True)

    if agree_clicked or disagree_clicked:
        elapsed = (datetime.now(timezone.utc) - st.session_state.case_start_time).total_seconds()
        save_response(
            st.session_state.participant_id, case_id, condition,
            block_num, agree_clicked, elapsed,
        )
        st.session_state.case_index += 1
        st.session_state.case_start_time = datetime.now(timezone.utc)
        st.rerun()

# ── Stage 3: Break between blocks ───────────────────────────────
elif st.session_state.stage == "interstitial":
    st.title("Block 1 complete")
    st.write("Take a short break if you'd like.")
    st.write("When ready, continue to the second block.")
    if st.button("Continue", type="primary"):
        go_to_block(2, st.session_state.second_condition)
        st.rerun()

# ── Stage 4: Done ────────────────────────────────────────────────
elif st.session_state.stage == "done":
    st.title("Study complete")
    st.write("Thank you for participating. Your responses have been recorded.")
    st.write("You may close this window.")
