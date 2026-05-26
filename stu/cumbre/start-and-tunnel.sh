#!/bin/bash
start_dev() {
  echo "🚀 启动 dev servers..."
  cd /home/ubuntu/workspace/stu/cumbre
  npm run dev &
  sleep 8
  # 确认启动
  if ss -tlnp | grep -q ':5173'; then
    echo "✅ 前端 (5173) 已启动"
  fi
  if ss -tlnp | grep -q ':8000'; then
    echo "✅ 后端 (8000) 已启动"
  fi
}

start_tunnel() {
  echo "🔗 创建 Cloudflare Tunnel..."
  echo "访问密码: cumbre2024"
  cloudflared tunnel --url http://localhost:5173 \
    --quick-service "https://challenges.cloudflare.com" \
    2>&1
}

start_dev
start_tunnel
