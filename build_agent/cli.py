from __future__ import annotations

import argparse
import os
import threading
import time
from typing import List, Optional

import requests

from .api_client import dispatch_task, report_result
from .builder import build_image_for_task


def _worker_loop(
    worker_idx: int,
    dispatch_url: str,
    report_url: str,
    worker_ip: str,
    report_md_base: str,
    idle_sleep: float = 1.0,
):
    last_idle_log = 0.0
    idle_count = 0
    while True:
        task = dispatch_task(dispatch_url=dispatch_url, worker_ip=worker_ip)
        if task is None:
            idle_count += 1
            now = time.time()
            if now - last_idle_log > 30:
                print(f"[worker-{worker_idx}] idle (no task). dispatch_url={dispatch_url} worker_ip={worker_ip} idle_count={idle_count}")
                last_idle_log = now
            time.sleep(idle_sleep)
            continue

        print(f"[worker-{worker_idx}] got task_id={task.task_id} tool={task.tool_meta.get('name')}")

        result = build_image_for_task(
            task_id=task.task_id,
            tool_meta=task.tool_meta,
            worker_ip_for_report=worker_ip,
            report_md_base=report_md_base,
        )

        if result.status == "success":
            payload = {
                "task_id": result.task_id,
                "status": "success",
                "result_json": result.result_json,
                "process_md_url": result.process_md_url,
            }
        else:
            payload = {
                "task_id": result.task_id,
                "status": "failed",
                "error_message": result.error_message,
                "process_md_url": result.process_md_url,
            }

        ok = report_result(report_url=report_url, payload=payload)
        if not ok:
            print(f"[worker-{worker_idx}] report failed for task_id={result.task_id}")


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="自动构建工具 Docker 镜像（API dispatch/report，v3）")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="并发 worker 数（默认 10；会并发请求 dispatch）",
    )
    parser.add_argument(
        "--report-md-base",
        default="/build_agent",
        help="上报 process_md_url 的路径前缀（默认 /build_agent；最终形如 ip:/build_agent/logs/xxx.md）",
    )
    parser.add_argument(
        "--idle-sleep",
        type=float,
        default=1.0,
        help="无任务时 sleep 秒数（默认 1.0）",
    )

    args = parser.parse_args(argv)
    # url = os.getenv("URL", "https://tast-agent.test.dp.tech").strip()
    url = os.getenv("URL", "https://tooltask.test.dp.tech").strip()

    dispatch_url = f"{url}/api/v1/dispatch".strip()
    report_url = f"{url}/api/v1/report".strip()
    worker_ip = os.getenv("WORKER_IP", "").strip()
    if not worker_ip:
        # 通过云厂商元数据服务获取公网 EIP（你指定的获取方式）
        ip_url = os.getenv("WORKER_IP_URL", "http://100.100.100.200/latest/meta-data/eipv4").strip()
        try:
            r = requests.get(ip_url, timeout=5)
            if r.status_code == 200:
                worker_ip = (r.text or "").strip()
        except Exception as e:
            print(f"[main] failed to fetch worker_ip from {ip_url}: {e}")
            worker_ip = ""

    if not worker_ip:
        raise RuntimeError("WORKER_IP 为空：请设置 WORKER_IP，或确保 WORKER_IP_URL 可访问并返回 IP。")

    print(f"[main] dispatch_url={dispatch_url}")
    print(f"[main] report_url={report_url}")
    print(f"[main] worker_ip={worker_ip}")
    print(f"[main] concurrency={args.concurrency} idle_sleep={args.idle_sleep} report_md_base={args.report_md_base}")

    threads: List[threading.Thread] = []
    for i in range(args.concurrency):
        th = threading.Thread(
            target=_worker_loop,
            args=(
                i,
                dispatch_url,
                report_url,
                worker_ip,
                args.report_md_base,
                args.idle_sleep,
            ),
            daemon=True,
        )
        th.start()
        threads.append(th)

    # 主线程阻塞
    try:
        for th in threads:
            th.join()
    except KeyboardInterrupt:
        print("\n[main] received Ctrl+C, exiting (workers are daemon threads).")
        return


if __name__ == "__main__":
    main()


