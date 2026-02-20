from __future__ import annotations

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


OWASP_MAP = {
    "injection": "A03:2021-Injection",
    "broken_access_control": "A01:2021-Broken Access Control",
    "cryptographic_failures": "A02:2021-Cryptographic Failures",
    "security_misconfiguration": "A05:2021-Security Misconfiguration",
    "vulnerable_components": "A06:2021-Vulnerable and Outdated Components",
}


async def owasp_mapper_node(state: ScanState) -> ScanState:
    # OWASP mapper groups normalized findings into OWASP categories.
    log_agent(state["scan_id"], "OWASPMapper", "Mapping findings to OWASP categories")

    mapped: dict[str, list[dict]] = {}
    for finding in state["findings"]:
        hint = finding.get("category_hint", "security_misconfiguration")
        category = OWASP_MAP.get(hint, "A04:2021-Insecure Design")
        mapped.setdefault(category, []).append(finding)

    log_agent(state["scan_id"], "OWASPMapper", f"OWASP mapping complete with {len(mapped)} categories")

    return merge_state(
        state,
        {
            "owasp_mapped": mapped,
            "owasp_categories": list(mapped.keys()),
            "analysis_stage": "owasp_mapped",
            "phase": "analysis_completed",
        },
    )
