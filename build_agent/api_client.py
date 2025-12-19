from __future__ import annotations

import random
import time
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
    max_retries: int = 40,
) -> Optional[DispatchTask]:
    """
    调度接口：POST /api/v1/dispatch（400台机器并发场景：40次重试，每次随机1-30秒）

    预期返回：
    {
      "task_id": "...",
      "tool_meta": {...}
    }

    当无任务时，可能返回非 200 或空 body；此处统一返回 None。
    """
    last_err = None
    for i in range(max_retries):
        try:
            resp = requests.post(
                dispatch_url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                json={"worker_ip": worker_ip},
                timeout=timeout,
            )
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    task_id = str(data.get("task_id") or "").strip()
                    tool_meta = data.get("tool_meta") or {}
                    if task_id and isinstance(tool_meta, dict):
                        return DispatchTask(task_id=task_id, tool_meta=tool_meta)
                    # 200 但无有效 task_id/tool_meta => 无任务，不重试
                    return None
                except Exception:
                    # JSON 解析失败，可能是服务端错误，需要重试
                    last_err = "JSON parse failed"
            elif resp.status_code in (204, 404):
                # 明确无任务，不重试
                return None
            else:
                last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)
        
        if i < max_retries - 1:
            sleep_sec = random.uniform(1, 30)
            print(f"[dispatch] Retry {i+1}/{max_retries}: {last_err}, sleep {sleep_sec:.1f}s")
            time.sleep(sleep_sec)
        else:
            print(f"[dispatch] All {max_retries} retries exhausted: {last_err}")
    
    return None


def report_result(
    report_url: str,
    payload: Dict[str, Any],
    timeout: int = 30,
    max_retries: int = 40,
) -> bool:
    """
    上报接口：POST /api/v1/report（400台机器并发场景：40次重试，每次随机1-30秒）
    """
    last_err = None
    for i in range(max_retries):
        try:
            resp = requests.post(
                report_url,
                headers={"accept": "application/json", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            if resp.status_code in (200, 201, 204):
                return True
            last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)
        
        if i < max_retries - 1:
            sleep_sec = random.uniform(1, 30)
            print(f"[report] Retry {i+1}/{max_retries}: {last_err}, sleep {sleep_sec:.1f}s")
            time.sleep(sleep_sec)
        else:
            print(f"[report] All {max_retries} retries exhausted: {last_err}")
    
    return False


