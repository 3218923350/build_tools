from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .models import ToolSpec


@dataclass(frozen=True)
class ToolSource:
    json_path: Path
    tool_id: Optional[int]
    raw_metadata: Dict[str, Any]
    raw_tool: Dict[str, Any]


def _coalesce_str(*values: object) -> str:
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _first_str_from_list(value: object) -> str:
    if isinstance(value, list):
        for x in value:
            if isinstance(x, str) and x.strip():
                return x.strip()
    return ""


def iter_tool_json_files(tools_root: Path) -> Iterable[Path]:
    if not tools_root.exists():
        return []
    # 只扫描一层子目录：tools/<subdir>/*.json
    for sub in sorted([p for p in tools_root.iterdir() if p.is_dir()]):
        for jp in sorted(sub.glob("*.json")):
            if jp.is_file():
                yield jp


def load_tools_from_tools_dir(tools_root: Path) -> List[Tuple[ToolSpec, ToolSource]]:
    """
    从 tools 目录下每个子目录中的 json 文件读取工具列表：
    - tools/<subdir>/*.json
    - 每个 json 文件内有 "metadata" 和 "tools" 字段
    """
    results: List[Tuple[ToolSpec, ToolSource]] = []
    for json_path in iter_tool_json_files(tools_root):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:
            print(f"[load_tools] WARN: 读取失败 {json_path}: {e}")
            continue

        metadata = data.get("metadata") or {}
        leaf = metadata.get("leaf_cluster") or {}
        unit = metadata.get("unit") or {}

        topic = _coalesce_str(
            f"{_coalesce_str(leaf.get('leaf_cluster_id'))} {_coalesce_str(leaf.get('leaf_cluster_name'))}".strip(),
            leaf.get("leaf_cluster_name"),
            leaf.get("leaf_cluster_id"),
        )
        category = _coalesce_str(
            f"{_coalesce_str(unit.get('unit_id'))} {_coalesce_str(unit.get('unit_name'))}".strip(),
            unit.get("unit_name"),
            unit.get("unit_id"),
        )

        tools = data.get("tools") or []
        if not isinstance(tools, list):
            continue

        for t in tools:
            if not isinstance(t, dict):
                continue
            name = _coalesce_str(t.get("name"))
            repo_url = _coalesce_str(t.get("repo_url"), t.get("repo"), t.get("homepage"))
            if not name or not repo_url:
                continue

            help_website = t.get("help_website")
            docs_url = _coalesce_str(_first_str_from_list(help_website), t.get("docs_url"))

            tool = ToolSpec(
                topic=topic,
                category=category,
                name=name,
                version="",  # 原 JSON 不提供版本号；保持空字符串
                homepage=repo_url,
                docs_url=docs_url,
                external_dep="",
            )
            source = ToolSource(
                json_path=json_path,
                tool_id=t.get("id") if isinstance(t.get("id"), int) else None,
                raw_metadata=metadata if isinstance(metadata, dict) else {},
                raw_tool=t,
            )
            results.append((tool, source))

    return results


