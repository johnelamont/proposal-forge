"""Clients for external systems.

Claude API and Zoho CRM clients will live here. Every call into an external
AI or CRM system goes through this package so that data filtering (R5) and
failure handling (R8) have one place to live. Nothing is implemented until
the corresponding feature has a complete entry in
docs/governance/FEATURE_REGISTER.md.
"""
