"""Application configuration layer.

Holds application configuration (host, port, paths) and the Pydantic
validation of USER forecast-flow parameters.

NOTE: the Bear integrity constants do NOT live here. They belong to
``domain/constants.py`` (pure business module) so that ``domain/`` stays
self-contained and the non-regression oracle stays isolated (cf. CLAUDE.md
"Frontière config/ vs domain/").
"""
