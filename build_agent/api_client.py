from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests


@dataclass(frozen=True)
class DispatchTask:
    task_id: str
    tool_meta: Dict[str, Any]


def dispatch_task(
    dispatch_url: str,
    worker_ip: str,
    timeout: int = 30,
) -> Optional[DispatchTask]:
    """
    调度接口：POST /api/v1/dispatch

    预期返回：
    {
      "task_id": "...",
      "tool_meta": {...}
    }

    当无任务时，可能返回非 200 或空 body；此处统一返回 None。
    """
    try:
        resp = requests.post(
            dispatch_url,
            headers={"accept": "application/json", "Content-Type": "application/json"},
            json={"worker_ip": worker_ip},
            timeout=timeout,
        )
    except Exception as e:
        print(f"[dispatch] ERROR: {e}")
        return None

    if resp.status_code != 200:
        # 常见：204/404/429/500 等
        return None

    try:
        data = resp.json()
    except Exception:
        return None

    task_id = str(data.get("task_id") or "").strip()
    tool_meta = data.get("tool_meta") or {}
    if not task_id or not isinstance(tool_meta, dict):
        return None
    return DispatchTask(task_id=task_id, tool_meta=tool_meta)


def report_result(
    report_url: str,
    payload: Dict[str, Any],
    timeout: int = 30,
) -> bool:
    """
    上报接口：POST /api/v1/report
    """
    try:
        resp = requests.post(
            report_url,
            headers={"accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        return resp.status_code in (200, 201, 204)
    except Exception as e:
        print(f"[report] ERROR: {e}")
        return False


