from __future__ import annotations

import random
import time
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from .config import SEARCH_BASE_URL, SEARCH_KEY
from .utils import summarize_text


def web_search(query: str, count: int = 5, timeout: int = 20, max_retries: int = 30) -> List[Dict[str, str]]:
    """基于 searchapi.io 的 websearch 封装（400台机器并发场景：40次重试，每次随机1-30秒）"""
    if not SEARCH_KEY:
        return []
    url = f"{SEARCH_BASE_URL}api/v1/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SEARCH_KEY,
        "num": min(count, 10),
    }
    last_err = None
    for i in range(max_retries):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                results = []
                for item in data.get("organic_results", [])[:count]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                        }
                    )
                return results
            else:
                last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)
        
        if i < max_retries - 1:
            sleep_sec = random.uniform(1, 30)
            print(f"[web_search] Retry {i+1}/{max_retries} for '{query}': {last_err}, sleep {sleep_sec:.1f}s")
            time.sleep(sleep_sec)
        else:
            print(f"[web_search] All {max_retries} retries exhausted for '{query}': {last_err}")
    
    return []


import re
import json
import requests
from urllib.parse import urlparse


# ---------- 通用工具 ----------
def _http_get(url: str, headers=None, params=None, timeout=20, max_retries: int = 2) -> requests.Response:
    """HTTP GET 请求（400台机器并发场景：40次重试，每次随机1-30秒）"""
    last_err = None
    for i in range(max_retries):
        try:
            resp = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
            )
            if resp.status_code == 200:
                return resp
            elif resp.status_code == 404:
                # 404 不需要重试
                return resp
            else:
                last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)
        
        if i < max_retries - 1:
            sleep_sec = random.uniform(1, 30)
            print(f"[_http_get] Retry {i+1}/{max_retries} for {url}: {last_err}, sleep {sleep_sec:.1f}s")
            time.sleep(sleep_sec)
        else:
            print(f"[_http_get] All {max_retries} retries exhausted for {url}: {last_err}")
            # 最后一次失败也返回响应（即使状态码不是200）
            try:
                return requests.get(url, headers=headers, params=params, timeout=timeout)
            except:
                raise RuntimeError(f"HTTP GET failed after {max_retries} retries: {last_err}")


def _extract_text_from_html(html: str) -> str:
    """
    极简 HTML → 文本
    （你后面大概率会用 BS / lxml，这里先保持轻量）
    """
    html = re.sub(r"<script[\s\S]*?</script>", "", html)
    html = re.sub(r"<style[\s\S]*?</style>", "", html)
    html = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html).strip()


# ---------- Reddit ----------
def _fetch_reddit(url: str, timeout=20) -> str:
    if not url.endswith(".json"):
        url = url.rstrip("/") + ".json"

    headers = {
        "User-Agent": "research-bot/1.0 (contact: you@example.com)"
    }

    resp = _http_get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        print(f"[reddit] HTTP {resp.status_code} for {url}")
        return ""

    try:
        data = resp.json()
        post = data[0]["data"]["children"][0]["data"]
        text = post.get("title", "") + "\n" + post.get("selftext", "")
        return text.strip()
    except Exception as e:
        print(f"[reddit] parse error: {e}")
        return ""


# ---------- StackExchange / AskUbuntu ----------
def _fetch_stackexchange(url: str, timeout=20) -> str:
    m = re.search(r"/questions/(\d+)", url)
    if not m:
        return ""

    qid = m.group(1)

    api_url = f"https://api.stackexchange.com/2.3/questions/{qid}"
    params = {
        "site": "askubuntu",
        "filter": "withbody",
    }

    resp = _http_get(api_url, params=params, timeout=timeout)
    if resp.status_code != 200:
        print(f"[stackexchange] HTTP {resp.status_code} for {api_url}")
        return ""

    try:
        item = resp.json()["items"][0]
        title = item.get("title", "")
        body = _extract_text_from_html(item.get("body", ""))
        return f"{title}\n{body}".strip()
    except Exception as e:
        print(f"[stackexchange] parse error: {e}")
        return ""


# ---------- 普通网页 ----------
def _fetch_html(url: str, timeout=20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    resp = _http_get(url, headers=headers, timeout=timeout)
    if resp.status_code != 200:
        print(f"[fetch_html] HTTP {resp.status_code} for {url}")
        return ""

    return _extract_text_from_html(resp.text)


# ---------- 你要替换的主函数 ----------
def fetch_url(url: str, timeout: int = 20) -> str:
    """
    Smart fetch:
    - Reddit -> .json
    - AskUbuntu / StackOverflow -> StackExchange API
    - Others -> HTML
    """
    domain = urlparse(url).netloc.lower()

    try:
        if "reddit.com" in domain:
            return _fetch_reddit(url, timeout)

        if "askubuntu.com" in domain or "stackoverflow.com" in domain:
            return _fetch_stackexchange(url, timeout)

        return _fetch_html(url, timeout)

    except Exception as e:
        print(f"[fetch_url] ERROR for {url}: {e}")
        return ""



def extract_install_links(base_url: str, html: str, max_links: int = 10) -> List[str]:
    """
    从文档页面中抽取与 install/installation/linux/ubuntu 等相关的链接，
    用于深挖安装说明。
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").lower()
        href_lower = href.lower()
        if any(k in href_lower for k in ["install", "installation", "getting-started", "linux", "ubuntu"]) or any(
            k in text for k in ["install", "installation", "linux", "ubuntu"]
        ):
            if href.startswith("http://") or href.startswith("https://"):
                full = href
            else:
                full = requests.compat.urljoin(base_url, href)
            links.append(full)

    # 去重
    seen = set()
    result = []
    for l in links:
        if l not in seen:
            seen.add(l)
            result.append(l)
        if len(result) >= max_links:
            break
    return result


def fetch_citation_contents(urls: List[str], known: Dict[str, str], max_chars: int = 3000) -> Dict[str, str]:
    """
    根据 citations 中的 URL 拉取网页内容，做简单截断，合并进 known 后返回。
    - known: 已经抓过的 URL->内容，避免重复请求
    """
    for url in urls:
        if not url or url in known:
            continue
        html = fetch_url(url)
        if not html:
            continue
        known[url] = summarize_text(html, max_chars)
    return known


def collect_docs_context(docs_url: str, tool_name: str, max_pages: int = 8) -> Dict[str, str]:
    """
    抓取文档首页 + 安装相关子页面 + 一些搜索结果。
    """
    ctx: Dict[str, str] = {}
    # docs_url 可能为空：此时跳过“抓取文档站点”，但仍然进行 websearch 深挖安装指南
    if docs_url:
        root_html = fetch_url(docs_url)
        if root_html:
            ctx[docs_url] = summarize_text(root_html, 6000)

        # 从主文档页抽取 install/linux/ubuntu 相关链接
        install_links = extract_install_links(docs_url, root_html or "", max_links=max_pages)
        for link in install_links:
            html = fetch_url(link)
            if html:
                ctx[link] = summarize_text(html, 6000)

    # 再用 websearch 深挖专门针对 linux/ubuntu 的安装指南
    queries = [
        f"{tool_name} install ubuntu",
        f"{tool_name} install linux",
        f"{tool_name} docker install",
    ]
    for q in queries:
        results = web_search(q, count=3)
        for r in results:
            link = r.get("link")
            if not link or link in ctx:
                continue
            html = fetch_url(link)
            if html:
                ctx[link] = summarize_text(html, 4000)

    return ctx


