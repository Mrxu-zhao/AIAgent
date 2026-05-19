from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LSP_SERVERS = {
    "python": {"cmd": ["pylsp"]},
    "javascript": {"cmd": ["typescript-language-server", "--stdio"]},
    "typescript": {"cmd": ["typescript-language-server", "--stdio"]},
    "go": {"cmd": ["gopls"]},
    "rust": {"cmd": ["rust-analyzer"]},
    "java": {"cmd": ["jdtls"]},
}


@dataclass
class CodeEdit:
    range_start: Tuple[int, int]
    range_end: Tuple[int, int]
    new_text: str
    old_text: str = ""


@dataclass
class CodeReviewResult:
    issues: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    security_concerns: List[Dict[str, Any]] = field(default_factory=list)
    score: float = 0.0


class LSPClient:
    def __init__(self, language: str, workspace: Optional[str] = None):
        self.language = language
        self.workspace = workspace or os.getcwd()
        self.config = LSP_SERVERS.get(language)
        self.process: Optional[subprocess.Popen[str]] = None
        self._req_id = 0
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> bool:
        if not self.config:
            return False
        try:
            self.process = subprocess.Popen(
                self.config["cmd"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.workspace,
            )
            self._send_request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": Path(self.workspace).as_uri(),
                    "capabilities": {"textDocument": {}},
                },
            )
            self._running = True
            return True
        except (FileNotFoundError, OSError):
            logger.info("LSP server unavailable for %s", self.language)
            return False

    def stop(self) -> None:
        if not self.process:
            return
        self._send_notification("shutdown", {})
        self._send_notification("exit", {})
        self.process.terminate()
        self._running = False

    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.process or not self.process.stdin:
            return None
        with self._lock:
            self._req_id += 1
            message = json.dumps({"jsonrpc": "2.0", "id": self._req_id, "method": method, "params": params})
            header = f"Content-Length: {len(message.encode())}\r\n\r\n"
            try:
                self.process.stdin.write(header + message)
                self.process.stdin.flush()
                return self._read_response()
            except Exception:
                return None

    def _send_notification(self, method: str, params: Dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            return
        message = json.dumps({"jsonrpc": "2.0", "method": method, "params": params})
        header = f"Content-Length: {len(message.encode())}\r\n\r\n"
        try:
            self.process.stdin.write(header + message)
            self.process.stdin.flush()
        except Exception:
            return

    def _read_response(self) -> Optional[Dict[str, Any]]:
        if not self.process or not self.process.stdout:
            return None
        headers: List[str] = []
        try:
            while True:
                line = self.process.stdout.readline()
                if not line or line == "\r\n":
                    break
                headers.append(line.strip())
            length = 0
            for header in headers:
                if header.startswith("Content-Length:"):
                    length = int(header.split(":")[1].strip())
            return json.loads(self.process.stdout.read(length)) if length else None
        except Exception:
            return None

    def _did_open(self, file_path: str) -> Optional[str]:
        if not self._running:
            return None
        path = Path(file_path).resolve()
        text = path.read_text(encoding="utf-8", errors="ignore")
        uri = path.as_uri()
        self._send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": uri,
                    "languageId": self.language,
                    "version": 1,
                    "text": text,
                }
            },
        )
        return uri

    def get_diagnostics(self, file_path: str) -> List[Dict[str, Any]]:
        uri = self._did_open(file_path)
        if not uri:
            return []
        result = self._send_request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
        if not result or "result" not in result:
            return []
        diagnostics: List[Dict[str, Any]] = []
        for symbol in result["result"][:30]:
            diagnostics.append(
                {
                    "name": symbol.get("name"),
                    "kind": symbol.get("kind"),
                    "location": symbol.get("location", {}),
                }
            )
        return diagnostics

    def goto_definition(self, file_path: str, line: int, char: int) -> List[Dict[str, Any]]:
        uri = self._did_open(file_path)
        if not uri:
            return []
        result = self._send_request(
            "textDocument/definition",
            {"textDocument": {"uri": uri}, "position": {"line": line, "character": char}},
        )
        if not result or "result" not in result:
            return []
        locations = result["result"]
        if not isinstance(locations, list):
            locations = [locations]
        return [{"uri": item.get("uri"), "range": item.get("range")} for item in locations]


