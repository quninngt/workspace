#!/usr/bin/env bash
# 文案号演示 — 用 DeepSeek V4 生成情感/人生感悟笔记
set -e

API_ENDPOINT="https://api.deepseek.com/v1/chat/completions"
API_KEY="sk-b63039c8233e4012a3d87dfdb06aadc3"

echo "━━━ 文案号 演示 ━━━"
echo ""

prompt='你是一个小红书博主，粉丝30万，靠写扎心文案火了。
请生成3条不同主题的情感/人生感悟笔记。

主题1：关于"告别和放下"
主题2：关于"孤独和自洽"
主题3：关于"努力和等待"

每篇格式：
━━━━━━━━━━━━━━━━
📖 标题：<一句话标题，要有冲击力>
📷 封面配图建议：<氛围感图片描述>（如"雨夜街灯下的背影""一杯冒着热气的咖啡"）

正文：
<核心金句开篇>
<2-3句个人感悟，口语化>
<一个留白/互动结尾，比如"你呢？"或"共勉"〉

标签： #情感语录 #人生感悟 #治愈系
━━━━━━━━━━━━━━━━

要求：
- 拒绝鸡汤空洞，要有一针见血的感觉
- 像是一个30岁左右的人在深夜写的真实感受
- 每条结尾引导互动（点赞/收藏/评论）
- 不要写"以下是我为你生成的内容"'

curl -s "$API_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "deepseek-v4-flash",
    "messages": [{"role": "user", "content": '"$(echo "$prompt" | jq -Rs .)"'}],
    "temperature": 0.9,
    "max_tokens": 2000
  }' | jq -r '.choices[0].message.content'

echo ""
echo "━━━ 演示结束 ━━━"
echo "运行方式：bash demo-quotes.sh"
