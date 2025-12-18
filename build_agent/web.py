from __future__ import annotations

from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from .config import SEARCH_BASE_URL, SEARCH_KEY
from .utils import summarize_text


def web_search(query: str, count: int = 5, timeout: int = 20) -> List[Dict[str, str]]:
    """基于 searchapi.io 的 websearch 封装"""
    if not SEARCH_KEY:
        return []
    url = f"{SEARCH_BASE_URL}api/v1/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SEARCH_KEY,
        "num": min(count, 10),
    }
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
            print(f"[web_search] HTTP {resp.status_code}: {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"[web_search] ERROR: {e}")
        return []


def fetch_url(url: str, timeout: int = 20) -> str:
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
        "Cache-Control": "no-cache",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.text
        print(f"[fetch_url] HTTP {resp.status_code} for {url}")
        return ""
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


