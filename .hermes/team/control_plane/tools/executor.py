from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Iterable, List, Optional, Tuple

from tools.spec import ToolExecutionContext, ToolResult, ToolSpec
from tools.transcript import ToolTranscriptStore


ToolRequest = Tuple[ToolSpec, Dict[str, object]]


class ToolExecutor:
    def __init__(self, transcript_store: Optional[ToolTranscriptStore] = None):
        self.transcript_store = transcript_store

    def execute_many(
        self,
        context: ToolExecutionContext,
        requests: Iterable[ToolRequest],
    ) -> List[ToolResult]:
        indexed_requests = list(enumerate(requests))
        results: List[Optional[ToolResult]] = [None] * len(indexed_requests)
        cursor = 0
        while cursor < len(indexed_requests):
            index, (tool, payload) = indexed_requests[cursor]
            if self._can_run_in_parallel(tool):
                batch = []
                while cursor < len(indexed_requests):
                    next_index, (next_tool, next_payload) = indexed_requests[cursor]
                    if not self._can_run_in_parallel(next_tool):
                        break
                    batch.append((next_index, next_tool, next_payload))
                    cursor += 1
                self._execute_parallel_batch(context, batch, results)
                continue
            results[index] = self._execute_one(context, tool, payload)
            cursor += 1
        return [result for result in results if result is not None]

    def _execute_parallel_batch(
        self,
        context: ToolExecutionContext,
        batch: List[Tuple[int, ToolSpec, Dict[str, object]]],
        results: List[Optional[ToolResult]],
    ) -> None:
        with ThreadPoolExecutor(max_workers=max(1, len(batch))) as pool:
            future_map = {
                pool.submit(self._execute_one, context, tool, payload): index
                for index, tool, payload in batch
            }
            for future, index in future_map.items():
                results[index] = future.result()

    def _execute_one(
        self,
        context: ToolExecutionContext,
        tool: ToolSpec,
        payload: Dict[str, object],
    ) -> ToolResult:
        try:
            result = tool.handler(context, payload)
        except Exception as exc:
            result = ToolResult.error_result(error=str(exc), content="")
        self._write_transcript(context, tool, payload, result)
        return result

    def _write_transcript(
        self,
        context: ToolExecutionContext,
        tool: ToolSpec,
        payload: Dict[str, object],
        result: ToolResult,
    ) -> None:
        if self.transcript_store is None:
            return
        self.transcript_store.append_record(
            {
                "task_id": context.task_id,
                "tool_name": tool.name,
                "agent_id": context.agent_id,
                "backend": context.backend,
                "input": payload,
                "ok": result.ok,
                "error": result.error,
                "content_preview": result.content[:200],
                "artifacts": list(result.artifacts),
                "knowledge_paths": list(context.knowledge_bundle.get("paths", [])),
                "timestamp": time.time(),
            }
        )

    @staticmethod
    def _can_run_in_parallel(tool: ToolSpec) -> bool:
        return tool.is_read_only and tool.is_concurrency_safe
