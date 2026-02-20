from __future__ import annotations

from collections import defaultdict
from hashlib import md5
from typing import Any

from langgraph.graph import END
from langgraph.graph import START
from langgraph.graph import StateGraph

from agentic_layer.scan_graph.logger import log_agent
from agentic_layer.scan_graph.state import ScanState
from agentic_layer.scan_graph.state import merge_state


def _normalize_severity(value: str | None) -> str:
    severity = (value or "medium").strip().lower()
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "info": "info",
        "informational": "info",
    }
    return mapping.get(severity, "medium")


def _token_set(text: str) -> set[str]:
    normalized = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return {token for token in normalized.split() if token}


def _owasp_id(category: str | None) -> str:
    if not category:
        return "A00"
    prefix = category.split(":", 1)[0].strip()
    return prefix if prefix.startswith("A") else "A00"


def _severity_rank(level: str) -> int:
    return {
        "critical": 5,
        "high": 4,
        "medium": 3,
        "low": 2,
        "info": 1,
    }.get(level, 3)


def _severity_from_rank(rank: int) -> str:
    reverse = {
        5: "critical",
        4: "high",
        3: "medium",
        2: "low",
        1: "info",
    }
    return reverse.get(max(1, min(5, rank)), "medium")


async def artifact_collector_node(state: ScanState) -> ScanState:
    artifacts: list[dict[str, Any]] = []

    for finding in state["normalized_findings"]:
        artifacts.append(
            {
                "source": "layer4_normalized",
                "payload": finding,
            }
        )

    for category_result in state["layer6_results"]:
        for finding in category_result.get("aggregated_findings", []):
            artifacts.append(
                {
                    "source": "layer6_aggregated",
                    "payload": finding,
                }
            )

    log_agent(state["scan_id"], "ArtifactCollector", f"Collected {len(artifacts)} artifacts for dedup")
    return merge_state(
        state,
        {
            "artifact_catalog": artifacts,
            "dedup_phase": "artifacts_collected",
        },
    )


async def format_detector_node(state: ScanState) -> ScanState:
    detected: list[dict[str, Any]] = []
    for artifact in state["artifact_catalog"]:
        payload = artifact.get("payload")
        fmt = "internal_structured" if isinstance(payload, dict) else "unknown"
        detected.append({**artifact, "format": fmt})

    log_agent(state["scan_id"], "FormatDetector", f"Detected formats for {len(detected)} artifacts")
    return merge_state(
        state,
        {
            "artifact_catalog": detected,
            "dedup_phase": "formats_detected",
        },
    )


async def known_format_parsers_node(state: ScanState) -> ScanState:
    parsed: list[dict[str, Any]] = []
    for artifact in state["artifact_catalog"]:
        if artifact.get("format") == "internal_structured":
            parsed.append({**artifact, "parsed_payload": artifact["payload"]})

    log_agent(state["scan_id"], "KnownFormatParsers", f"Parsed {len(parsed)} known-format artifacts")
    return merge_state(
        state,
        {
            "artifact_catalog": parsed,
            "dedup_phase": "formats_parsed",
        },
    )


async def schema_mapper_node(state: ScanState) -> ScanState:
    unified: list[dict[str, Any]] = []
    for index, artifact in enumerate(state["artifact_catalog"], start=1):
        payload = artifact.get("parsed_payload", {})
        title = payload.get("title") or payload.get("message") or "Untitled finding"
        description = payload.get("description") or payload.get("reasoning") or payload.get("message") or title
        category = payload.get("category") or payload.get("owasp_category") or "A04:2021-Insecure Design"
        evidence = payload.get("evidence") or payload.get("snippet") or "No evidence provided"
        file_path = payload.get("file_path") or payload.get("file") or ""
        line_number = int(payload.get("line_number") or payload.get("line") or 0)
        provenance = payload.get("tool_sources") or [payload.get("tool_provenance") or payload.get("scanner") or artifact.get("source")]
        confidence = float(payload.get("confidence") or 0.5)
        reasoning = payload.get("reasoning") or description

        finding_id = payload.get("finding_id")
        if not finding_id:
            digest = md5(f"{title}|{file_path}|{line_number}|{index}".encode("utf-8")).hexdigest()[:12]
            finding_id = f"{state['scan_id']}-uf-{digest}"

        unified.append(
            {
                "finding_id": finding_id,
                "title": str(title),
                "description": str(description),
                "category": str(category),
                "severity": _normalize_severity(payload.get("severity")),
                "evidence": str(evidence),
                "file_path": str(file_path),
                "line_number": line_number,
                "tool_sources": [str(item) for item in provenance if item],
                "confidence": round(confidence, 2),
                "reasoning": str(reasoning),
            }
        )

    log_agent(state["scan_id"], "SchemaMapper", f"Mapped {len(unified)} findings into unified schema")
    return merge_state(
        state,
        {
            "unified_findings": unified,
            "dedup_phase": "schema_mapped",
        },
    )