class ASTCodeEditor:
    def apply_edits(self, source: str, edits: List[CodeEdit]) -> str:
        lines = source.split("\n")
        ordered = sorted(edits, key=lambda item: (item.range_start[0], item.range_start[1]), reverse=True)
        for edit in ordered:
            start_line, start_char = edit.range_start
            end_line, end_char = edit.range_end
            if start_line == end_line:
                line = lines[start_line]
                lines[start_line] = line[:start_char] + edit.new_text + line[end_char:]
                continue
            before = lines[start_line][:start_char]
            after = lines[end_line][end_char:]
            lines[start_line : end_line + 1] = (before + edit.new_text + after).split("\n")
        return "\n".join(lines)


class CodeReviewer:
    RULES = {
        "security": [
            {"pattern": r"eval\s*\(", "severity": "high", "msg": "避免使用eval()，存在代码注入风险"},
            {"pattern": r"exec\s*\(", "severity": "high", "msg": "避免使用exec()，存在代码注入风险"},
            {"pattern": r"password\s*=\s*['\"][^'\"]+['\"]", "severity": "high", "msg": "硬编码密码 detected"},
        ],
        "style": [
            {"pattern": r";\s*$", "severity": "low", "msg": "Python中不需要分号"},
            {"pattern": r"print\s*\(", "severity": "low", "msg": "生产代码中避免使用print，改用logging"},
        ],
        "performance": [
            {"pattern": r"for\s+\w+\s+in\s+range\s*\(\s*len\s*\(", "severity": "low", "msg": "考虑使用enumerate()代替range(len())"},
        ],
    }

    def review(self, code: str, language: str = "python") -> CodeReviewResult:
        import re

        _ = language
        result = CodeReviewResult()
        for category, rules in self.RULES.items():
            for rule in rules:
                for match in re.finditer(rule["pattern"], code, re.MULTILINE):
                    issue = {
                        "line": code[: match.start()].count("\n") + 1,
                        "severity": rule["severity"],
                        "message": rule["msg"],
                        "category": category,
                        "match": match.group(0)[:50],
                    }
                    if category == "security":
                        result.security_concerns.append(issue)
                    elif category == "style":
                        result.suggestions.append(issue)
                    else:
                        result.issues.append(issue)

        total = len(result.issues) + len(result.suggestions) + len(result.security_concerns)
        if total == 0:
            result.score = 100.0
            return result

        weights = {"high": 10, "medium": 5, "low": 1}
        penalty = sum(weights.get(item["severity"], 1) for item in result.security_concerns)
        penalty += sum(weights.get(item["severity"], 1) * 0.5 for item in result.issues)
        penalty += sum(weights.get(item["severity"], 1) * 0.2 for item in result.suggestions)
        result.score = max(0.0, 100.0 - penalty)
        return result


class CodeIntelligenceHub:
    def __init__(self):
        self.lsp_clients: Dict[str, LSPClient] = {}
        self.ast_editor = ASTCodeEditor()
        self.reviewer = CodeReviewer()

    def get_lsp(self, language: str, workspace: Optional[str] = None) -> Optional[LSPClient]:
        key = f"{language}:{workspace or os.getcwd()}"
        if key not in self.lsp_clients:
            client = LSPClient(language, workspace)
            if not client.start():
                return None
            self.lsp_clients[key] = client
        return self.lsp_clients[key]

    def shutdown_all(self) -> None:
        for client in self.lsp_clients.values():
            client.stop()
        self.lsp_clients.clear()


def detect_language(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
    }.get(ext, "")


_HUB = CodeIntelligenceHub()


def get_code_hub() -> CodeIntelligenceHub:
    return _HUB
