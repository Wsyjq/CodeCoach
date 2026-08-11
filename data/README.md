# Knowledge Data

`knowledge_seed/` contains reviewed first-party teaching cards used by local search and the optional vector-store adapter.

## Layout

```text
data/
  knowledge_seed/
    c_basics.jsonl
    c_mistakes.jsonl
    algorithms_c.jsonl
    problem_patterns.jsonl
  runtime/              generated locally and ignored by Git
```

Every non-empty JSONL line is one card with at least:

```json
{
  "id": "stable_unique_id",
  "title": "Card title",
  "source": "CodeCoach contributors",
  "license": "MIT",
  "category": "c_basic",
  "content": "Reviewed teaching content",
  "tags": ["C语言"]
}
```

## Provenance Policy

- Commit only content you authored or content whose redistribution and modification rights are documented.
- Use an SPDX license identifier such as `MIT`, not labels such as `project_owned` or `unknown`.
- Record the exact source URL and revision for permitted third-party material.
- Do not copy books, paid courses, school handouts, tutorials, coding-platform statements, or solution repositories without explicit compatible permission.
- AI-assisted content must be reviewed for accuracy, originality, and accidental reproduction before submission.
- Pull requests that cannot establish provenance will not be merged.

## Reset Runtime Data

From the repository root on Windows:

```powershell
.\scripts\reset_backend_data.ps1
```

Generated SQLite and vector-store files stay under `data/runtime/` and are excluded from Git and Docker build context. ChromaDB is not installed by default while its current release has an unresolved security advisory; JSONL search works without it.
