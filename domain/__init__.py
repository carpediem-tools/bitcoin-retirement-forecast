"""Pure business pipeline — Aggregation -> Price engine -> Flow engine -> Pipeline.

PURITY RULE (CLAUDE.md): this package depends on NOTHING external — no Flask,
no sqlite3, no requests. Outer layers depend on ``domain/``, never the reverse.
Detailed in Spec technique 8 (out of scope for this scaffold).
"""
