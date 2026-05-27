#!/usr/bin/env bash
# 知识科普号演示 — 用 DeepSeek V4 生成冷知识/实用技巧笔记
set -e

API_ENDPOINT="https://api.deepseek.com/v1/chat/completions"
API_KEY="sk-b63039c8233e4012a3d87dfdb06aadc3"

echo "━━━ 知识科普号 演示 ━━━"
echo ""

prompt='你是一个小红书博主，做知识科普方向，专讲"大多数人不知道但超级有用"的冷知识和实用技巧。

请生成3条笔记，主题如下：
主题1：日常生活的科学冷知识（比如"为什么飞机窗户是圆的"这类）
主题2：打工人效率技巧（不常见的实用技巧）
主题3：健康/养生冷知识（颠覆常识的那种）

每篇格式：
━━━━━━━━━━━━━━━━
📖 标题：<带数字+引发好奇，如"99%的人不知道…">
📷 封面配图建议：<信息图风格描述>（如"深色背景+白色大字"）

正文：
<开篇提问/设悬念>
<3-4个干货点，每个点简短一句>
<总结金句>

标签： #冷知识 #涨知识 #实用技巧 #科普
━━━━━━━━━━━━━━━━

要求：
- 知识必须有来源/proven，不能编造
- 每个点控制在1-2句话，小红书用户没耐心看长文
- 用"你知道吗？""是不是很神奇"这类互动语气
- 不要写"以下是我为你生成的"'

curl -s "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": '"$(echo "$prompt" | jq -Rs .)"'}],
    "temperature": 0.7,
    "max_tokens": 2000
  }' | jq -r '.choices[0].message.content'

echo ""
echo "━━━ 演示结束 ━━━"
echo "运行方式：bash demo-tips.sh"
