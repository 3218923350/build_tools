from __future__ import annotations

import argparse
import threading
from pathlib import Path
from typing import List, Tuple

from . import config
from .builder import build_image_for_tool
from .loaders import ToolSource, load_tools_from_tools_dir
from .models import ToolSpec


def worker_thread(tool: ToolSpec, source: ToolSource):
    try:
        note = f"{source.json_path}"
        if source.tool_id is not None:
            note += f" (id={source.tool_id})"
        build_image_for_tool(tool, source=source, source_note=note)
    except Exception as e:
        print(f"[worker] Tool {tool.name} failed with error: {e}")


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="自动构建工具 Docker 镜像（多工具并行，v2）")
    parser.add_argument(
        "--tools-root",
        default="tools",
        help="工具清单根目录（默认 tools/，扫描 tools/<子目录>/*.json）",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=config.MAX_PARALLEL_TOOLS,
        help=f"最大并行工具数（默认 {config.MAX_PARALLEL_TOOLS}）",
    )
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="只处理某一个工具名（完全匹配 name 字段）",
    )

    args = parser.parse_args(argv)

    tools_root = Path(args.tools_root)
    pairs: List[Tuple[ToolSpec, ToolSource]] = load_tools_from_tools_dir(tools_root)

    if args.only:
        pairs = [(t, s) for (t, s) in pairs if t.name == args.only]

    print(f"[INFO] 将处理 {len(pairs)} 个工具（最多并行 {args.max_parallel} 个）")

    threads: List[threading.Thread] = []
    sem = threading.Semaphore(args.max_parallel)

    for tool, source in pairs:
        sem.acquire()

        def start_tool(t: ToolSpec, s: ToolSource):
            try:
                worker_thread(t, s)
            finally:
                sem.release()

        th = threading.Thread(target=start_tool, args=(tool, source), daemon=True)
        th.start()
        threads.append(th)

    for th in threads:
        th.join()

    print("[INFO] 所有工具处理结束。")


if __name__ == "__main__":
    main()


