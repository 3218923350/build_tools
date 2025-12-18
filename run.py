#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多工具自动 Docker 镜像构建 Agent - v2

核心变化：
- 两个 AI 可以无限次分析 / 打分，但“真正写 Dockerfile”的机会最多 10 次。
- 每次准备写 Dockerfile 之前，两个 AI 都要明确给出 can_build + confidence，
  且 Reviewer 认为“足够有把握”才允许进入 build 流程。
- 如果两个 AI 判定在当前信息下无法可靠构建，则直接放弃该工具；
  或者 10 次构建机会用完也判定放弃。
"""
from build_agent.cli import main


if __name__ == "__main__":
    main()