async def owasp_tagger_node(state: ScanState) -> ScanState:
    tagged: list[dict[str, Any]] = []
    for finding in state["unified_findings"]:
        category = finding["category"].strip()
        normalized_category = category if ":" in category else f"{_owasp_id(category)}:2021-Unknown"
        tagged.append(
            {
                **finding,
                "category": normalized_category,
                "owasp_id": _owasp_id(normalized_category),
            }
        )

    log_agent(state["scan_id"], "OWASPTagger", f"Tagged {len(tagged)} unified findings with OWASP IDs")
    return merge_state(
        state,
        {
            "unified_findings": tagged,
            "dedup_phase": "owasp_tagged",
        },
    )


async def signature_dedup_node(state: ScanState) -> ScanState:
    buckets: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for finding in state["unified_findings"]:
        signature = (
            finding["title"].strip().lower(),
            finding["file_path"].strip().lower(),
            int(finding["line_number"]),
        )
        buckets[signature].append(finding)

    clusters = [{"cluster_id": f"sig-{idx}", "findings": items} for idx, items in enumerate(buckets.values(), start=1)]

    log_agent(
        state["scan_id"],
        "SignatureDedup",
        f"Reduced unified findings {len(state['unified_findings'])} -> {len(clusters)} signature clusters",
    )
    return merge_state(
        state,
        {
            "dedup_clusters": clusters,
            "dedup_phase": "signature_deduped",
        },
    )


def _cluster_description_tokens(cluster: dict[str, Any]) -> set[str]:
    merged = " ".join(item["description"] for item in cluster.get("findings", []))
    return _token_set(merged)


async def semantic_dedup_node(state: ScanState) -> ScanState:
    clusters = list(state["dedup_clusters"])
    reduced: list[dict[str, Any]] = []

    for cluster in clusters:
        current_tokens = _cluster_description_tokens(cluster)
        merged = False
        for existing in reduced:
            existing_tokens = _cluster_description_tokens(existing)
            union = current_tokens | existing_tokens
            overlap = (current_tokens & existing_tokens)
            ratio = (len(overlap) / len(union)) if union else 0.0
            if ratio >= 0.7:
                existing["findings"] = [*existing["findings"], *cluster["findings"]]
                merged = True
                break
        if not merged:
            reduced.append({"cluster_id": cluster["cluster_id"], "findings": list(cluster["findings"])})

    log_agent(
        state["scan_id"],
        "SemanticDedup",
        f"Reduced clusters from {len(clusters)} -> {len(reduced)}",
    )
    return merge_state(
        state,
        {
            "dedup_clusters": reduced,
            "dedup_phase": "semantic_deduped",
        },
    )


ROOT_CAUSE_GROUPS = {
    "secret_management": {"hardcoded", "secret", "key", "entropy", "static"},
    "injection": {"injection", "sql", "query", "taint", "unsafe"},
    "access_control": {"permission", "authorization", "access", "policy"},
}


def _root_cause_for_cluster(cluster: dict[str, Any]) -> str:
    text = " ".join(
        [
            " ".join(
                [
                    finding.get("title", ""),
                    finding.get("description", ""),
                    finding.get("reasoning", ""),
                ]
            )
            for finding in cluster.get("findings", [])
        ]
    ).lower()
    for group_name, keywords in ROOT_CAUSE_GROUPS.items():
        if any(keyword in text for keyword in keywords):
            return group_name
    return "general"


async def context_dedup_node(state: ScanState) -> ScanState:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cluster in state["dedup_clusters"]:
        key = _root_cause_for_cluster(cluster)
        grouped[key].append(cluster)

    collapsed: list[dict[str, Any]] = []
    for root_cause, cluster_list in grouped.items():
        findings: list[dict[str, Any]] = []
        for cluster in cluster_list:
            findings.extend(cluster.get("findings", []))
        collapsed.append(
            {
                "cluster_id": f"ctx-{root_cause}-{len(collapsed)+1}",
                "root_cause": root_cause,
                "findings": findings,
            }
        )

    log_agent(
        state["scan_id"],
        "ContextDedup",
        f"Applied root-cause grouping: {len(state['dedup_clusters'])} -> {len(collapsed)} clusters",
    )
    return merge_state(
        state,
        {
            "dedup_clusters": collapsed,
            "dedup_phase": "context_deduped",
        },
    )


