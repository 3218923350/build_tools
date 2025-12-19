from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests


def _parse_github_repo(repo_url: str) -> Optional[Tuple[str, str]]:
    """
    解析 GitHub 仓库 URL -> (owner, repo)
    支持：
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    """
    if not repo_url:
        return None
    u = repo_url.strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/#?]+)", u)
    if m:
        owner, repo = m.group(1), m.group(2)
    else:
        m = re.match(r"^git@github\.com:([^/]+)/([^/#?]+)", u)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2)
    repo = repo[:-4] if repo.endswith(".git") else repo
    return owner, repo


@dataclass(frozen=True)
class GithubRepoInfo:
    avatar_url: str = ""
    stars: Optional[int] = None
    forks: Optional[int] = None
    watchers: Optional[int] = None
    open_issues: Optional[int] = None
    primary_language: str = ""
    language_list: Dict[str, float] = None  # normalized
    license: str = ""
    last_commit_id: str = ""
    last_commit_date: str = ""
    version_tag: str = ""


def _gh_headers(token: str) -> Dict[str, str]:
    h = {
        "accept": "application/vnd.github+json",
        "user-agent": "build-agent",
    }
    if token:
        h["authorization"] = f"Bearer {token}"
    return h


def fetch_github_repo_info(
    repo_url: str,
    token: str = "",
    api_base: str = "https://api.github.com",
    timeout: int = 20,
) -> Optional[GithubRepoInfo]:
    """
    通过 GitHub REST API 补全仓库信息。失败返回 None（不阻断主流程）。
    """
    parsed = _parse_github_repo(repo_url)
    if not parsed:
        return None
    owner, repo = parsed
    base = api_base.rstrip("/")
    headers = _gh_headers(token)

    def get_json(path: str, max_retries: int = 40) -> Optional[Dict[str, Any]]:
        """GitHub API 请求（400台机器并发场景：40次重试，每次随机1-30秒）"""
        last_err = None
        for i in range(max_retries):
            try:
                r = requests.get(f"{base}{path}", headers=headers, timeout=timeout)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 404:
                    # 404 不需要重试
                    return None
                else:
                    last_err = f"HTTP {r.status_code}"
            except Exception as e:
                last_err = str(e)
            
            if i < max_retries - 1:
                sleep_sec = random.uniform(1, 30)
                print(f"[github_api] Retry {i+1}/{max_retries} for {path}: {last_err}, sleep {sleep_sec:.1f}s")
                time.sleep(sleep_sec)
            else:
                print(f"[github_api] All {max_retries} retries exhausted for {path}: {last_err}")
        return None

    repo_j = get_json(f"/repos/{owner}/{repo}")
    if not repo_j:
        return None

    avatar_url = (repo_j.get("owner") or {}).get("avatar_url") or ""
    stars = repo_j.get("stargazers_count")
    forks = repo_j.get("forks_count")
    # subscribers_count 是“watchers/subscribers”；watchers_count 在 GitHub 中常等同 stars
    watchers = repo_j.get("subscribers_count")
    open_issues = repo_j.get("open_issues_count")

    lic = (repo_j.get("license") or {}).get("spdx_id") or ""
    if lic == "NOASSERTION":
        lic = ""
    default_branch = repo_j.get("default_branch") or "main"

    languages_j = get_json(f"/repos/{owner}/{repo}/languages") or {}
    language_list: Dict[str, float] = {}
    if isinstance(languages_j, dict) and languages_j:
        total = sum(int(v) for v in languages_j.values() if isinstance(v, (int, float)))
        if total > 0:
            for k, v in languages_j.items():
                if isinstance(v, (int, float)):
                    language_list[str(k)] = float(v) / float(total)

    primary_language = repo_j.get("language") or ""
    if not primary_language and language_list:
        primary_language = max(language_list.items(), key=lambda kv: kv[1])[0]

    # last commit: /commits/{default_branch}
    last_commit_id = ""
    last_commit_date = ""
    c = get_json(f"/repos/{owner}/{repo}/commits/{default_branch}")
    if c:
        last_commit_id = c.get("sha") or ""
        last_commit_date = ((c.get("commit") or {}).get("committer") or {}).get("date") or ""

    # version tag: releases/latest -> tag_name，若无 release 再 tags?per_page=1
    version_tag = ""
    rel = get_json(f"/repos/{owner}/{repo}/releases/latest")
    if rel and isinstance(rel.get("tag_name"), str):
        version_tag = rel.get("tag_name") or ""
    if not version_tag:
        tags = None
        for i in range(40):  # 40次重试
            try:
                r = requests.get(f"{base}/repos/{owner}/{repo}/tags?per_page=1", headers=headers, timeout=timeout)
                if r.status_code == 200:
                    tags = r.json()
                    break
                elif r.status_code == 404:
                    break
            except Exception as e:
                if i < 39:
                    sleep_sec = random.uniform(1, 30)
                    print(f"[github_api] Retry {i+1}/40 for tags: {e}, sleep {sleep_sec:.1f}s")
                    time.sleep(sleep_sec)
        if isinstance(tags, list) and tags:
            version_tag = str((tags[0] or {}).get("name") or "")

    return GithubRepoInfo(
        avatar_url=str(avatar_url or ""),
        stars=int(stars) if isinstance(stars, int) else None,
        forks=int(forks) if isinstance(forks, int) else None,
        watchers=int(watchers) if isinstance(watchers, int) else None,
        open_issues=int(open_issues) if isinstance(open_issues, int) else None,
        primary_language=str(primary_language or ""),
        language_list=language_list,
        license=str(lic or ""),
        last_commit_id=str(last_commit_id or ""),
        last_commit_date=str(last_commit_date or ""),
        version_tag=str(version_tag or ""),
    )


