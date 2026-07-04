"""
app.py

The web interface. Run with: streamlit run app.py
"""

import os
import time
import tempfile
import pandas as pd
import streamlit as st

from core.engine import load_contracts, load_amendments, process_invoice

st.set_page_config(page_title="Invoice & Contract Compliance Checker", layout="wide")

# ---------------------------------------------------------------------------
# Styling — a plain, professional look (no emoji, muted palette, clean type)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}

    .stApp { background-color: #ffffff; }
    .block-container { padding-top: 2rem; max-width: 1100px; background-color: #ffffff; }
    html, body, [class*="css"] { font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
        color: #1a1f36; }

    p, span, div, label, li { color: #1a1f36; }

    .app-header { border-bottom: 1px solid #dfe3e8; padding-bottom: 1.1rem; margin-bottom: 1.6rem; }
    .app-header h1 { font-size: 1.65rem; font-weight: 600; color: #1a1f36 !important; margin: 0 0 0.3rem 0; }
    .app-header p { color: #5b6270 !important; font-size: 0.95rem; margin: 0; }

    .section-label { font-size: 0.78rem; font-weight: 600; letter-spacing: 0.06em;
        color: #7a8090 !important; text-transform: uppercase; margin: 1.4rem 0 0.5rem 0; }

    .instructions-box { background-color: #f6f7f9; border: 1px solid #e3e6ea; border-radius: 6px;
        padding: 0.9rem 1.1rem; font-size: 0.88rem; color: #3d4250 !important; line-height: 1.55; margin-bottom: 1rem; }
    .instructions-box strong { color: #1a1f36 !important; }
    .instructions-box li { color: #3d4250 !important; }
    .instructions-box ol { margin: 0.3rem 0 0 1.1rem; padding: 0; }

    .status-pill { display: inline-block; padding: 2px 11px; border-radius: 3px;
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
    .status-clean   { background-color: #e6f4ea; color: #1c7c37 !important; }
    .status-flagged { background-color: #fbe9e9; color: #b3261e !important; }
    .status-nomatch { background-color: #fdf2e0; color: #97660a !important; }

    .metric-card { border: 1px solid #e3e6ea; border-radius: 6px; padding: 0.9rem 1.1rem;
        text-align: left; background-color: #ffffff; }
    .metric-card .label { font-size: 0.75rem; color: #7a8090 !important; text-transform: uppercase;
        letter-spacing: 0.04em; margin-bottom: 0.25rem; }
    .metric-card .value { font-size: 1.35rem; font-weight: 700; color: #1a1f36 !important; }
    .metric-card .subtext { font-size: 0.75rem; color: #8a90a0 !important; margin-top: 0.15rem; }

    div.stButton > button { background-color: #1a1f36; color: #ffffff !important; border-radius: 5px;
        border: none; padding: 0.55rem 1.4rem; font-weight: 600; }
    div.stButton > button:hover { background-color: #2c3352; color: #ffffff !important; }
    div.stButton > button p { color: #ffffff !important; }

    /* File uploader and text areas: force readable text on a white background */
    [data-testid="stFileUploaderDropzone"] { background-color: #f6f7f9 !important; }
    .stTextArea textarea { color: #1a1f36 !important; background-color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-header">
    <h1>Invoice &amp; Contract Compliance Checker</h1>
    <p>Automated verification of vendor invoices against contracted terms, amendments, and configurable review rules.</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Brief instructions
# ---------------------------------------------------------------------------
st.markdown("""
<div class="instructions-box">
<strong>How to use this tool</strong>
<ol>
<li>Upload one or more contracts, any related amendments, and the invoices you want checked.</li>
<li>Optionally, add any additional checks you want considered, below.</li>
<li>Click "Check Invoices Against Contracts." Each invoice is matched to the correct contract
(including any amendments) and reviewed for pricing, arithmetic, timing, and tax-jurisdiction issues.</li>
</ol>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Documents</div>', unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    contract_files = st.file_uploader(
        "Contracts", type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
with col2:
    amendment_files = st.file_uploader(
        "Amendments / Change Orders (optional)",
        type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
with col3:
    invoice_files = st.file_uploader(
        "Invoices", type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

# ---------------------------------------------------------------------------
# Custom, user-defined checks
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Additional Checks (Optional)</div>', unsafe_allow_html=True)
custom_instructions = st.text_area(
    "Describe any extra things you want checked, in plain English.",
    placeholder=(
        "Examples:\n"
        "- Flag any invoice that does not reference a purchase order number.\n"
        "- Flag invoices billed in a currency other than the contract currency.\n"
        "- Flag any line item described as a \"fee\" without further detail."
    ),
    height=100,
    label_visibility="collapsed",
)

st.markdown('<div class="section-label">Assumptions</div>', unsafe_allow_html=True)
manual_minutes_per_invoice = st.number_input(
    "Estimated manual review time per invoice (minutes) — used only to calculate time saved below",
    min_value=1, max_value=120, value=15, step=1,
)


def _save_temp(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


run_clicked = st.button("Check Invoices Against Contracts", type="primary")

if run_clicked:
    if not contract_files or not invoice_files:
        st.warning("Please upload at least one contract and one invoice.")
    else:
        start_time = time.perf_counter()

        with st.spinner("Reading and parsing contracts..."):
            contract_paths = [_save_temp(f) for f in contract_files]
            contracts = load_contracts(contract_paths)

        amendments = []
        if amendment_files:
            with st.spinner("Reading and parsing amendments..."):
                amendment_paths = [_save_temp(f) for f in amendment_files]
                amendments = load_amendments(amendment_paths)

        results = []
        progress = st.progress(0.0, text="Checking invoices...")
        for i, invoice_file in enumerate(invoice_files):
            invoice_path = _save_temp(invoice_file)
            result = process_invoice(invoice_path, contracts, amendments, custom_instructions)
            result["invoice_name"] = invoice_file.name
            results.append(result)
            progress.progress((i + 1) / len(invoice_files), text=f"Checked {invoice_file.name}")
        progress.empty()

        elapsed_seconds = time.perf_counter() - start_time

        # -------------------------------------------------------------
        # Time-savings summary — the core "why this beats a chat window" proof
        # -------------------------------------------------------------
        manual_total_minutes = len(invoice_files) * manual_minutes_per_invoice
        automated_minutes = elapsed_seconds / 60
        time_saved_minutes = max(manual_total_minutes - automated_minutes, 0)
        pct_faster = (
            round((time_saved_minutes / manual_total_minutes) * 100)
            if manual_total_minutes > 0 else 0
        )

        st.markdown('<div class="section-label">Results Overview</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f"""<div class="metric-card"><div class="label">Invoices Checked</div>
                <div class="value">{len(results)}</div></div>""", unsafe_allow_html=True)
        with m2:
            st.markdown(f"""<div class="metric-card"><div class="label">Automated Time</div>
                <div class="value">{elapsed_seconds:.0f} sec</div></div>""", unsafe_allow_html=True)
        with m3:
            st.markdown(f"""<div class="metric-card"><div class="label">Estimated Manual Time</div>
                <div class="value">{manual_total_minutes} min</div>
                <div class="subtext">at {manual_minutes_per_invoice} min/invoice</div></div>""", unsafe_allow_html=True)
        with m4:
            st.markdown(f"""<div class="metric-card"><div class="label">Time Saved</div>
                <div class="value">{time_saved_minutes:.0f} min</div>
                <div class="subtext">~{pct_faster}% faster</div></div>""", unsafe_allow_html=True)

        st.write("")

        # Summary table
        summary_rows = []
        for r in results:
            summary_rows.append({
                "Invoice": r["invoice_name"],
                "Status": r["status"],
                "Matched Contract": os.path.basename(r["matched_contract"]) if r["matched_contract"] else "—",
                "Issues Found": len(r["issues"]),
            })
        st.markdown('<div class="section-label">Summary</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        # Downloadable Excel report
        report_rows = []
        for r in results:
            if r["issues"]:
                for issue in r["issues"]:
                    report_rows.append({
                        "Invoice": r["invoice_name"],
                        "Status": r["status"],
                        "Issue Category": issue.get("category", issue["rule"]),
                        "Severity": issue["severity"].title(),
                        "Explanation": issue["message"],
                    })
            else:
                report_rows.append({
                    "Invoice": r["invoice_name"],
                    "Status": r["status"],
                    "Issue Category": "—",
                    "Severity": "—",
                    "Explanation": "No issues found.",
                })
        report_df = pd.DataFrame(report_rows)
        excel_path = os.path.join(tempfile.gettempdir(), "invoice_check_report.xlsx")
        report_df.to_excel(excel_path, index=False)
        with open(excel_path, "rb") as f:
            st.download_button(
                "Download Full Report (Excel)",
                data=f,
                file_name="invoice_check_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Detailed view per invoice
        st.markdown('<div class="section-label">Details</div>', unsafe_allow_html=True)
        status_class = {
            "Clean": "status-clean",
            "Flagged": "status-flagged",
            "No Matching Contract Found": "status-nomatch",
        }
        for r in results:
            with st.expander(f"{r['invoice_name']}  —  {r['status']}"):
                st.markdown(
                    f'<span class="status-pill {status_class.get(r["status"], "status-nomatch")}">{r["status"]}</span>',
                    unsafe_allow_html=True,
                )
                st.write("")

                data = r["invoice_data"] or {}
                st.markdown(
                    f"**Vendor:** {data.get('vendor_name') or 'Not found'}  \n"
                    f"**Invoice Number:** {data.get('invoice_number') or 'Not found'}  \n"
                    f"**Invoice Date:** {data.get('invoice_date') or 'Not found'}  \n"
                    f"**Total:** {data.get('total') if data.get('total') is not None else 'Not found'} "
                    f"{data.get('currency') or ''}  \n"
                    f"**Matched Contract:** "
                    f"{os.path.basename(r['matched_contract']) if r['matched_contract'] else 'No matching contract found'}"
                )

                amendments_applied = r.get("amendments_applied") or []
                if amendments_applied:
                    st.markdown("**Amendments applied to this contract:**")
                    for summary in amendments_applied:
                        st.markdown(f"- {summary}")

                if r["issues"]:
                    st.markdown("**Issues found:**")
                    issue_table = pd.DataFrame([
                        {
                            "Issue Category": issue.get("category", issue["rule"]),
                            "Severity": issue["severity"].title(),
                            "Explanation": issue["message"],
                        }
                        for issue in r["issues"]
                    ])
                    st.table(issue_table)
                else:
                    st.markdown("No issues found. This invoice matches the contract terms.")
