from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip())
    s = s.strip("-").lower()
    return s or "tool"


def is_gitlab_repo(url: str) -> bool:
    """判断仓库是否为 GitLab（包括自建 gitlab 实例）"""
    if not url:
        return False
    u = url.lower()
    return "gitlab" in u


def is_github_repo(url: str) -> bool:
    """判断仓库是否为 GitHub"""
    if not url:
        return False
    u = url.lower()
    return "github.com" in u or "github.io" in u


def is_git_repo(url: str) -> bool:
    """判断是否为 Git 仓库（GitHub、GitLab 或直接的 git:// 地址）"""
    if not url:
        return False
    u = url.lower()
    return is_github_repo(url) or is_gitlab_repo(url) or u.startswith("git://") or u.startswith("git@")


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def run_cmd(cmd: List[str], cwd: Optional[Path] = None, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """运行 shell 命令，返回 (exit_code, stdout, stderr)"""
    print(f"[CMD] {' '.join(cmd)} (cwd={cwd})")
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            return 124, stdout, stderr + "\n[ERROR] Command timeout"
        return proc.returncode, stdout, stderr
    except FileNotFoundError as e:
        return 127, "", f"[ERROR] {e}"


def summarize_text(text: str, max_chars: int = 4000) -> str:
    text = (text or "").strip()
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n...[TRUNCATED]..."
    return text


def log_summary_text(text: str, max_chars: int = 4000) -> str:
    text = (text or "").strip()
    if len(text) > max_chars:
        return "...[LOG_TRUNCATED]...\n" + text[-max_chars:]
    return text


