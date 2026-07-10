# P010_FEEDBACK_MEMORY

Persist review decisions to reduce future review burden. When a user keeps a detection the engine suggested redacting (or vice versa), offer to record it: exact-value allowlist entries and simple context patterns, stored per policy profile in a local user config dir. DecisionEngine consults memory before assigning `ask`. Explicit opt-in per entry (privacy tool — never silently remember PII values; store salted hashes of values, not plaintext). Deferred until P009 has real usage.
