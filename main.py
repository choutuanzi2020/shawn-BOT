"""
Shawn AI Team Bot - 极简快速版
去掉复杂架构，每次请求只调用一次 AI，追求极速响应
"""

import os
import time
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional
from functools import lru_cache
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx

# ============== 配置 ==============
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-91fcc62518024138a8adf65ba3514775")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-plus")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8768169528:AAFFQzdG973w655DknEs3BFLkIiWvGqqwlI").strip()
TELEGRAM_API_URL = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN

# ============== FastAPI 应用 ==============
app = FastAPI(title="Shawn AI Team Bot - 极速版")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== AI 团队角色定义 ==============
AI_TEAM = {
    "🎨 小红书运营官": {
        "emoji": "🎨",
        "name": "小红书运营官",
        "system": "你是一位资深小红书运营专家，擅长创作爆款内容、文案撰写、标题优化。回答简洁专业，直接给出建议。",
        "keywords": ["小红书", "笔记", "文案", "爆款", "标题", "种草", "写作", "推广", "内容"]
    },
    "📊 数据分析师": {
        "emoji": "📊",
        "name": "数据分析师",
        "system": "你是一位数据分析专家，擅长数据统计、趋势分析、用户增长分析。回答简洁专业，直接给出建议。",
        "keywords": ["分析", "数据", "统计", "趋势", "增长", "用户", "转化", "报表"]
    },
    "💬 智能客服": {
        "emoji": "💬",
        "name": "智能客服",
        "system": "你是一位专业客服，善于解答问题、解决用户疑虑。回答亲切简洁。",
        "keywords": ["客服", "问题", "帮助", "咨询", "怎么用", "收费", "功能", "退款", "账号"]
    },
    "💻 技术顾问": {
        "emoji": "💻",
        "name": "技术顾问",
        "system": "你是一位全栈技术专家，精通代码开发、bug修复、架构设计。回答简洁专业。",
        "keywords": ["代码", "报错", "bug", "开发", "部署", "小程序", "云开发", "数据库", "服务器"]
    }
}

# 默认 Agent
DEFAULT_AGENT = {
    "emoji": "🤖",
    "name": "AI中枢",
    "system": "你是Shawn的私人AI助手，聪明、高效、有个性。回答简洁有趣。",
    "keywords": []
}


# ============== 记忆系统（简化） ==============
class SimpleMemory:
    """极简记忆：只保留最近 5 轮对话"""
    
    def __init__(self):
        self.conversations: Dict[str, List[Dict]] = {}
        self.max_history = 5
    
    def add(self, user_id: str, role: str, content: str):
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        self.conversations[user_id].append({"role": role, "content": content})
        if len(self.conversations[user_id]) > self.max_history * 2:
            self.conversations[user_id] = self.conversations[user_id][-self.max_history * 2:]
    
    def get(self, user_id: str) -> List[Dict]:
        return self.conversations.get(user_id, [])


memory = SimpleMemory()


# ============== 响应缓存 ==============
class ResponseCache:
    """简单缓存：热门问题 5 分钟内不重复调用 AI"""
    
    def __init__(self):
        self.cache: Dict[str, Dict] = {}
        self.ttl = 300  # 5 分钟
    
    def _make_key(self, text: str, agent: str) -> str:
        """生成缓存 key"""
        raw = f"{agent}:{text}"
        return hashlib.md5(raw.encode()).hexdigest()
    
    def get(self, text: str, agent: str) -> Optional[str]:
        key = self._make_key(text, agent)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["time"] < self.ttl:
                return entry["response"]
            else:
                del self.cache[key]
        return None
    
    def set(self, text: str, agent: str, response: str):
        key = self._make_key(text, agent)
        self.cache[key] = {"response": response, "time": time.time()}
    
    def clear_old(self):
        """清理过期缓存"""
        now = time.time()
        self.cache = {k: v for k, v in self.cache.items() if now - v["time"] < self.ttl}


cache = ResponseCache()


# ============== 意图识别（极简关键词） ==============
def pick_agent(message: str) -> Dict:
    """根据关键词快速选择 Agent"""
    message_lower = message.lower()
    
    best_agent = None
    best_score = 0
    
    for agent_key, agent_info in AI_TEAM.items():
        score = sum(1 for kw in agent_info["keywords"] if kw in message_lower)
        if score > best_score:
            best_score = score
            best_agent = agent_info
    
    if best_agent is None:
        return DEFAULT_AGENT
    
    return best_agent


