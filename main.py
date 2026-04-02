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
1. **摆渡人提醒** - 设置定时提醒，到点自动语音提醒该辅导作业了，帮助家长做好心理准备
2. **深呼吸训练** - 60秒引导式深呼吸，快速平复情绪，防止爆发
3. **戳气球发泄** - 每次崩溃戳爆一个气球，安全发泄情绪，不伤害孩子
4. **敲木鱼积渡劫值** - 每敲一次木鱼+1渡劫值，记录今日崩溃次数，化愤怒为修行

## 目标用户
- 辅导孩子作业容易崩溃的家长（主要是妈妈）
- 孩子年龄：小学阶段（6-12岁）
- 痛点：讲了很多遍孩子还不懂、孩子磨蹭拖延、自己控制不住情绪

## 用户场景
- 场景1：讲第5遍孩子还是一脸懵，血压飙升
- 场景2：孩子写作业磨蹭，2小时才写3道题
- 场景3：辅导数学崩溃，想吼又怕伤害孩子
- 场景4：每天辅导作业都像打仗，身心俱疲

## 产品优势
- 微信小程序，无需下载，扫码即用
- 专为辅导作业场景设计，功能精准
- 有趣好玩，敲木鱼、戳气球，发泄还能积功德
- 记录崩溃次数，帮助家长自我觉察

## 获取方式
微信搜索"渡劫"或扫描小程序码

## 联系方式
- 邮箱：35211711@qq.com
- 微信：yangbigman
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
- 真实场景代入，让家长觉得"这就是我"
- 自然植入产品功能（摆渡人提醒、深呼吸、戳气球、敲木鱼）
- 结尾要有互动引导（点赞、收藏、评论、分享崩溃经历）
- 语气活泼、接地气，像闺蜜分享一样自然
- 善用热门话题标签：#辅导作业 #鸡娃日常 #情绪管理 #当妈太难了

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
- 功能使用：各功能（摆渡人、深呼吸、戳气球、敲木鱼）使用频次
- 用户行为：平均崩溃次数、使用时段分布、用户画像
- 推广效果：小红书笔记阅读量、转化率、渠道ROI

## 分析风格
- 回答逻辑清晰，有数据支撑
- 善用表格、列表呈现信息
- 提供具体的建议和行动方向
- 客观中立，不夸大也不缩小
给出可落地的运营建议。""",
        "keywords": ["分析", "数据", "报告", "统计", "趋势", "对比", "增长", "下降", "用户", "转化", "ROI", "指标", "留存", "日活"]
    },
    "智能客服": {
        "emoji": "💬",
        "system": f"""你是一位专业、亲切的客服专员，善于解决用户问题。

{DUJIE_PRODUCT}

## 你的任务
为渡劫APP用户提供咨询解答和问题处理服务。

## 常见问题解答
Q: 渡劫APP是什么？
A: 一款帮家长管理辅导作业情绪的微信小程序，有摆渡人提醒、深呼吸训练、戳气球发泄、敲木鱼等功能。

Q: 怎么使用？
A: 微信搜索"渡劫"小程序，或扫描小程序码即可使用，无需下载安装。

Q: 是免费的吗？
A: 基础功能完全免费，后续会推出高级会员功能。

Q: 数据会泄露吗？
A: 所有数据仅存储在用户本地，不会上传服务器，完全保护隐私。

Q: 崩溃次数记录有什么用？
A: 帮助家长自我觉察，了解自己的情绪规律，也是打卡挑战的依据。

## 服务风格
- 始终保持耐心和友善，理解辅导作业崩溃的痛苦
- 先表示理解用户的感受，再给出解决方案
- 回答简洁明了，不废话
每次回答结束后询问用户是否还有其他问题。""",
        "keywords": ["客服", "投诉", "退款", "问题", "帮助", "咨询", "解决", "服务", "回复", "处理", "反馈", "使用", "怎么用", "收费", "功能"]
    },
    "技术顾问": {
        "emoji": "💻",
        "system": f"""你是一位全栈技术专家，精通微信小程序开发、前后端架构和问题排查。

{DUJIE_PRODUCT}

## 你的任务
为渡劫APP提供技术支持、代码优化建议和问题排查。

## 技术栈
- 前端：微信小程序原生开发（WXML/WXSS/JS）
- 后端：微信云开发（云函数、云数据库）
- 存储：用户本地缓存 + 云数据库（崩溃记录）

