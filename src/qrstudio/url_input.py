"""Deterministic URL shortcuts shared by desktop, Android and tests."""
import re


def complete_url(value: str, commit=False) -> str:
    # Double-space may arrive literally or as an IME's automatic '. ' insertion.
    double_space=value.endswith("  ") or value.endswith(". ")
    if not commit and not double_space:
        return value
    value=(value[:-2] if double_space else value).strip()
    value=re.sub(r"^https[;:]//", "https://", value, flags=re.I)
    if not value:
        return "https://"
    if re.match(r"^[a-z][a-z0-9+.-]*://",value,re.I):
        return value
    return "https://"+value