# ============== LLM 调用 ==============
async def call_qwen(messages: List[Dict], max_tokens: int = 800) -> str:
    """调用通义千问 API"""
    headers = {
        "Authorization": "Bearer " + QWEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": QWEN_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(QWEN_API_URL, headers=headers, json=payload)
            print("[Qwen]", response.status_code)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("[Error]", e)
        return "抱歉，服务暂时不可用，请稍后重试。"


# ============== Telegram 发送 ==============
async def send_message(chat_id: str, text: str):
    """发送消息"""
    # 清理文本
    clean = ''.join(c if c.isprintable() or c == '\n' else '' for c in text)
    if len(clean) > 4000:
        clean = clean[:4000] + "..."
    
    url = TELEGRAM_API_URL + "/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "text": clean,
        "parse_mode": "Markdown"
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print("[Telegram Error]", e)
        return None


async def edit_message(chat_id: str, message_id: int, text: str):
    """编辑消息（实现打字效果）"""
    clean = ''.join(c if c.isprintable() or c == '\n' else '' for c in text)
    if len(clean) > 4000:
        clean = clean[:4000] + "..."
    
    url = TELEGRAM_API_URL + "/editMessageText"
    data = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "message_id": message_id,
        "text": clean,
        "parse_mode": "Markdown"
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except:
        return None


# ============== 路由 ==============
@app.get("/")
async def root():
    return {
        "status": "ok",
        "bot": "Shawn AI Team Bot",
        "version": "5.0.0",
        "mode": "极速版"
    }


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """处理 Telegram 消息 - 极速版"""
    try:
        body = await request.json()
    except:
        return {"ok": False}
    
    message = body.get("message", {})
    if not message:
        return {"ok": True}
    
    # 忽略机器人消息
    if message.get("from", {}).get("is_bot"):
        return {"ok": True}
    
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    
    if not text or not chat_id:
        return {"ok": True}
    
    user_id = str(chat_id)
    print(f"[收到] {text[:50]}")
    
    # 记录用户消息
    memory.add(user_id, "user", text)
    
    # 快速选择 Agent（不用 AI 分类）
    agent = pick_agent(text)
    agent_name = agent["name"]
    emoji = agent["emoji"]
    
    # 发送处理中提示
    thinking_msg = await send_message(
        chat_id,
        f"{emoji} **{agent_name}** 正在思考...\n\n⏳"
    )
    
    # 检查缓存
    cached = cache.get(text, agent_name)
    if cached:
        # 有缓存，直接发送
        result_text = emoji + " " + cached
        await send_message(chat_id, result_text)
        if thinking_msg and "message_id" in thinking_msg:
            await edit_message(chat_id, thinking_msg["message_id"], result_text)
        return {"ok": True}
    
    # 构建消息
    context = memory.get(user_id)
    messages = [{"role": "system", "content": agent["system"]}]
    
    # 添加上下文（最多 3 轮）
    for msg in context[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    messages.append({"role": "user", "content": text})
    
    # 调用 AI（只调用一次！）
    response = await call_qwen(messages)
    
    # 缓存结果
    cache.set(text, agent_name, response)
    
    # 记录 AI 回复
    memory.add(user_id, "assistant", response)
    
    # 发送最终结果
    result_text = emoji + " " + response
    await send_message(chat_id, result_text)
    
    # 更新"处理中"消息
    if thinking_msg and "message_id" in thinking_msg:
        await edit_message(chat_id, thinking_msg["message_id"], result_text)
    
    return {"ok": True}


@app.get("/team")
async def show_team():
    team_list = [{"name": info["name"], "emoji": info["emoji"]} for info in AI_TEAM.values()]
    team_list.append({"name": "AI中枢", "emoji": "🤖"})
    return {"team": team_list}


@app.get("/stats")
async def show_stats():
    """显示统计信息"""
    cache.clear_old()
    return {
        "cache_size": len(cache.cache),
        "conversations": len(memory.conversations)
    }


# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    import json
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
