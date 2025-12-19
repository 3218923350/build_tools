from __future__ import annotations

import dataclasses
import json
import random
import re
import textwrap
import time
from typing import Dict, List, Optional

from openai import OpenAI

from .config import GEMINI_MODEL, OPENAI_MODEL, REQUIRED_SSH_MCP_SNIPPET, gemini_client, gpt_client
from .models import AttemptLog, DockerPlan, ToolSpec
from .utils import log_summary_text, summarize_text
from .web import fetch_citation_contents


def call_llm_json(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_retries: int = 40,
) -> dict:
    """调用 LLM 并解析 JSON（400台机器并发场景：40次重试，每次随机1-30秒）"""
    last_err: Optional[Exception] = None
    temperature = 1.0 if model == OPENAI_MODEL else 0.1
    for i in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )
            content = resp.choices[0].message.content
            # 尝试抽取 JSON
            match = re.search(r"\{.*\}", content, re.S)
            json_text = match.group(0) if match else content
            data = json.loads(json_text)
            return data
        except Exception as e:
            last_err = e
            if i < max_retries - 1:
                sleep_sec = random.uniform(1, 30)
                print(f"[call_llm_json] Retry {i+1}/{max_retries} failed: {e}, sleep {sleep_sec:.1f}s")
                time.sleep(sleep_sec)
            else:
                print(f"[call_llm_json] All {max_retries} retries exhausted: {e}")
    raise RuntimeError(f"LLM 调用失败（已重试{max_retries}次）: {last_err}")


