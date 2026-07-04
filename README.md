# Invoice vs Contract Checker

An AI-assisted tool for financial controllers: upload your contracts,
amendments/change orders, and invoices, and it automatically matches each
invoice to the right (currently effective) contract and flags deviations —
overcharges, arithmetic errors, stale invoices, cross-jurisdiction tax
issues, and more — without checking each invoice by hand.

**Live demo:** _(add your published Replit / Hugging Face link here)_

## How it works

```
Contracts ──┐
Amendments ─┼─► Parse into structured data (LLM-assisted extraction)
Invoices ───┘
                │
                ▼
     Match each invoice to its contract
     (contract/PO number, or vendor name similarity)
                │
                ▼
     Apply any amendments to get the
     CURRENT effective contract terms
                │
                ▼
     Run deterministic rule checks           Run one LLM "judgment" pass
     (math, staleness, rate limits,    +     for fuzzier issues (scope
      tax jurisdiction rules)                creep, inconsistencies)
                │
                ▼
        Summary report (on-screen + downloadable Excel)
```

Deterministic checks (arithmetic, staleness, rate limits, tax rules) never
rely on AI — they're plain code, so they're 100% reliable and explainable.
The AI is used only where genuine judgment is needed: reading messy
document text, and evaluating fuzzy edge cases.

## Project structure

```
core/           the engine (extraction, matching, orchestration) — no UI code here
rules/          pluggable rule checks — see "Adding your own rule" below
config/         user-editable settings, e.g. tax jurisdiction rules (no code needed)
sample_data/    fictional sample contract/amendment/invoices for safe testing
app.py          the Streamlit web interface
```

## Running it yourself

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_free_groq_api_key   # https://console.groq.com
streamlit run app.py
```

No local AI model required — this uses Groq's free API by default. To run
with a fully local, zero-cost model instead (no API key, no internet
required at inference time), install [Ollama](https://ollama.com), pull a
model (e.g. `ollama pull llama3.1`), and set `LLM_BACKEND=ollama` before
running.

## Adding your own rule

This is what makes the tool extensible for any controller, in any country,
with any rule set:

1. Copy `rules/community/example_rule_template.py` to a new file.
2. Subclass `BaseRule` (see `rules/base_rule.py`) and implement `check()`.
3. Register your new rule in `rules/registry.py`'s `get_active_rules()`.

No changes to the core engine are needed — the engine only knows that a
rule takes `(invoice_data, contract_data)` and returns a list of `Issue`s.

## Adding your own tax jurisdiction rules

Edit `config/tax_rules.yaml` — no coding required. Add a rule for any
vendor-country → buyer-country pair and whether tax should apply.

## Limitations & honest disclaimers

- This tool does not know tax law on its own — cross-jurisdiction tax
  checks only apply the rules you configure in `config/tax_rules.yaml`.
  It is not a source of legal or tax advice.
- LLM-based extraction and judgment can make mistakes, especially on
  messy or low-quality scans. Always review flagged (and a sample of
  clean) results before relying on them for financial decisions.
- Contract-to-invoice matching uses vendor name similarity as a fallback
  when no exact contract/PO reference is found — verify matches on
  ambiguous vendor names.

## License

MIT — see `LICENSE`. Contributions welcome.
