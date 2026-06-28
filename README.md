# Fraud Review Study — Streamlit App

## Setup

1. Install dependencies:
   ```
   pip install streamlit pandas
   ```

2. Keep these 4 files in the same folder:
   - `app.py`
   - `study_cases_condition_A.csv`
   - `counterfactuals_condition_B.csv`
   - `latin_square_assignment.csv`

3. Run:
   ```
   streamlit run app.py
   ```
   This opens a local URL (e.g. `http://localhost:8501`) in your browser.

## Running participants

- Each participant opens the link and picks an open slot from a dropdown
  (only unused IDs are shown — no names collected, no collisions possible).
- Clicking Start immediately reserves that slot (written to
  `participant_locks.csv`) so two people can't grab the same one even if
  they click within seconds of each other.
- If someone reserves a slot but never finishes (closes the tab), it
  automatically frees up again after 30 minutes of inactivity.
- They review all 10 cases in block 1, see a short break screen, then
  review the same 10 cases (different random order) in block 2 under
  the other condition.
- Each click on Agree/Disagree is saved immediately to
  `user_study_responses.csv`, created automatically in the same folder.

## Output

`user_study_responses.csv` will contain one row per case-view, with columns:
`participant_id, block, condition, case_id, ai_recommendation, participant_decision,
agreed_with_ai, response_time_seconds, timestamp_utc`

This is the exact file your analysis notebook's Section 17 expects
(`pd.read_csv('user_study_responses.csv')`) — no reformatting needed.

## Checking results / downloading data

While the app is running (local or deployed), open it with `?admin=true`
added to the URL — e.g. `https://your-app.streamlit.app/?admin=true`.
This shows a researcher-only view: response count, the full data table,
a download button for `user_study_responses.csv`, and which participant
slots are still open. This view is hidden from the normal participant
flow — they'd never see it unless given this exact URL.

## Hosting for remote participants

Running locally only works if participants are physically at your machine.
For remote participants, deploy for free via Streamlit Community Cloud
(streamlit.io/cloud):
1. Push this whole folder (including `requirements.txt`) to a public GitHub repo
2. Sign into streamlit.io/cloud with GitHub, click "New app", point it at the repo
3. You get a public URL to share with all 20 participants

Responses and locks save to the deployed app's own filesystem, which can
reset if the app restarts or redeploys. For a short data-collection window
this is usually fine — just avoid pushing code changes to the repo while
participants are mid-study, and download `user_study_responses.csv` from
the app promptly once everyone's done.

## Known data issue to check before running participants

Some counterfactuals reference negative `credit_risk_score` values (e.g. -166),
which aren't realistic. Worth a quick look at `counterfactuals_condition_B.csv`
before launch — these come from the DiCE generation step in the analysis
notebook, not from this app.
