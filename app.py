"""
app.py

The web interface. Run with: streamlit run app.py

Lets a user upload MULTIPLE contracts, MULTIPLE amendments (optional),
and MULTIPLE invoices, then checks every invoice against the right
contract automatically and shows a summary report.
"""

import os
import tempfile
import pandas as pd
import streamlit as st

from core.engine import load_contracts, load_amendments, process_invoice

st.set_page_config(page_title="Invoice vs Contract Checker", layout="wide")

st.title("📋 Invoice vs Contract Checker")
st.caption(
    "Upload your contracts, any amendments/change orders, and your invoices. "
    "The tool matches each invoice to the right contract (applying the latest "
    "amendments) and flags any deviations."
)

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


def _save_temp(uploaded_file) -> str:
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        return tmp.name


if st.button("🔍 Check Invoices Against Contracts", type="primary"):
    if not contract_files or not invoice_files:
        st.warning("Please upload at least one contract and one invoice.")
    else:
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
            result = process_invoice(invoice_path, contracts, amendments)
            result["invoice_name"] = invoice_file.name
            results.append(result)
            progress.progress((i + 1) / len(invoice_files), text=f"Checked {invoice_file.name}")

        st.success(f"Done. Checked {len(results)} invoice(s).")

        # Summary table
        summary_rows = []
        for r in results:
            summary_rows.append({
                "Invoice": r["invoice_name"],
                "Status": r["status"],
                "Matched Contract": os.path.basename(r["matched_contract"]) if r["matched_contract"] else "—",
                "Issues Found": len(r["issues"]),
            })
        st.subheader("Summary")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

        # Downloadable Excel report
        report_rows = []
        for r in results:
            if r["issues"]:
                for issue in r["issues"]:
                    report_rows.append({
                        "Invoice": r["invoice_name"],
                        "Status": r["status"],
                        "Rule": issue["rule"],
                        "Severity": issue["severity"],
                        "Issue": issue["message"],
                    })
            else:
                report_rows.append({
                    "Invoice": r["invoice_name"],
                    "Status": r["status"],
                    "Rule": "—",
                    "Severity": "—",
                    "Issue": "No issues found.",
                })
        report_df = pd.DataFrame(report_rows)
        excel_path = os.path.join(tempfile.gettempdir(), "invoice_check_report.xlsx")
        report_df.to_excel(excel_path, index=False)
        with open(excel_path, "rb") as f:
            st.download_button(
                "⬇️ Download Full Report (Excel)",
                data=f,
                file_name="invoice_check_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        # Detailed view per invoice
        st.subheader("Details")
        for r in results:
            icon = "✅" if r["status"] == "Clean" else ("🚩" if r["status"] == "Flagged" else "⚠️")
            with st.expander(f"{icon} {r['invoice_name']} — {r['status']}"):
                if r["amendments_applied"] if "amendments_applied" in r else []:
                    st.write("**Amendments applied:**", r.get("amendments_applied"))
                if r["issues"]:
                    for issue in r["issues"]:
                        st.markdown(f"- **[{issue['severity'].upper()}]** ({issue['rule']}) {issue['message']}")
                else:
                    st.write("No issues found.")
                st.json(r["invoice_data"])
