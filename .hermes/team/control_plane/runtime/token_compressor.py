from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

_MAX_URL_LEN = 60
_CJK_PER_TOKEN = 1.5
_ASCII_PER_TOKEN = 4.0
_DEDUP_THRESHOLD = 0.85


@dataclass
class CompressionResult:
    original: str
    compressed: str
    orig_tokens: int
    comp_tokens: int
    ratio: float
    techniques: List[str] = field(default_factory=list)


class TokenCompressor:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._url_cache: Dict[str, str] = {}
        self._stats = {"calls": 0, "orig_tokens": 0, "comp_tokens": 0}

    def compress(self, text: str, ctx_type: str = "general") -> CompressionResult:
        if not text or not isinstance(text, str):
            return CompressionResult(text, text, 0, 0, 0.0)

        original_tokens = self._estimate_tokens(text)
        compressed = text
        techniques: List[str] = []

        if ctx_type in {"web", "general"} and self._has_html(compressed):
            compressed = self._html_to_md(compressed)
            techniques.append("html_to_md")
        if self._has_long_urls(compressed):
            compressed = self._shorten_urls(compressed)
            techniques.append("url_shorten")
        if self._has_repeats(compressed):
            compressed = self._dedup(compressed)
            techniques.append("dedup")
        if ctx_type == "tool" and len(compressed) > 500:
            compressed = self._summarize_tool(compressed)
            techniques.append("tool_summary")
        if ctx_type == "chat":
            compressed = self._compress_chat(compressed)
            techniques.append("chat_compress")

        compressed_tokens = self._estimate_tokens(compressed)
        ratio = (original_tokens - compressed_tokens) / original_tokens if original_tokens else 0.0

        self._stats["calls"] += 1
        self._stats["orig_tokens"] += original_tokens
        self._stats["comp_tokens"] += compressed_tokens
        return CompressionResult(text, compressed, original_tokens, compressed_tokens, ratio, techniques)

    def get_stats(self) -> Dict[str, Any]:
        overall_ratio = 0.0
        if self._stats["orig_tokens"]:
            overall_ratio = (self._stats["orig_tokens"] - self._stats["comp_tokens"]) / self._stats["orig_tokens"]
        return {**self._stats, "overall_ratio": overall_ratio}

    def _has_html(self, text: str) -> bool:
        return bool(re.search(r"<[a-zA-Z][^>]*>", text))

    def _html_to_md(self, html: str) -> str:
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.I)
        replacements = [
            (r"<h1[^>]*>(.*?)</h1>", r"# \1"),
            (r"<h2[^>]*>(.*?)</h2>", r"## \1"),
            (r"<strong[^>]*>(.*?)</strong>", r"**\1**"),
            (r"<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>", r"[\2](\1)"),
            (r"<li[^>]*>(.*?)</li>", r"- \1"),
            (r"<br\s*/?>", "\n"),
            (r"<p[^>]*>(.*?)</p>", r"\1\n"),
        ]
        for pattern, replacement in replacements:
            html = re.sub(pattern, replacement, html, flags=re.DOTALL | re.I)
        html = re.sub(r"<[^>]+>", "", html)
        html = re.sub(r"\n{3,}", "\n\n", html)
        return html.strip()

    def _has_long_urls(self, text: str) -> bool:
        urls = re.findall(r"https?://[^\s<>\"']+", text)
        return any(len(url) > _MAX_URL_LEN for url in urls)

    def _shorten_urls(self, text: str) -> str:
        def replace(match: re.Match[str]) -> str:
            url = match.group(0)
            if len(url) <= _MAX_URL_LEN:
                return url
            if url in self._url_cache:
                return self._url_cache[url]
            parsed = urlparse(url)
            path = parsed.path or ""
            short_path = path[:15] + "..." + path[-10:] if len(path) > 30 else path
            shortened = f"[{parsed.netloc}{short_path}]({url})"
            self._url_cache[url] = shortened
            return shortened

        candidate = re.sub(r"https?://[^\s<>\"']+", replace, text)
        return candidate if len(candidate) < len(text) else text

    def _has_repeats(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return len(lines) >= 5 and len(set(lines)) / len(lines) < _DEDUP_THRESHOLD

    def _dedup(self, text: str) -> str:
        lines = text.splitlines()
        seen = set()
        output = []
        duplicate_run = 0
        for line in lines:
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue
            fingerprint = hashlib.md5(stripped.encode("utf-8")).hexdigest()
            if fingerprint in seen:
                duplicate_run += 1
                if duplicate_run <= 2:
                    output.append("[...重复内容省略...]")
                continue
            seen.add(fingerprint)
            duplicate_run = 0
            output.append(line)
        return "\n".join(output)

    def _summarize_tool(self, output: str) -> str:
        lines = output.splitlines()
        if len(lines) <= 40:
            return output
        head = lines[:12]
        tail = lines[-8:]
        keywords = ("error", "warning", "success", "failed", "passed", "total")
        key_lines = [line for line in lines[12:-8] if any(keyword in line.lower() for keyword in keywords)]
        return "\n".join(head + [f"[... {len(lines) - 20} 行已摘要 ...]"] + key_lines[:8] + tail)

    def _compress_chat(self, text: str) -> str:
        for pattern in (r"\b(um|uh|like|you know)\b", r" {2,}"):
            text = re.sub(pattern, " ", text, flags=re.I)
        return text.strip()

    def _estimate_tokens(self, text: str) -> int:
        cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff")
        ascii_chars = len(text) - cjk
        return int(cjk / _CJK_PER_TOKEN + ascii_chars / _ASCII_PER_TOKEN)


@dataclass
class ContextLayer:
    name: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    max_tokens: int = 0
    summary: str = ""


class MemoryTreeManager:
    def __init__(self, short_term: int = 4000, medium_term: int = 6000, long_term: int = 4000):
        self.short = ContextLayer("short", max_tokens=short_term)
        self.medium = ContextLayer("medium", max_tokens=medium_term)
        self.long = ContextLayer("long", max_tokens=long_term)
        self.compressor = TokenCompressor()

    def add(self, message: Dict[str, Any]) -> None:
        self.short.messages.append(message)
        self._rebalance()

    def get_context(self) -> List[Dict[str, Any]]:
        context = []
        if self.long.summary:
            context.append({"role": "system", "content": f"[长期记忆] {self.long.summary}"})
        context.extend(self.medium.messages)
        context.extend(self.short.messages)
        return context

    def _rebalance(self) -> None:
        short_tokens = sum(self.compressor._estimate_tokens(str(msg.get("content", ""))) for msg in self.short.messages)
        while short_tokens > self.short.max_tokens and len(self.short.messages) > 5:
            oldest = self.short.messages.pop(0)
            compressed = self.compressor.compress(str(oldest.get("content", "")), "chat")
            self.medium.messages.append({**oldest, "content": compressed.compressed, "_layer": "medium"})
            short_tokens = sum(self.compressor._estimate_tokens(str(msg.get("content", ""))) for msg in self.short.messages)

        medium_tokens = sum(self.compressor._estimate_tokens(str(msg.get("content", ""))) for msg in self.medium.messages)
        if medium_tokens > self.medium.max_tokens:
            snippets = [str(msg.get("content", ""))[:100] for msg in self.medium.messages[-20:] if str(msg.get("content", ""))]
            self.long.summary = " | ".join(snippets[:5])
            self.medium.messages = self.medium.messages[-10:]


def create_compressor(config: Optional[Dict[str, Any]] = None) -> TokenCompressor:
    return TokenCompressor(config)


def create_memory_tree(short: int = 4000, medium: int = 6000, long: int = 4000) -> MemoryTreeManager:
    return MemoryTreeManager(short, medium, long)


def build_context_summary(knowledge_bundle: Dict[str, Any]) -> Dict[str, Any]:
    compressor = TokenCompressor()
    paths = list(knowledge_bundle.get("paths", []))
    excerpt = "\n".join(paths[:5])
    result = compressor.compress(excerpt, "tool") if excerpt else CompressionResult("", "", 0, 0, 0.0, [])
    return {
        "path_count": len(paths),
        "summary": result.compressed,
        "compression_ratio": round(result.ratio, 2),
    }
