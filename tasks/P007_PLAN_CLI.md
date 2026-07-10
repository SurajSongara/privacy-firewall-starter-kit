# P007_PLAN_CLI

Wire the review workflow into the CLI (thin wrappers only). `detect file.pdf --plan review.json [--policy name]` writes a ReviewPlan. `redact file.pdf out.pdf --plan review.json` loads the plan, verifies the source-file hash, and redacts only entries whose resolved decision is `redact`. `redact ... --plan ... --interactive` walks ask-band entries in the terminal (show text + reasons + page, y/n/a=all/q), records decisions back into the plan file, then renders. `--yes` accepts all suggestions non-interactively. Existing flag behavior unchanged when `--plan` is absent.
