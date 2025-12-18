from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from .utils import summarize_text


def collect_repo_context(repo_dir: Path, max_files: int = 40, max_chars_per_file: int = 4000) -> Dict[str, str]:
    """
    收集仓库中的 README / 所有 .md / 若干构建文件的部分内容，
    为 LLM 提供上下文。
    """
    important_files: List[Path] = []

    # 优先 README / INSTALL
    patterns = [
        "README",
        "README.md",
        "README.rst",
        "INSTALL",
        "INSTALL.md",
        "INSTALL.rst",
    ]
    for pattern in patterns:
        for p in repo_dir.rglob(pattern):
            important_files.append(p)

    # 所有 .md 文件
    md_files = [p for p in repo_dir.rglob("*.md")]
    md_files = sorted(md_files, key=lambda p: len(str(p)))
    for p in md_files:
        if p not in important_files:
            important_files.append(p)

    # 构建相关文件
    build_patterns = ["setup.py", "pyproject.toml", "CMakeLists.txt", "Makefile", "configure", "environment.yml"]
    for pattern in build_patterns:
        for p in repo_dir.rglob(pattern):
            if p not in important_files:
                important_files.append(p)

    seen = set()
    final_files: List[Path] = []
    for p in important_files:
        if not p.is_file():
            continue
        k = str(p)
        if k in seen:
            continue
        seen.add(k)
        final_files.append(p)
        if len(final_files) >= max_files:
            break

    ctx: Dict[str, str] = {}
    for p in final_files:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            ctx[str(p.relative_to(repo_dir))] = summarize_text(content, max_chars_per_file)
        except Exception as e:
            print(f"[collect_repo_context] Error reading {p}: {e}")
    return ctx


