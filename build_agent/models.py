from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ToolSpec:
    topic: str
    category: str
    name: str
    version: str
    homepage: str  # Git 仓库地址（优先 GitHub/GitLab）
    docs_url: str
    external_dep: str = ""


@dataclass
class DockerPlan:
    can_build: bool
    confidence: float
    dockerfile: str
    verify_commands: List[str]
    rationale: str
    citations: List[Dict[str, str]] = field(default_factory=list)
    proposer_model: str = ""
    reviewer_model: str = ""


@dataclass
class AttemptLog:
    attempt_index: int
    proposer_model: str
    reviewer_model: str
    analysis_summary: str
    dockerfile: str
    verify_commands: List[str]
    build_succeeded: bool
    build_log: str
    run_succeeded: bool
    run_log: str
    plan_confidence: float
    can_build: bool
    citations: List[Dict[str, str]]