async def merge_executor_node(state: ScanState) -> ScanState:
    merged_clusters: list[dict[str, Any]] = []

    for cluster in state["dedup_clusters"]:
        findings = cluster.get("findings", [])
        if not findings:
            continue

        tool_sources = sorted({tool for finding in findings for tool in finding.get("tool_sources", [])})
        evidences = [finding.get("evidence", "") for finding in findings if finding.get("evidence")]
        reasoning = "\n".join(
            sorted({finding.get("reasoning", "") for finding in findings if finding.get("reasoning")})
        )
        confidence_values = [float(finding.get("confidence", 0.5)) for finding in findings]
        avg_confidence = round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.5

        merged_clusters.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "root_cause": cluster.get("root_cause", "general"),
                "representative": findings[0],
                "evidence": evidences,
                "tool_sources": tool_sources,
                "average_confidence": avg_confidence,
                "reasoning": reasoning,
                "finding_count": len(findings),
            }
        )

    log_agent(state["scan_id"], "MergeExecutor", f"Merged {len(merged_clusters)} clusters into canonical summaries")
    return merge_state(
        state,
        {
            "dedup_clusters": merged_clusters,
            "dedup_phase": "clusters_merged",
        },
    )


CATEGORY_BONUS = {
    "A01": 1,
    "A02": 1,
    "A03": 1,
    "A05": 1,
}


async def severity_adjuster_node(state: ScanState) -> ScanState:
    intelligent: list[dict[str, Any]] = []

    for cluster in state["dedup_clusters"]:
        representative = cluster["representative"]
        base_rank = _severity_rank(_normalize_severity(representative.get("severity")))
        tool_count = len(cluster.get("tool_sources", []))
        confidence = float(cluster.get("average_confidence", 0.5))
        owasp = _owasp_id(representative.get("category"))

        adjusted_rank = base_rank
        if tool_count >= 2:
            adjusted_rank += 1
        if confidence >= 0.75:
            adjusted_rank += 1
        adjusted_rank += CATEGORY_BONUS.get(owasp, 0)

        intelligent.append(
            {
                "finding_id": representative.get("finding_id"),
                "title": representative.get("title"),
                "description": representative.get("description"),
                "category": representative.get("category"),
                "owasp_id": owasp,
                "severity": _severity_from_rank(adjusted_rank),
                "evidence": cluster.get("evidence", []),
                "file_path": representative.get("file_path"),
                "line_number": representative.get("line_number"),
                "tool_sources": cluster.get("tool_sources", []),
                "confidence": confidence,
                "reasoning": cluster.get("reasoning", ""),
                "root_cause": cluster.get("root_cause", "general"),
                "cluster_size": cluster.get("finding_count", 1),
            }
        )

    log_agent(
        state["scan_id"],
        "SeverityAdjuster",
        f"Produced {len(intelligent)} intelligent findings from {len(state['dedup_clusters'])} clusters",
    )
    return merge_state(
        state,
        {
            "intelligent_findings": intelligent,
            "dedup_phase": "dedup_completed",
        },
    )


def build_smart_dedup_subgraph():
    graph = StateGraph(ScanState)

    graph.add_node("artifact_collector", artifact_collector_node)
    graph.add_node("format_detector", format_detector_node)
    graph.add_node("known_format_parsers", known_format_parsers_node)
    graph.add_node("schema_mapper", schema_mapper_node)
    graph.add_node("owasp_tagger", owasp_tagger_node)
    graph.add_node("signature_dedup", signature_dedup_node)
    graph.add_node("semantic_dedup", semantic_dedup_node)
    graph.add_node("context_dedup", context_dedup_node)
    graph.add_node("merge_executor", merge_executor_node)
    graph.add_node("severity_adjuster", severity_adjuster_node)

    graph.add_edge(START, "artifact_collector")
    graph.add_edge("artifact_collector", "format_detector")
    graph.add_edge("format_detector", "known_format_parsers")
    graph.add_edge("known_format_parsers", "schema_mapper")
    graph.add_edge("schema_mapper", "owasp_tagger")
    graph.add_edge("owasp_tagger", "signature_dedup")
    graph.add_edge("signature_dedup", "semantic_dedup")
    graph.add_edge("semantic_dedup", "context_dedup")
    graph.add_edge("context_dedup", "merge_executor")
    graph.add_edge("merge_executor", "severity_adjuster")
    graph.add_edge("severity_adjuster", END)

    return graph.compile()


smart_dedup_subgraph = build_smart_dedup_subgraph()
