from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from . import config
from .dockerfile_utils import sanitize_dockerfile
from .llm import build_docker_plan_with_two_models
from .loaders import ToolSource
from .models import AttemptLog, ToolSpec
from .repo_context import collect_repo_context
from .utils import ensure_dir, is_git_repo, run_cmd, slugify
from .web import collect_docs_context


def _unique_urls(urls: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for u in urls:
        u = (u or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _write_success_artifact(
    tool: ToolSpec,
    source: Optional[ToolSource],
    dockerfile_text: str,
    used_links: List[str],
) -> Path:
    """
    成功后输出一个“单工具 JSON”，结构参考 tools/*/*.json：
    - generated_at
    - metadata（来自原始 json 的 metadata）
    - tools: [ 原 tool 条目 + dockerfile + helpurl/help_website(使用的链接) ]
    """
    success_dir = Path("success_tools").absolute()
    ensure_dir(success_dir)

    tool_slug = slugify(tool.name)
    out_path = success_dir / f"{tool_slug}.json"

    raw_metadata = source.raw_metadata if source else {}
    raw_tool = dict(source.raw_tool) if (source and isinstance(source.raw_tool, dict)) else {}
    if not raw_tool:
        raw_tool = {
            "name": tool.name,
            "repo_url": tool.homepage,
            "help_website": [],
        }

    used_links = _unique_urls(used_links)
    raw_tool["dockerfile"] = dockerfile_text
    raw_tool["helpurl"] = used_links
    raw_tool["help_website"] = used_links

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "metadata": raw_metadata,
        "tools": [raw_tool],
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def build_image_for_tool(
    tool: ToolSpec,
    source: Optional[ToolSource] = None,
    source_note: str = "",
) -> Optional[str]:
    """
    为单个工具构建镜像。
    返回成功镜像 tag；失败则返回 None。
    """
    tool_slug = slugify(tool.name)
    work_dir = config.BASE_WORK_DIR / tool_slug
    repo_dir = work_dir / "repo"
    ensure_dir(work_dir)
    ensure_dir(repo_dir)

    log_md_path = config.LOG_DIR / f"{tool_slug}.md"
    history: List[AttemptLog] = []

    def append_md(text: str):
        with log_md_path.open("a", encoding="utf-8") as f:
            f.write(text + "\n")

    # 初始化 md
    if not log_md_path.exists():
        with log_md_path.open("w", encoding="utf-8") as f:
            f.write(f"# Tool: {tool.name}\n\n")
            f.write(f"- Version: {tool.version}\n")
            f.write(f"- Homepage: {tool.homepage}\n")
            f.write(f"- Docs: {tool.docs_url}\n")
            if source_note:
                f.write(f"- Source: {source_note}\n")
            f.write("\n")

    append_md(f"---\n\n## 开始构建（{time.strftime('%Y-%m-%d %H:%M:%S')}）\n")

    # 克隆或更新仓库
    repo_clone_success = False
    repo_ctx: Dict[str, str] = {}

    if is_git_repo(tool.homepage):
        # 如果是 Git 仓库地址，尝试克隆
        if repo_dir.exists() and (repo_dir / ".git").exists():
            append_md("### 更新仓库\n")
            code, out, err = run_cmd(["git", "pull"], cwd=repo_dir)
            append_md("```text\n" + out + err + "\n```\n")
            repo_clone_success = code == 0
        else:
            if repo_dir.exists():
                shutil.rmtree(repo_dir)
            ensure_dir(repo_dir.parent)
            append_md("### 克隆仓库\n")
            code, out, err = run_cmd(["git", "clone", tool.homepage, str(repo_dir)], cwd=repo_dir.parent)
            append_md("```text\n" + out + err + "\n```\n")
            repo_clone_success = code == 0

        if repo_clone_success:
            # 收集仓库上下文
            append_md("### 分析仓库与文档（静态收集）\n")
            repo_ctx = collect_repo_context(repo_dir)
        else:
            append_md(f"**WARN**: git clone 失败，退出码 {code}，将把 homepage 作为文档链接进行分析。\n")
    else:
        append_md("### 仓库地址检查\n")
        append_md(f"**INFO**: homepage (`{tool.homepage}`) 不是 Git 仓库地址，将作为文档链接进行分析。\n")

    # 收集文档上下文
    docs_ctx = collect_docs_context(tool.docs_url, tool.name)

    # 如果仓库克隆失败或不是 Git 仓库，将 homepage 也作为文档链接
    if not repo_clone_success:
        append_md("### 将 homepage 作为文档链接分析\n")
        homepage_docs = collect_docs_context(tool.homepage, tool.name)
        docs_ctx.update(homepage_docs)
        append_md(f"**已添加 homepage 到文档上下文**: `{tool.homepage}`\n")

    append_md("**仓库文件摘要（部分路径）**:\n")
    append_md("```text\n" + "\n".join(list(repo_ctx.keys())[:15]) + "\n```\n")
    append_md("**文档页面地址（部分）**:\n")
    append_md("```text\n" + "\n".join(list(docs_ctx.keys())[:15]) + "\n```\n")
    append_md("### 文档抓取链接（docs_ctx 全量）\n")
    if docs_ctx:
        for u in _unique_urls(list(docs_ctx.keys())):
            append_md(f"- {u}")
    else:
        append_md("- （无）")
    append_md("")
    # 生成时间戳作为镜像 tag（格式：YYYYMMDDHHMMSS）
    timestamp = time.strftime("%Y%m%d%H%M%S")
    image_tag = f"registry.dp.tech/dptech/davinci/{tool_slug}:{timestamp}"
    build_attempt_index = 0  # 已经使用了多少次"写 Dockerfile + build"的机会

    while build_attempt_index < config.MAX_BUILD_ATTEMPTS:
        attempts_left = config.MAX_BUILD_ATTEMPTS - build_attempt_index
        append_md(f"\n---\n\n## 构建尝试 #{build_attempt_index + 1}（剩余写 Dockerfile 机会：{attempts_left}）\n")

        # 1. 双模型协同生成 Docker 方案
        try:
            plan = build_docker_plan_with_two_models(tool, repo_ctx, docs_ctx, history, attempts_left)
        except Exception as e:
            append_md(f"**ERROR**: LLM 分析失败：{e}\n")
            break

        append_md(f"**提案模型**: {plan.proposer_model}, **评审模型**: {plan.reviewer_model}\n")
        append_md(f"**plan.can_build**: {plan.can_build}, **confidence**: {plan.confidence:.3f}\n")

        append_md("### 综合分析说明\n")
        append_md("```text\n" + plan.rationale + "\n```\n")

        append_md("### 引用链接\n")
        if plan.citations:
            for c in plan.citations:
                url = c.get("url", "")
                note = c.get("note", "")
                append_md(f"- {url}  — {note}")
        else:
            append_md("- （无显式引用）")
        append_md("")
        used_links = _unique_urls(
            [c.get("url", "") for c in (plan.citations or [])] + ([tool.docs_url] if tool.docs_url else [])
        )
        append_md("### 本轮使用的链接（去重）\n")
        if used_links:
            for u in used_links:
                append_md(f"- {u}")
        else:
            append_md("- （无）")
        append_md("")

        if not plan.can_build and build_attempt_index > 8:
            append_md(
                "**判定**：经过多轮辩论后，两个模型尚未同时认为可以构建 Dockerfile，本轮不进入构建阶段，该工具暂时被放弃。\n"
            )
            break

        if plan.confidence < 0.7 and build_attempt_index > 8:
            append_md(
                f"**判定**：两个模型最终都认为可以构建，但综合置信度 {plan.confidence:.3f} < 0.7，"
                f"按照策略，本轮不实际执行 docker build（不消耗构建机会）。该工具留待人工或后续策略处理。\n"
            )
            break

        # 到这里说明两个模型认为可以尝试写 Dockerfile，这次构建机会将被消耗
        build_attempt_index += 1

        dockerfile_raw = plan.dockerfile or ""
        dockerfile_sanitized = sanitize_dockerfile(dockerfile_raw, tool.name)

        append_md("### 本轮 Dockerfile（原始）\n")
        append_md("```dockerfile\n" + dockerfile_raw + "\n```\n")

        append_md("### 本轮 Dockerfile（sanitize 后实际使用）\n")
        append_md("```dockerfile\n" + dockerfile_sanitized + "\n```\n")

        (work_dir / "Dockerfile").write_text(dockerfile_sanitized, encoding="utf-8")

        # 2. docker build
        append_md("### docker build 日志\n")
        code, out, err = run_cmd(
            ["docker", "build", "-t", image_tag, "."],
            cwd=work_dir,
            timeout=config.BUILD_TIMEOUT,
        )
        build_log = out + "\n" + err
        append_md("```text\n" + build_log + "\n```\n")
        build_succeeded = code == 0

        if not build_succeeded:
            append_md(f"**本轮结果**：docker build 失败（退出码 {code}），构建机会已消耗 1 次，将根据日志进行下一轮分析。\n")
            history.append(
                AttemptLog(
                    attempt_index=build_attempt_index,
                    proposer_model=plan.proposer_model,
                    reviewer_model=plan.reviewer_model,
                    analysis_summary=plan.rationale,
                    dockerfile=dockerfile_sanitized,
                    verify_commands=plan.verify_commands,
                    build_succeeded=False,
                    build_log=build_log,
                    run_succeeded=False,
                    run_log="",
                    plan_confidence=plan.confidence,
                    can_build=plan.can_build,
                    citations=plan.citations,
                )
            )
            continue

        # 3. docker run 验证
        append_md("### docker run 验证命令\n")
        verify_commands = plan.verify_commands or []
        if not verify_commands:
            verify_commands = ["echo 'No specific verify command provided'"]

        append_md("将依次执行：\n")
        for cmd in verify_commands:
            append_md(f"- `{cmd}`")
        append_md("")

        run_succeeded = True
        run_log_total = ""
        for cmd in verify_commands:
            append_md(f"#### 运行：`{cmd}`\n")
            docker_cmd = ["docker", "run", "--rm", image_tag, "bash", "-lc", cmd]
            code, out, err = run_cmd(docker_cmd, timeout=config.RUN_TIMEOUT)
            log = f"$ {' '.join(docker_cmd)}\n\n" + out + "\n" + err
            run_log_total += "\n\n" + log
            append_md("```text\n" + log + "\n```\n")
            if code != 0:
                append_md(f"**该验证命令失败，退出码 {code}**\n")
                run_succeeded = False
                break

        history.append(
            AttemptLog(
                attempt_index=build_attempt_index,
                proposer_model=plan.proposer_model,
                reviewer_model=plan.reviewer_model,
                analysis_summary=plan.rationale,
                dockerfile=dockerfile_sanitized,
                verify_commands=verify_commands,
                build_succeeded=build_succeeded,
                build_log=build_log,
                run_succeeded=run_succeeded,
                run_log=run_log_total,
                plan_confidence=plan.confidence,
                can_build=plan.can_build,
                citations=plan.citations,
            )
        )

        if run_succeeded:
            append_md("## ✅ 构建 & 验证成功\n")
            append_md(f"- 镜像标签：`{image_tag}`\n")
            append_md("- 最终验证命令：\n")
            for cmd in verify_commands:
                append_md(f"  - `{cmd}`")
            append_md("\n构建流程结束。\n")
            out_path = _write_success_artifact(
                tool=tool,
                source=source,
                dockerfile_text=dockerfile_sanitized,
                used_links=used_links,
            )
            append_md("\n### 成功产物（单工具 JSON）\n")
            append_md(f"- `{out_path}`\n")
            
            append_md(f"\n---\n\n## 结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            return image_tag
        else:
            append_md("**本轮结果**：镜像构建成功，但验证命令失败，构建机会已消耗 1 次，将结合日志进行下一轮分析。\n")

    append_md(f"\n在消耗了 {config.MAX_BUILD_ATTEMPTS} 次 Dockerfile 构建机会后仍未成功，按照规则，该工具暂时被放弃。\n")
    append_md(f"\n---\n\n## 结束时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    return None


