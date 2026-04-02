"""
Shawn AI Team Bot - 中枢 Bot
消息分发器：判断意图，分发给不同 AI 角色（通义千问驱动）
"""

import os
import json
import re
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio

# ============== 配置 ==============
# OpenClaw Gateway 配置（本地运行用）
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "")
OPENCLAW_API_KEY = os.getenv("OPENCLAW_API_KEY", "")
OPENCLAW_MODEL = "modelroute"

# 通义千问 API 配置（Railway部署用）
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-91fcc62518024138a8adf65ba3514775")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"

# 判断使用哪个模型后端
USE_OPENCLAW = bool(OPENCLAW_GATEWAY_URL and OPENCLAW_API_KEY)
USE_QWEN = bool(QWEN_API_KEY)

# Telegram 配置
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8768169528:AAFFQzdG973w655DknEs3BFLkIiWvGqqwlI")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ============== 渡劫APP 产品知识 ==============
DUJIE_PRODUCT = """
【渡劫APP - 产品知识库】

## 产品定位
渡劫APP 是一款帮家长管理辅导作业时情绪的微信小程序。
Slogan：陪你度过每一个崩溃的瞬间

## 核心功能
1. 摆渡人提醒 - 设置定时提醒，到点自动语音提醒该辅导作业了
2. 深呼吸训练 - 60秒引导式深呼吸，快速平复情绪
3. 戳气球发泄 - 每次崩溃戳爆一个气球，安全发泄情绪
4. 敲木鱼积渡劫值 - 每敲一次木鱼+1渡劫值，记录今日崩溃次数

## 目标用户
- 辅导孩子作业容易崩溃的家长（主要是妈妈）
- 孩子年龄：小学阶段（6-12岁）

## 用户场景
- 讲第5遍孩子还是一脸懵，血压飙升
- 孩子写作业磨蹭，2小时才写3道题
- 辅导数学崩溃，想吼又怕伤害孩子
- 每天辅导作业都像打仗，身心俱疲

## 产品优势
- 微信小程序，无需下载，扫码即用
- 专为辅导作业场景设计，功能精准
- 有趣好玩，敲木鱼、戳气球，发泄还能积功德

## 获取方式
微信搜索「渡劫」或扫描小程序码

## 联系方式
邮箱：35211711@qq.com
微信：yangbigman
"""

# ============== AI 团队角色定义 ==============
AI_TEAM = {
 "小红书运营官": {
 "emoji": "🎨",
 "system": f"""你是一位资深小红书运营专家，擅长创作爆款内容。

{DUJIE_PRODUCT}

## 你的任务
为渡劫APP创作小红书推广内容，目标是吸引辅导作业崩溃的家长关注和使用。

## 内容风格
- 标题必须有吸引力，善用数字、emoji、疑问句、痛点共鸣
- 正文结构清晰，分段落，多用 emoji 点缀
- 真实场景代入，让家长觉得「这就是我」
- 自然植入产品功能
- 结尾要有互动引导
- 语气活泼、接地气，像闺蜜分享一样自然

回答时直接给出可以发布的内容，不要解释太多。""",
 "keywords": ["小红书", "笔记", "文案", "爆款", "标题", "种草", "博主", "粉丝", "涨粉", "内容", "发帖", "写作", "推广", "营销"]
 },
 "数据分析师": {
 "emoji": "📊",
 "system": f"""你是一位严谨的数据分析专家，擅长从数据中发现规律和洞察。

{DUJIE_PRODUCT}

## 你的任务
分析渡劫APP的运营数据，为产品迭代和推广策略提供数据支撑。

## 关注指标
- 用户增长：新增用户、日活、留存率
- 功能使用：各功能使用频次
- 用户行为：平均崩溃次数、使用时段分布
- 推广效果：小红
