from __future__ import annotations

OWASP_DEFAULT_CATEGORY = "A04:2021-Insecure Design"

OWASP_HINT_MAP = {
    "injection": "A03:2021-Injection",
    "broken_access_control": "A01:2021-Broken Access Control",
    "cryptographic_failures": "A02:2021-Cryptographic Failures",
    "security_misconfiguration": "A05:2021-Security Misconfiguration",
    "vulnerable_components": "A06:2021-Vulnerable and Outdated Components",
    "insecure_transport": "A04:2021-Insecure Design",
}


def map_category_hint(category_hint: str | None) -> str:
    if not category_hint:
        return OWASP_DEFAULT_CATEGORY
    return OWASP_HINT_MAP.get(category_hint.strip().lower(), OWASP_DEFAULT_CATEGORY)


def get_owasp_id(category: str | None) -> str:
    if not category:
        return "A00"
    prefix = str(category).split(":", 1)[0].strip().upper()
    if prefix.startswith("A") and len(prefix) == 3 and prefix[1:].isdigit():
        return prefix
    return "A00"


def normalize_owasp_category(category_or_hint: str | None) -> str:
    if not category_or_hint:
        return OWASP_DEFAULT_CATEGORY

    value = category_or_hint.strip()
    if ":" in value and get_owasp_id(value) != "A00":
        return value

    return map_category_hint(value)
