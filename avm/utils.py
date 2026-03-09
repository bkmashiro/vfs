"""
avm/utils.py - Utility functions
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Get current UTC time (timezone-aware).
    
    Replacement for deprecated datetime.utcnow()
    """
    return datetime.now(timezone.utc)
