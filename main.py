"""
Shawn AI Team Bot - 中枢 Bot
消息分发器：判断意图，分发给不同 AI 角色
"""

import os
import urllib.request
import urllib.parse
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx

# ============== 配置 ==============
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-91fcc62518024138a8adf65ba3514775")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8768169528:AAFFQzdG973w655DknEs3BFLkIiWvGqqwlI")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# ============== AI 团队角色定义 ==============
AI_TEAM = {
    "小红书运营官": {
        "emoji": "🎨",
        "system": "你是一位资深小红书运营专家，擅长创作爆款内容。为渡劫APP创作推广笔记。渡劫APP是一款帮家长管理辅导作业情绪的微信小程序，有摆渡人提醒、深呼吸训练、戳气球发泄、敲木鱼等功能。目标用户是辅导孩子作业容易崩溃的家长。内容风格：标题有吸引力，正文结构清晰，真实场景代入，语气活泼接地气。直接给出可发布的内容。",
        "keywords": ["小红书", "笔记", "文案", "爆款", "标题", "种草", "写作", "推广"]
    },
    "数据分析师": {
        "emoji": "📊",
        "system": "你是一位数据分析专家，擅长从数据中发现规律。为渡劫APP分析运营数据，关注用户增长、功能使用、用户行为等指标。回答逻辑清晰，善用表格列表，给出可落地的建议。",
        "keywords": ["分析", "数据", "报告", "统计", "趋势", "增长", "用户", "转化"]
    },
    "智能客服": {
        "emoji": "💬",
        "system": "你是一位专业亲切的客服，善于解决用户问题。渡劫APP是帮家长管理辅导作业情绪的微信小程序。微信搜索渡劫即可使用，基础功能免费，数据本地存储保护隐私。回答简洁友善，每次结束询问是否还有其他问题。",
        "keywords": ["客服", "问题", "帮助", "咨询", "怎么用", "收费", "功能"]
    },
    "技术顾问": {
        "emoji": "💻",
        "system": "你是一位全栈技术专家，精通微信小程序开发。为渡劫APP提供技术支持、代码优化建议。技术栈：微信小程序原生开发、微信云开发。回答精准，直接给代码示例。",
        "keywords": ["代码", "报错", "bug", "开发", "部署", "小程序", "云开发"]
    },
    "AI中枢": {
        "emoji": "🤖",
        "system": "你是Shawn的私人AI助手，聪明、高效、有个性。渡劫APP是一款帮家长管理辅导作业情绪的微信小程序。你能处理各种问题，回答直接不废话，语气轻松偶尔幽默。",
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

    headers = {
        "Authorization": f"Bearer {QWEN_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": QWEN_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "max_tokens": 1500,
        "temperature": 0.7
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(QWEN_API_URL, headers=headers, json=payload)
            print(f"[{agent_name}] API状态码: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            return f"{emoji} {agent_name}\n\n{reply}"
    except Exception as e:
        print(f"[{agent_name}] 调用失败: {e}")
        return f"⚠️ AI调用失败: {str(e)}"

# ============== 文本清理 ==============
def clean_text(text: str) -> str:
    text = ''.join(c for c in text if c.isprintable() or c in '\n\t')
    if len(text) > 4000:
        text = text[:4000] + "..."
    return text

# ============== Telegram 发送消息 ==============
async def send_telegram_message(chat_id: int, text: str):
    clean_content = clean_text(text)
    url = f"{TELEGRAM_API_URL}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "text": clean_content
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Telegram发送: {resp.status}")
    except Exception as e:
        print(f"Telegram发送失败: {e}")

# ============== 路由 ==============
@app.get("/")
async def root():
    return {
        "status": "ok",
        "bot": "Shawn AI Team Bot",
        "version": "3.0.0",
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

    if not text or not chat_id:
        return {"ok": True}

    print(f"收到消息: {text}")

    agent_name = pick_agent(text)
    agent = AI_TEAM[agent_name]
    print(f"分配给: {agent['emoji']} {agent_name}")

    await send_telegram_message(chat_id, f"⏳ {agent['emoji']} {agent_name} 正在处理...")

    reply = await call_llm(text, agent_name)
    await send_telegram_message(chat_id, reply)

    return {"ok": True}

@app.get("/team")
async def show_team():
    return {"team": [{"name": k, "emoji": v["emoji"]} for k, v in AI_TEAM.items()]}

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="No message")
    agent_name = pick_agent(message)
    reply = await call_llm(message, agent_name)
    return {"agent": agent_name, "reply": reply}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
