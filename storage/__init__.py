"""SQLite access layer (DAO, no ORM — ST7 §1, §2).

Owns schema initialisation/migration, monthly-close upserts (with the
``real`` > ``interpolated`` guard enforced here, ST7 §9), series reads and
sync metadata.
"""
