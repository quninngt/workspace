#!/usr/bin/env bash
# 书单号演示 — 用 DeepSeek V4 生成 3 条小红书笔记
set -e

API_ENDPOINT="https://api.deepseek.com/v1/chat/completions"
API_KEY="sk-b63039c8233e4012a3d87dfdb06aadc3"

echo "━━━ 书单号 演示 ━━━"
echo ""

prompt='你是一个小红书博主，粉丝20万，专做书单推荐。
请为以下3本书各生成一条小红书笔记。

书籍列表（必选这3本，不要换）：
1. 《富爸爸穷爸爸》— 理财启蒙
2. 《被讨厌的勇气》— 阿德勒心理学
3. 《人类简史》— 宏大历史叙事

每篇笔记格式如下：
━━━━━━━━━━━━━━━━
📖 标题：<吸引人的标题，带数字>
📷 封面配图建议：<一句话描述封面设计>

正文：
<3-5行正文，用emoji和换行分段，口语化，像是真人写的>

标签： #书单 #读书推荐 #必读好书
━━━━━━━━━━━━━━━━

要求：
- 标题必须有数字（如"这3本…"、"豆瓣9分以上的5本…"）
- 正文口语化，带个人感受，不要AI味
- 每篇完全不同风格
- 不要写"以下是我为你生成的"这种引导语'

curl -s "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": '"$(echo "$prompt" | jq -Rs .)"'}],
    "temperature": 0.8,
    "max_tokens": 2000
  }' | jq -r '.choices[0].message.content'

echo ""
echo "━━━ 演示结束 ━━━"
echo "运行方式：bash demo-book.sh"
