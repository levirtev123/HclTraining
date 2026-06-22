# Natural Language to SQL UI

This is a local prototype that accepts normal English questions, translates them into read-only SQL, executes them against a bundled SQLite database, and shows the associated result rows.

## Run

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:8765
```

## Example prompts

- Show pending orders in the west region
- Revenue by region
- Top 3 products by sales
- Enterprise customers
- Pending software orders after 2026-03-01

## Notes

The translator is intentionally conservative and rule-based for the prototype. For production, replace `translate_to_sql()` in `app.py` with a model-backed translator that is constrained by schema metadata, validates output as read-only SQL, and runs with least-privilege database credentials.