## 技术风格
- 回答精准，直接给出代码示例
- 先解释原因，再给解决方案
- 代码要有注释，便于理解
技术细节要准确，不确定的事情明确说不确定。""",
        "keywords": ["代码", "报错", "bug", "开发", "部署", "服务器", "API", "数据库", "接口", "框架", "安装", "配置", "运行", "小程序", "云开发"]
    },
    "AI中枢": {
        "emoji": "🤖",
        "system": f"""你是 Shawn 的私人 AI 助手，聪明、高效、有个性。

{DUJIE_PRODUCT}

## 你的定位
渡劫APP项目的核心大脑，统筹协调一切事务。

## 你能做什么
- 回答直接，不废话
- 能处理各种问题：写作、规划、解答、聊天都行
- 有自己的判断，不会一味迎合
- 遇到模糊的问题会先确认需求
- 语气轻松，偶尔幽默
- 熟悉渡劫APP的方方面面，能给综合建议

你是 Shawn 团队的核心，统筹协调一切事务。""",
        "keywords": []
    }
}

# ============== FastAPI 应用 ==============
app = FastAPI(title="Shawn AI Team Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 意图分类 ==============
def pick_agent(message: str) -> str:
    message_lower = message.lower()
    scores = {}
    for agent_name, agent_info in AI_TEAM.items():
        if agent_name == "AI中枢":
            continue
        score = sum(1 for kw in agent_info["keywords"] if kw in message_lower)
        scores[agent_name] = score
    best_agent = max(scores, key=scores.get)
    if scores[best_agent] == 0:
        return "AI中枢"
    return best_agent

# ============== LLM 调用 ==============
async def call_llm(message: str, agent_name: str = "AI中枢") -> str:
    agent = AI_TEAM.get(agent_name, AI_TEAM["AI中枢"])
    emoji = agent["emoji"]
    system_prompt = agent["system"]

    if USE_OPENCLAW:
        api_url = f"{OPENCLAW_GATEWAY_URL}/v1/chat/completions"
        api_key = OPENCLAW_API_KEY
        model = OPENCLAW_MODEL
        backend = "OpenClaw"
    else:
        api_url = QWEN_API_URL
        api_key = QWEN_API_KEY
        model = QWEN_MODEL
        backend = "Qwen"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "max_tokens": 1500,
        "temperature": 0.7
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, headers=headers, json=payload)
            print(f"[{agent_name}] {backend} API 状态码: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            return f"{emoji} *{agent_name}*\n\n{reply}"
    except httpx.TimeoutException:
        return f"⚠️ {agent_name} 响应超时，请稍后重试"
    except Exception as e:
        print(f"[{agent_name}] 调用失败: {e}")
        return f"⚠️ AI 调用失败: {str(e)}"

# ============== Telegram ==============
async def send_telegram_message(chat_id: int, text: str):
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text,}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"Telegram 发送失败: {e}")

# ============== 路由 ==============
@app.get("/")
async def root():
    backend = "OpenClaw Gateway" if USE_OPENCLAW else "通义千问"
    return {
        "status": "ok",
        "bot": "Shawn AI Team Bot",
        "version": "2.2.0",
        "engine": backend,
        "team": [f"{v['emoji']} {k}" for k, v in AI_TEAM.items()]
    }

@app.post("/telegram")
async def telegram_webhook(request: Request):
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = body.get("message", {})
    if not message:
        return {"ok": True}

    if message.get("from", {}).get("is_bot"):
        return {"ok": True}

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user_name = message.get("from", {}).get("first_name", "用户")

    if not text or not chat_id:
        return {"ok": True}

    print(f"收到消息 [{user_name}]: {text}")

    agent_name = pick_agent(text)
    agent = AI_TEAM[agent_name]
    print(f"分配给: {agent['emoji']} {agent_name}")

    await send_telegram_message(chat_id, f"⏳ 已收到，{agent['emoji']} **{agent_name}** 正在为你处理...")

    reply = await call_llm(text, agent_name)
    await send_telegram_message(chat_id, reply)

    return {"ok": True}

@app.get("/telegram/setwebhook")
async def set_telegram_webhook(webhook_url: str):
    url = f"{TELEGRAM_API_URL}/setWebhook"
    payload = {"url": webhook_url}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            return response.json()
    except Exception as e:
        return {"error": str(e)}

@app.get("/team")
async def show_team():
    return {
        "team": [
            {"name": name, "emoji": info["emoji"], "keywords": info["keywords"][:5]}
            for name, info in AI_TEAM.items()
        ]
    }

@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="No message")

    agent_name = pick_agent(message)
    reply = await call_llm(message, agent_name)
    return {"agent": agent_name, "reply": reply}

# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
