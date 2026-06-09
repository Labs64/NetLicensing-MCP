"""Shared warning thresholds for P1.8 (customer health) and P1.9 (validation explainer).

Tests can monkeypatch these module attributes.
"""

WARN_DAYS: int = 30
CRITICAL_DAYS: int = 7
WARN_QUOTA_PCT: float = 0.90
