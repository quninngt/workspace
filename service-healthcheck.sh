#!/bin/bash
# Service Health Check & Auto-Recovery
# 检查所有服务的前端/后端/隧道是否存活，挂了自动重启
# 用法: 每5分钟跑一次 crontab 或 systemd timer

set -euo pipefail

LOG="/tmp/service-healthcheck.log"
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

log() { echo "[$(timestamp)] $1" >> "$LOG"; }

# 检查端口是否存活
check_port() {
    timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/$1" 2>/dev/null
}

# 启动进程（带日志）
start_proc() {
    local name="$1" path="$2" cmd="$3"
    log "  RESTART: $name ($cmd)"
    cd "$path"
    nohup bash -c "$cmd" > "/tmp/${name}.log" 2>&1 &
    sleep 2
}

# ── Service Definitions ──
declare -A SVC_BACKEND_PORT=( [cumbre]=8000 [portal]=8002 [lottery]=8001 )
declare -A SVC_FRONTEND_PORT=( [cumbre]=5173 [portal]=5175 [lottery]=5174 )
declare -A SVC_BACKEND_PATH=(
    [cumbre]="/home/ubuntu/workspace/stu/cumbre/backend"
    [portal]="/home/ubuntu/workspace/portal/backend"
    [lottery]="/home/ubuntu/workspace/beijing-lottery/backend"
)
declare -A SVC_FRONTEND_PATH=(
    [cumbre]="/home/ubuntu/workspace/stu/cumbre/client"
    [portal]="/home/ubuntu/workspace/portal/client"
    [lottery]="/home/ubuntu/workspace/beijing-lottery/client"
)
declare -A SVC_BACKEND_CMD=(
    [cumbre]=".venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
    [portal]="python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload"
    [lottery]=".venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001"
)
declare -A SVC_FRONTEND_CMD=(
    [cumbre]="npx vite --port 5173 --host 0.0.0.0"
    [portal]="npx vite --host 0.0.0.0 --port 5175"
    [lottery]="npx vite --host 0.0.0.0 --port 5174"
)

log "=== Health Check Start ==="

NEED_PUSH=false

for svc in cumbre portal lottery; do
    bk_port=${SVC_BACKEND_PORT[$svc]}
    ft_port=${SVC_FRONTEND_PORT[$svc]}

    # Check backend
    if ! check_port "$bk_port"; then
        log "DOWN: $svc backend (port $bk_port)"
        start_proc "${svc}-backend" "${SVC_BACKEND_PATH[$svc]}" "${SVC_BACKEND_CMD[$svc]}"
        if check_port "$bk_port"; then
            log "  OK: $svc backend recovered"
            NEED_PUSH=true
        else
            log "  FAIL: $svc backend still down after restart"
        fi
    fi

    # Check frontend
    if ! check_port "$ft_port"; then
        log "DOWN: $svc frontend (port $ft_port)"
        start_proc "${svc}-frontend" "${SVC_FRONTEND_PATH[$svc]}" "${SVC_FRONTEND_CMD[$svc]}"
        if check_port "$ft_port"; then
            log "  OK: $svc frontend recovered"
            NEED_PUSH=true
        else
            log "  FAIL: $svc frontend still down after restart"
        fi
    fi
done

# Check cloudflared tunnels
for ft_port in 5173 5175; do
    if check_port "$ft_port" && ! pgrep -f "cloudflared tunnel.*$ft_port" > /dev/null 2>&1; then
        log "DOWN: cloudflared tunnel for port $ft_port"
        log "  RESTART: cloudflared tunnel --url http://localhost:$ft_port"
        nohup cloudflared tunnel --url "http://localhost:$ft_port" > "/tmp/cf_tunnel_${ft_port}.log" 2>&1 &
        NEED_PUSH=true
    fi
done

if [ "$NEED_PUSH" = true ]; then
    log "Services recovered — URL may have changed, check /tmp/cf_tunnel_*.log"
fi

log "=== Health Check End ==="
