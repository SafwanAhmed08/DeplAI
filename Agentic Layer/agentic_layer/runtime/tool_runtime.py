from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Callable

from agentic_layer.scan_graph.logger import log_agent


class ToolRuntime:
    def __init__(self, scan_id: str, timeout_seconds: int = 60) -> None:
        self.scan_id = scan_id
        self.timeout_seconds = timeout_seconds
        self._tool_specs: dict[str, dict[str, str | Callable[[str], list[str]]]] = {
            "access_path_scan": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_access_path_scan_cmd,
            },
            "policy_gap_scan": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_policy_gap_scan_cmd,
            },
            "crypto_key_scan": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_crypto_key_scan_cmd,
            },
            "config_entropy_check": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_config_entropy_check_cmd,
            },
            "ast_deep_scan": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_ast_deep_scan_cmd,
            },
            "regex_injection": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_regex_injection_cmd,
            },
            "taint_sim": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_taint_sim_cmd,
            },
            "generic_pattern_scan": {
                "image": "python:3.11-alpine",
                "command_builder": self._build_generic_pattern_scan_cmd,
            },
        }

    def run_tool(self, tool_name: str, repo_path: str) -> dict:
        repo_dir = Path(repo_path).resolve()
        if tool_name not in self._tool_specs:
            raise ValueError(f"Unsupported tool_name: {tool_name}")
        if not repo_dir.exists() or not repo_dir.is_dir():
            raise ValueError(f"Invalid repo_path: {repo_path}")

        tool_spec = self._tool_specs[tool_name]
        image = str(tool_spec["image"])
        command_builder = tool_spec["command_builder"]
        command = command_builder(tool_name)

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "512m",
            "--pids-limit",
            "128",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "-v",
            f"{repo_dir}:/workspace:ro",
            "-w",
            "/workspace",
            image,
            *command,
        ]

        log_agent(self.scan_id, "ToolRuntime", f"Starting tool={tool_name}")
        started_at = time.monotonic()
        try:
            completed = subprocess.run(
                docker_cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            stdout = self._sanitize_output(completed.stdout)
            stderr = self._sanitize_output(completed.stderr)
            contract = self._validate_and_parse_contract(tool_name=tool_name, exit_code=int(completed.returncode), stdout=stdout)
            parsed_findings = contract["parsed_findings"]
            status = contract["status"]

            log_agent(
                self.scan_id,
                "ToolRuntime",
                f"Completed tool={tool_name} exit_code={completed.returncode}",
            )
            if status == "completed":
                log_agent(self.scan_id, "ToolRuntime", "Tool contract validation passed")
            log_agent(
                self.scan_id,
                "ToolRuntime",
                f"Parsed findings count={len(parsed_findings)}",
            )
            return {
                "tool_name": tool_name,
                "exit_code": int(completed.returncode),
                "execution_time_ms": elapsed_ms,
                "stdout": stdout,
                "stderr": stderr,
                "status": status,
                "parsed_findings": parsed_findings,
                "summary": contract["summary"],
            }
        except subprocess.TimeoutExpired as exc:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            stdout = self._sanitize_output(exc.stdout or "")
            stderr = self._sanitize_output(exc.stderr or "")
            log_agent(self.scan_id, "ToolRuntime", f"Timeout tool={tool_name}")
            return {
                "tool_name": tool_name,
                "exit_code": 124,
                "execution_time_ms": elapsed_ms,
                "stdout": stdout,
                "stderr": stderr,
                "status": "failed",
                "parsed_findings": [],
                "summary": {},
            }
        except FileNotFoundError:
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            error = "docker executable not found"
            log_agent(self.scan_id, "ToolRuntime", f"Completed tool={tool_name} exit_code=127")
            return {
                "tool_name": tool_name,
                "exit_code": 127,
                "execution_time_ms": elapsed_ms,
                "stdout": "",
                "stderr": error,
                "status": "failed",
                "parsed_findings": [],
                "summary": {},
            }
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.monotonic() - started_at) * 1000)
            message = self._sanitize_output(str(exc))
            log_agent(self.scan_id, "ToolRuntime", f"Completed tool={tool_name} exit_code=1")
            return {
                "tool_name": tool_name,
                "exit_code": 1,
                "execution_time_ms": elapsed_ms,
                "stdout": "",
                "stderr": message,
                "status": "failed",
                "parsed_findings": [],
                "summary": {},
            }

    def _validate_and_parse_contract(self, tool_name: str, exit_code: int, stdout: str) -> dict:
        if exit_code != 0:
            return {"status": "failed", "parsed_findings": [], "summary": {}}
        if not stdout:
            return {"status": "failed", "parsed_findings": [], "summary": {}}

        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return {"status": "failed", "parsed_findings": [], "summary": {}}

        if not isinstance(payload, dict):
            return {"status": "failed", "parsed_findings": [], "summary": {}}

        findings_value = payload.get("findings")
        if not isinstance(findings_value, list):
            return {"status": "failed", "parsed_findings": [], "summary": {}}

        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        parsed_findings = self._extract_findings_from_json(tool_name, payload)
        return {"status": "completed", "parsed_findings": parsed_findings, "summary": summary}

    def _extract_findings_from_json(self, tool_name: str, payload: object) -> list[dict]:
        raw_findings: list[dict]
        if not isinstance(payload, dict):
            return []

        findings_value = payload.get("findings")
        if not isinstance(findings_value, list):
            return []
        raw_findings = [item for item in findings_value if isinstance(item, dict)]

        normalized: list[dict] = []
        for item in raw_findings:
            normalized.append(
                {
                    "category": str(item.get("category") or self._infer_category(tool_name)),
                    "title": str(item.get("title") or f"{tool_name} finding"),
                    "severity": str(item.get("severity") or self._infer_severity(tool_name)),
                    "evidence": str(item.get("evidence") or item.get("message") or ""),
                    "tool_provenance": tool_name,
                    "confidence": float(item.get("confidence") or 0.6),
                    "reasoning": str(item.get("reasoning") or "Tool output parsed as JSON."),
                    "origin_parser": "strict_json",
                }
            )
        return normalized

    def _sanitize_output(self, text: str) -> str:
        if not text:
            return ""
        redacted = text
        patterns = [
            r"gh[pousr]_[A-Za-z0-9_]+",
            r"lsv2_[A-Za-z0-9_]+",
            r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+",
            r"(?i)(api[_-]?key\s*[=:]\s*)[^\s\"']+",
            r"(?i)(token\s*[=:]\s*)[^\s\"']+",
        ]
        for pattern in patterns:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted[:8000]

    def _infer_category(self, tool_name: str) -> str:
        mapping = {
            "access_path_scan": "A01:2021-Broken Access Control",
            "policy_gap_scan": "A01:2021-Broken Access Control",
            "crypto_key_scan": "A02:2021-Cryptographic Failures",
            "config_entropy_check": "A02:2021-Cryptographic Failures",
            "ast_deep_scan": "A03:2021-Injection",
            "regex_injection": "A03:2021-Injection",
            "taint_sim": "A03:2021-Injection",
        }
        return mapping.get(tool_name, "A04:2021-Insecure Design")

    def _infer_severity(self, tool_name: str) -> str:
        high_tools = {"taint_sim", "crypto_key_scan", "access_path_scan"}
        return "high" if tool_name in high_tools else "medium"

    def _build_access_path_scan_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; findings=[]; "
                "files=list(pathlib.Path('/workspace').rglob('*.py'))[:200]; "
                "\nfor p in files:\n"
                " t=p.read_text(encoding='utf-8',errors='ignore');\n"
                " if 'chmod(777' in t or 'allow_all' in t.lower():\n"
                "  findings.append({'title':'Overly permissive access pattern','evidence':str(p),'severity':'high'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_policy_gap_scan_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; findings=[]; "
                "targets=list(pathlib.Path('/workspace').rglob('*.y*ml'))[:200]; "
                "\nfor p in targets:\n"
                " t=p.read_text(encoding='utf-8',errors='ignore').lower();\n"
                " if 'public: true' in t or 'anonymous' in t:\n"
                "  findings.append({'title':'Potential policy gap','evidence':str(p),'severity':'medium'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_crypto_key_scan_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib, re; findings=[]; pat=re.compile(r'(AKIA[0-9A-Z]{16}|secret[_-]?key)', re.I); "
                "files=list(pathlib.Path('/workspace').rglob('*'))[:300]; "
                "\nfor p in files:\n"
                " if not p.is_file():\n"
                "  continue\n"
                " t=p.read_text(encoding='utf-8',errors='ignore');\n"
                " if pat.search(t):\n"
                "  findings.append({'title':'Potential key material exposure','evidence':str(p),'severity':'high'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_config_entropy_check_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; findings=[]; "
                "files=list(pathlib.Path('/workspace').rglob('.env*'))[:100]; "
                "\nfor p in files:\n"
                " t=p.read_text(encoding='utf-8',errors='ignore');\n"
                " if 'password=' in t.lower() or 'token=' in t.lower():\n"
                "  findings.append({'title':'Sensitive config value detected','evidence':str(p),'severity':'medium'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_ast_deep_scan_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; findings=[]; "
                "files=list(pathlib.Path('/workspace').rglob('*.py'))[:200]; "
                "\nfor p in files:\n"
                " t=p.read_text(encoding='utf-8',errors='ignore');\n"
                " if 'exec(' in t or 'eval(' in t:\n"
                "  findings.append({'title':'Dynamic execution primitive','evidence':str(p),'severity':'high'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_regex_injection_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib, re; findings=[]; "
                "files=list(pathlib.Path('/workspace').rglob('*'))[:250]; "
                "pat=re.compile(r'(SELECT\\s+.+\\s+FROM|http://|password\\s*=)', re.I); "
                "\nfor p in files:\n"
                " if not p.is_file():\n"
                "  continue\n"
                " t=p.read_text(encoding='utf-8',errors='ignore');\n"
                " if pat.search(t):\n"
                "  findings.append({'title':'Injection-related pattern match','evidence':str(p),'severity':'medium'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_taint_sim_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; findings=[]; "
                "files=list(pathlib.Path('/workspace').rglob('*.py'))[:200]; "
                "\nfor p in files:\n"
                " t=p.read_text(encoding='utf-8',errors='ignore').lower();\n"
                " if 'request.args' in t and ('execute(' in t or 'subprocess' in t):\n"
                "  findings.append({'title':'Potential source-to-sink dataflow','evidence':str(p),'severity':'high'});\n"
                "print(json.dumps({'findings':findings}))"
            ),
        ]

    def _build_generic_pattern_scan_cmd(self, _: str) -> list[str]:
        return [
            "python",
            "-c",
            (
                "import json, pathlib; files=sum(1 for _ in pathlib.Path('/workspace').rglob('*') if _.is_file()); "
                "print(json.dumps({'findings':[{'title':'Repository scanned','evidence':f'files={files}','severity':'low'}]}))"
            ),
        ]