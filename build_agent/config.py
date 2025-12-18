from __future__ import annotations

import os
import textwrap
from pathlib import Path

from openai import OpenAI

# =============================
# 全局配置
# =============================

MAX_PARALLEL_TOOLS = 3  # 最多并行工具数量
MAX_BUILD_ATTEMPTS = 10  # “写 Dockerfile + build”的最大次数
BUILD_TIMEOUT = 60 * 30  # docker build 超时时间
RUN_TIMEOUT = 60 * 5  # docker run 验证超时时间

BASE_WORK_DIR = Path("tools_workspace").absolute()
LOG_DIR = Path("logs").absolute()
LOG_DIR.mkdir(parents=True, exist_ok=True)

# websearch (searchapi.io)
SEARCH_KEY = os.getenv("SEARCH_KEY", "")
SEARCH_BASE_URL = os.getenv("SEARCH_BASE_URL", "https://www.searchapi.io/")

# LLM: Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_BASE = os.getenv("GEMINI_API_BASE", "https://api.gpugeek.com/v1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")

# LLM: gpt-5
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://llm.dp.tech")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

# LLM client 初始化
gemini_client = OpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_API_BASE) if GEMINI_API_KEY else None
gpt_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE) if OPENAI_API_KEY else None

# 必须追加的 SSH / MCP 配置（在工具安装之后，Dockerfile 末尾）
REQUIRED_SSH_MCP_SNIPPET = (
    textwrap.dedent(
        """
        RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \\
            cat > /etc/supervisord.conf << 'EOF'
        [supervisord]
        nodaemon=true
        logfile=/var/log/supervisor/supervisord.log
        pidfile=/var/run/supervisord.log
        [program:sshd]
        command=/usr/sbin/sshd -D
        EOF

        RUN cat >> /etc/ssh/sshd_config << 'EOF'
        ClientAliveInterval 60
        ClientAliveCountMax 3
        EOF

        RUN mkdir -p /var/run/sshd && \\
            mkdir -p /var/log/supervisor && \\
            sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \\
            sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config

        RUN pip install mcp numpy
        """
    ).strip()
    + "\n"
)


