"""Local review UI: a thin web client over the ReviewPlan.

The UI holds zero business logic — it renders page images with
detection overlays, edits ``decision`` fields on the ReviewPlan, and
asks the engine to apply the result. Requires the ``ui`` extra
(``pip install privacy-firewall[ui]``).
"""