def build_docker_plan_with_two_models(
    tool: ToolSpec,
    repo_ctx: Dict[str, str],
    docs_ctx: Dict[str, str],
    previous_attempts: List[AttemptLog],
    attempts_left: int,
) -> DockerPlan:
    """
    双模型协同（多轮辩论版）：
    - 两个模型可以无限次“分析 / 打分 / 互怼”，这一部分不消耗 Dockerfile 构建机会。
    - 本函数只在“双方都认为可以 build”时返回一个 DockerPlan；
    - 返回后，外层再根据 plan.confidence >= 0.7 决定是否真的去 docker build（消耗一次机会）。
    """

    models = []
    if gemini_client:
        models.append(("gemini", gemini_client, GEMINI_MODEL))
    if gpt_client:
        models.append(("gpt5", gpt_client, OPENAI_MODEL))

    if not models:
        raise RuntimeError("没有可用的 LLM 模型（请检查 GEMINI_API_KEY / OPENAI_API_KEY）")

    # 固定 A/B，两者交替发言。为了随机性可以随机决定谁是 A。
    if len(models) == 1:
        model_A = model_B = models[0]
    else:
        model_A = random.choice(models)
        model_B = models[0] if models[1] == model_A else models[1]

    A_name, A_client, A_model = model_A
    B_name, B_client, B_model = model_B

    # 存放“所有引用链接的正文摘要”，供多轮来回用
    citation_contents: Dict[str, str] = {}
    # 上一轮 B 的评审结果，下一轮 A 会用
    last_review_from_B: Optional[dict] = None

    # 限制辩论轮数，防止真的死循环；评分逻辑本身可以认为“无限”，这里只是技术限制
    MAX_DEBATE_ROUNDS = 10

    best_plan: Optional[DockerPlan] = None
    best_confidence: float = 0.0
    all_citations: List[Dict[str, str]] = []

    for round_idx in range(1, MAX_DEBATE_ROUNDS + 1):
        # ========== A 作为 proposer ==========
        system_prompt_proposer = textwrap.dedent(
            f"""
        你是资深 DevOps 工程师（模型：{A_name}），目标是为工具生成“最小可用”的 Dockerfile。

        非常重要的约束：
        - 整个系统总共有 **10 次** 写 Dockerfile 的机会（包括本次），每写一次 Dockerfile 就会消耗一次机会。
        - 你当前调用时的剩余机会次数为：{attempts_left}。
        - 在这 10 次机会之外，你和另一个 AI 可以进行 **无限次分析和打分**，
          但每次真正输出 Dockerfile 并进入实际构建阶段，都会消耗一次机会。
        - 只有当你和另一模型都认为“可以构建”时，你们才会把方案交给外层；
          外层会根据最终置信度（>=0.7 与否）决定是否真的去 docker build。

        你的任务（这是第 {round_idx} 轮讨论）：
        1. 根据提供的仓库内容（README / .md / 构建文件）、文档页面（包括 install/linux/ubuntu 等）、
           历史尝试（失败日志、之前的 Dockerfile 摘要）、引用链接正文（citation_contents）进行彻底分析。
        2. 给出一个布尔值 can_build：
           - true ：你认为在当前信息下已经做了足够深入的分析，写出的 Dockerfile 成功概率很高。
           - false：你认为当前信息下还不能有把握写出正确 Dockerfile。
        3. 给出一个 0.0~1.0 的 confidence（你自己对 can_build=true 之后构建成功的置信度）。
        4. 当 can_build=true 时：
           - 写出“最小可行”的 Dockerfile，
             但是必须要安装 python、pip、wget、curl 等命令——可以通过发行版的包管理器安装）。
           - 不要设置限制性的 CMD/ENTRYPOINT（如 CMD ["python"], CMD ["julia"], CMD ["{tool.name.lower()}"] 等）。
           - 优先使用官方文档中给出的安装命令，比如有些工具可以直接 pip install XXX，不要臆想依赖。
           - 只安装该工具所需的依赖。
           - 如果需要源码：
             * 在 Dockerfile 中显式通过 `git clone {tool.homepage}` 获取源码后再编译安装；
               或者使用 `wget` / `curl` 下载源码压缩包，然后用 `tar` 解压再编译安装。
             * 不要假设源码已经存在于镜像中，一切源码获取动作都应该写进 Dockerfile 的 RUN 步骤中。
           - 给出 1~3 个“验证命令”，用于验证该工具是否安装成功，例如：
             - 命令行工具：`which xxx`、`xxx --version`、`xxx -h`
             - Python 库：`python -c "import xxx; print(xxx.__version__)"` 等。
        4.1 **硬性要求（必须满足，否则将 can_build=false）**：
           - Dockerfile 必须安装并启用 SSH 能力所需包：`openssh-server`，并包含 `supervisor` 与 `net-tools`（用于守护 sshd 与排障）。
           - Dockerfile 必须包含 `pip install mcp`（MCP 客户端）。
           - Dockerfile 必须安装 `numpy`（例如 `pip install numpy`），作为运行时基础包（强制要求）。
           - 上述要求请直接体现在你输出的 Dockerfile 中，而不是依赖外部脚本“事后补丁”。
        4.2 参考实现（强烈建议直接复用或等价实现）：
           - 下方片段来自系统配置 `REQUIRED_SSH_MCP_SNIPPET`，代表“期望的 SSH/MCP 配置方式”。
           - 你输出的 Dockerfile 应当 **显式包含** 这段内容或等价内容（包安装 + supervisord 配置 + sshd 配置 + pip install mcp + pip install numpy）：

           ===== BEGIN REQUIRED_SSH_MCP_SNIPPET =====
{textwrap.indent(REQUIRED_SSH_MCP_SNIPPET.rstrip(), "           ")}
           ===== END REQUIRED_SSH_MCP_SNIPPET =====

        5. 所有关键决策必须给出 citations（引用链接）：
           - 例如：从哪个文档 URL、哪篇安装教程中推断出哪条安装命令。
           - 每条 citation 结构为：{{"url": "...", "note": "说明你从该链接学到了什么"}}
        6. 你会看到 previous_attempts_summary，其中包括：
            - 每一轮的 dockerfile 摘要
            - build_log_excerpt（构建日志片段）
            - run_log_excerpt（运行/验证日志片段）
            请特别关注其中诸如 "pip: not found"、"command not found"、"No module named ..." 等关键信息，
            并据此补充缺失的依赖（例如安装 python3-pip、wget、curl、缺失的动态库或开发头文件等），
            不要重复犯同样的错误。
        7. 你还会看到上一轮来自另一模型的评审反馈（如果有），以及 citation_contents 中根据你们给出的 URL 拉取的网页正文摘要，
           请核对：对方在理由中引用的链接内容是否真的支持 ta 的说法。

        强调：
        - 如果你完全没有把握，请设置 can_build=false，并解释原因。
        - 但是在前几次构建中，可以在有一定依据的前提下尝试构建，不要因为“害怕失败”就永远不愿意给出方案。

        输出 JSON，结构必须为：
        {{
          "can_build": true/false,
          "confidence": 0.0~1.0,
          "dockerfile": "完整 Dockerfile（当 can_build=false 时可以是空字符串）",
          "verify_commands": ["cmd1", "cmd2", ...],
          "rationale": "详细理由，说明你如何从文档/代码中推导安装步骤，以及为什么这次你觉得有把握。",
          "citations": [
            {{"url": "...", "note": "..."}},
            ...
          ]
        }}
        """
        ).strip()

        proposer_payload = {
            "tool": dataclasses.asdict(tool),
            "repo_context_excerpt": repo_ctx,
            "docs_context_excerpt": docs_ctx,
            "previous_attempts_summary": [
                {
                    "attempt_index": a.attempt_index,
                    "build_succeeded": a.build_succeeded,
                    "run_succeeded": a.run_succeeded,
                    "plan_confidence": a.plan_confidence,
                    "can_build": a.can_build,
                    "analysis_summary": summarize_text(a.analysis_summary, 4000),
                    "dockerfile_excerpt": summarize_text(a.dockerfile, 4000),
                    "build_log_excerpt": log_summary_text(a.build_log, 1000),
                    "run_log_excerpt": log_summary_text(a.run_log, 1000),
                }
                for a in previous_attempts
            ],
            "citation_contents": citation_contents,
            "last_review_from_other_model": last_review_from_B,
            "debate_round": round_idx,
        }
        user_prompt_proposer = json.dumps(proposer_payload, ensure_ascii=False, indent=2)

        proposer_result = call_llm_json(A_client, A_model, system_prompt_proposer, user_prompt_proposer)

        # 解析 proposer 结果
        proposer_can_build = bool(proposer_result.get("can_build", False))
        proposer_conf = float(proposer_result.get("confidence", 0.0))
        proposer_dockerfile = str(proposer_result.get("dockerfile", ""))
        proposer_verify_cmds = list(proposer_result.get("verify_commands", []))
        proposer_rationale = str(proposer_result.get("rationale", ""))
        proposer_citations = list(proposer_result.get("citations", []))

        # 把 proposer 的 citations 中的 URL 抓取正文
        urls_from_A = [c.get("url", "") for c in proposer_citations]
        citation_contents = fetch_citation_contents(urls_from_A, citation_contents)

        all_citations.extend(proposer_citations)

        # ========== B 作为 reviewer ==========
        system_prompt_reviewer = textwrap.dedent(
            f"""
        你是另一个独立的 DevOps 审核 AI（模型：{B_name}），需要对另一个 AI 提供的 Dockerfile 方案进行严格审查。

        非常重要的全局约束（与对方 AI 共享）：
        - 整个系统最多只能写（并构建） **10 个 Dockerfile**。
        - 当前剩余构建机会次数：{attempts_left}。
        - 分析/评分/思考可以无限次，但是每当你们选择“同意编写并构建一个 Dockerfile”，就会消耗一次机会。
        - 只有当你和对方都认为“可以构建”时，你们才会把方案交给外层；
          外层会根据最终置信度（>=0.7）决定是否真的去 docker build。

        你的任务（这是第 {round_idx} 轮讨论）：
        1. 你会看到：
           - 仓库文件摘要
           - 文档页面摘要
           - 之前若干次尝试摘要与失败日志（含 build_log_excerpt / run_log_excerpt）
           - 对方当前给出的 plan（can_build/confidence/dockerfile/verify_commands/citations）
           - citation_contents：根据你们给出的 URL 抓取到的网页正文摘要
        2. 请特别检查：
           - Dockerfile 是否遵循官方安装文档（可以对照 citation_contents 中的正文）。
           - 是否缺少明显依赖（结合 previous_attempts 的错误日志，例如 "pip: not found" 等）。
           - 是否存在限制性 CMD/ENTRYPOINT。
           - **硬性要求是否满足**：`openssh-server` + `supervisor` + `net-tools`；包含 `pip install mcp`；包含 `numpy` 安装（例如 `pip install numpy`）。
           - **参考实现是否已满足**：提案是否包含（或等价实现）以下片段（REQUIRED_SSH_MCP_SNIPPET）：

           ===== BEGIN REQUIRED_SSH_MCP_SNIPPET =====
{textwrap.indent(REQUIRED_SSH_MCP_SNIPPET.rstrip(), "           ")}
           ===== END REQUIRED_SSH_MCP_SNIPPET =====
        3. 输出 JSON，结构必须为：
           {{
             "accept": true/false,
             "review_confidence": 0.0~1.0,
             "final_can_build": true/false,
             "final_confidence": 0.0~1.0,
             "final_dockerfile": "当你决定可以尝试构建时，给出你认可的完整 Dockerfile；如果你只在细节上修正，请给出修订后的完整 Dockerfile；当 final_can_build=false 时可以为空字符串。",
             "final_verify_commands": ["cmd1", "cmd2", ...],
             "critique": "你对提案的详细评价，指出问题和风险，并说明为什么接受或拒绝。",
             "citations": [
               {{"url": "...", "note": "..."}},
               ...
             ]
           }}

        评审标准建议：
        - 当以下情况时，你应该让 final_can_build=false：
          - 官方/社区安装文档不清晰或版本不匹配。
          - 编译链、依赖版本互相冲突，无法保证可用。
          - 提案严重违背官方推荐流程，且没有充分证据支持。
        - 当你认为“在当前信息下确实已经很清楚如何安装”时，才设置 final_can_build=true，
          并给出 final_confidence（你自己的置信度）。
        - 你的输出将作为下一轮对方分析的输入，请尽量指出具体可改进的地方（例如缺少 python3-pip、缺少 libxxx-dev、错误的包名等）。
        - 如果提案没有满足上述“硬性要求”，你应当让 final_can_build=false，或在 final_dockerfile 中补齐并说明原因。
        """
        ).strip()

        reviewer_input = {
            "tool": dataclasses.asdict(tool),
            "repo_context_excerpt": repo_ctx,
            "docs_context_excerpt": docs_ctx,
            "previous_attempts_summary": [
                {
                    "attempt_index": a.attempt_index,
                    "build_succeeded": a.build_succeeded,
                    "run_succeeded": a.run_succeeded,
                    "plan_confidence": a.plan_confidence,
                    "can_build": a.can_build,
                    "analysis_summary": summarize_text(a.analysis_summary, 4000),
                    "dockerfile_excerpt": summarize_text(a.dockerfile, 4000),
                    "build_log_excerpt": log_summary_text(a.build_log, 1000),
                    "run_log_excerpt": log_summary_text(a.run_log, 1000),
                }
                for a in previous_attempts
            ],
            "proposal_from_other_model": {
                "model_name": A_name,
                "raw_plan": proposer_result,
            },
            "citation_contents": citation_contents,
            "debate_round": round_idx,
        }
        user_prompt_reviewer = json.dumps(reviewer_input, ensure_ascii=False, indent=2)

        reviewer_result = call_llm_json(B_client, B_model, system_prompt_reviewer, user_prompt_reviewer)

        last_review_from_B = reviewer_result  # 给下一轮 A 使用

        final_can_build = bool(reviewer_result.get("final_can_build", False))
        review_conf = float(reviewer_result.get("review_confidence", 0.0))
        final_conf = float(reviewer_result.get("final_confidence", 0.0))
        final_dockerfile = str(reviewer_result.get("final_dockerfile", proposer_dockerfile))
        final_verify_commands = list(reviewer_result.get("final_verify_commands", proposer_verify_cmds))
        critique = str(reviewer_result.get("critique", ""))
        reviewer_citations = list(reviewer_result.get("citations", []))

        urls_from_B = [c.get("url", "") for c in reviewer_citations]
        citation_contents = fetch_citation_contents(urls_from_B, citation_contents)
        all_citations.extend(reviewer_citations)

        # 综合置信度（但此处不做阈值判断，让外层来决定是否 build）
        combined_confidence = max(0.0, min(1.0, (proposer_conf + final_conf + review_conf) / 3.0))

        combined_rationale = (
            f"=== Round {round_idx} Proposer ({A_name}) rationale ===\n"
            + proposer_rationale
            + f"\n\n=== Round {round_idx} Reviewer ({B_name}) critique ===\n"
            + critique
        )

        # 记录最好的一次方案（即使最后没形成“双方都同意”的共识，也可以作为参考）
        if combined_confidence > best_confidence:
            best_confidence = combined_confidence
            best_plan = DockerPlan(
                can_build=proposer_can_build and final_can_build,
                confidence=combined_confidence,
                dockerfile=final_dockerfile,
                verify_commands=final_verify_commands,
                rationale=combined_rationale,
                citations=all_citations.copy(),
                proposer_model=A_name,
                reviewer_model=B_name,
            )

        # 双方都认为可以 build，则直接认为辩论收敛，返回该方案
        if proposer_can_build and final_can_build:
            return DockerPlan(
                can_build=True,
                confidence=combined_confidence,
                dockerfile=final_dockerfile,
                verify_commands=final_verify_commands,
                rationale=combined_rationale,
                citations=all_citations,
                proposer_model=A_name,
                reviewer_model=B_name,
            )

        # 否则轮换 A/B 角色，下一轮进攻方换成另外一个模型
        model_A, model_B = model_B, model_A
        A_name, A_client, A_model = model_A
        B_name, B_client, B_model = model_B

    # 多轮辩论后仍未达到“双方都认为可以 build”的情况：
    # 返回 best_plan（如果有），但 can_build 只在双方都同意时为 True，这里保持 False。
    if best_plan is not None:
        best_plan.can_build = False  # 双方未达成一致 => 不允许真正构建
        return best_plan

    # 完全没有合理方案
    return DockerPlan(
        can_build=False,
        confidence=0.0,
        dockerfile="",
        verify_commands=[],
        rationale="多轮辩论后，两个模型均未能形成共同认可的 Dockerfile 方案。",
        citations=all_citations,
        proposer_model=A_name,
        reviewer_model=B_name,
    )


