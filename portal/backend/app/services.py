"""
Service definitions and management logic for the portal.
"""
import os
import signal
import subprocess
import asyncio
from typing import Optional

# ── Service Definitions ──

SERVICES = [
    {
        "id": "beijing-lottery",
        "name": "北京摇号模拟器",
        "description": "模拟北京小客车指标摇号（燃油车）— 一年两期、阶梯基数递增",
        "category": "模拟器",
        "web_url": "https://introducing-colors-findings-polo.trycloudflare.com",
        "backend": {"port": 8001, "path": "/home/ubuntu/workspace/beijing-lottery/backend", "cmd": "uvicorn app.main:app --host 0.0.0.0 --port 8001"},
        "frontend": {"port": 5174, "path": "/home/ubuntu/workspace/beijing-lottery/client", "cmd": "npx vite --host 0.0.0.0 --port 5174"},
        "tunnel": "https://introducing-colors-findings-polo.trycloudflare.com",
    },
    {
        "id": "cumbre",
        "name": "Cumbre 基金智投",
        "description": "基金智投跟投平台 — 跟投基金经理组合、策略回测",
        "category": "金融",
        "web_url": "https://unable-auckland-attractions-logical.trycloudflare.com",
        "backend": {"port": 8000, "path": "/home/ubuntu/workspace/stu/cumbre/backend", "cmd": "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"},
        "frontend": {"port": 5173, "path": "/home/ubuntu/workspace/stu/cumbre/client", "cmd": "npx vite --host 0.0.0.0 --port 5173"},
        "tunnel": "https://unable-auckland-attractions-logical.trycloudflare.com",
    },
    {
        "id": "portal",
        "name": "服务管理门户",
        "description": "统一管理所有服务的控制面板",
        "category": "系统",
        "web_url": "https://dale-scanned-gourmet-ron.trycloudflare.com",
        "backend": {"port": 8002, "path": "/home/ubuntu/workspace/portal/backend", "cmd": "uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload"},
        "frontend": {"port": 5175, "path": "/home/ubuntu/workspace/portal/client", "cmd": "npx vite --host 0.0.0.0 --port 5175"},
        "tunnel": "https://dale-scanned-gourmet-ron.trycloudflare.com",
    },
]


def get_venv_path(backend_path: str) -> str:
    """Find the virtual env in the backend dir."""
    for p in [os.path.join(backend_path, ".venv", "bin", "python3"),
              os.path.join(backend_path, "venv", "bin", "python3")]:
        if os.path.isfile(p):
            return os.path.dirname(os.path.dirname(p))
    return ""


async def check_port(port: int) -> bool:
    """Check if a TCP port is open (service is running)."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection("127.0.0.1", port), timeout=2
        )
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
        return False


async def get_service_status(service: dict) -> dict:
    """Get the current status of a service."""
    backend_alive = await check_port(service["backend"]["port"])
    frontend_alive = await check_port(service["frontend"]["port"])
    overall = "running" if backend_alive and frontend_alive else "partial" if backend_alive or frontend_alive else "stopped"
    return {
        "id": service["id"],
        "name": service["name"],
        "description": service["description"],
        "category": service["category"],
        "status": overall,
        "backend": {"port": service["backend"]["port"], "alive": backend_alive},
        "frontend": {"port": service["frontend"]["port"], "alive": frontend_alive},
        "web_url": service["web_url"],
        "tunnel": service.get("tunnel"),
    }


def _kill_port(port: int):
    """Kill processes on a given port."""
    try:
        result = subprocess.run(
            ["fuser", "-k", f"{port}/tcp"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        pass
    # Fallback
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, timeout=5, text=True,
        )
        if result.stdout.strip():
            pids = [int(p) for p in result.stdout.strip().split("\n")]
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            return True
    except Exception:
        pass
    return False


def start_backend(service: dict) -> bool:
    """Start the backend process."""
    path = service["backend"]["path"]
    cmd = service["backend"]["cmd"]
    venv = get_venv_path(path)
    
    if venv:
        activate = os.path.join(venv, "bin", "activate")
        shell_cmd = f"setsid bash -c 'cd {path} && source {activate} && exec {cmd}' > /tmp/{service['id']}_backend.log 2>&1 &"
    else:
        shell_cmd = f"setsid bash -c 'cd {path} && exec {cmd}' > /tmp/{service['id']}_backend.log 2>&1 &"
    
    try:
        subprocess.Popen(["bash", "-c", shell_cmd], preexec_fn=os.setpgrp)
        return True
    except Exception:
        return False


def start_frontend(service: dict) -> bool:
    """Start the frontend process."""
    path = service["frontend"]["path"]
    cmd = service["frontend"]["cmd"]
    shell_cmd = f"setsid bash -c 'cd {path} && exec {cmd}' > /tmp/{service['id']}_frontend.log 2>&1 &"
    try:
        subprocess.Popen(["bash", "-c", shell_cmd], preexec_fn=os.setpgrp)
        return True
    except Exception:
        return False


def stop_service(service: dict) -> dict:
    """Stop both backend and frontend."""
    backend_killed = _kill_port(service["backend"]["port"])
    frontend_killed = _kill_port(service["frontend"]["port"])
    return {"backend": backend_killed, "frontend": frontend_killed}


def restart_service(service: dict) -> dict:
    """Restart service (stop then start)."""
    stop_service(service)
    import time
    time.sleep(1)
    bk = start_backend(service)
    ft = start_frontend(service)
    return {"backend_started": bk, "frontend_started": ft}
