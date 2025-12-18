from __future__ import annotations

from .config import REQUIRED_SSH_MCP_SNIPPET


def sanitize_dockerfile(dockerfile_text: str, tool_name: str) -> str:
    """
    - 注释掉包含 python/julia/工具名 的 CMD/ENTRYPOINT（限制性）。
    - 若未包含 pip install mcp，则追加 SSH/MCP 段。
    """
    lines = (dockerfile_text or "").splitlines()
    new_lines = []
    tool_lower = (tool_name or "").lower()

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if lower.startswith("cmd") or lower.startswith("entrypoint"):
            # 判断是否限制性：包括 python/julia/工具名
            if any(k in lower for k in ["python", "julia", tool_lower] if k):
                new_lines.append("# " + line + "  # commented out: tool-specific CMD/ENTRYPOINT disabled")
                continue
        new_lines.append(line)

    text = "\n".join(new_lines).rstrip() + "\n"

    # 若没有 pip install mcp，则确保追加一次 SSH/MCP
    if "pip install mcp" not in text:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + REQUIRED_SSH_MCP_SNIPPET

    return text.strip() + "\n"


