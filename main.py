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
    "💬 心理客服": {
        "emoji": "💬",
        "name": "心理客服",
        "system": """你是渡劫情绪急救站的「心理客服」角色。

你的职责：
1. 倾听家长的养育压力和情绪困扰
2. 提供共情和情绪支持
3. 引导家长表达内心感受
4. 在必要时提供情绪舒缓的小技巧
5. 语气温柔、耐心，像朋友聊天

回复原则：
- 先共情，再引导
- 不评判，不说教
- 适当用"我理解你的感受"等表达
- 回复控制在100-200字内
- 不提供专业医疗或心理治疗建议

遇到需要专业帮助的情况，引导用户寻求专业支持。""",
        "keywords": ["压力", "焦虑", "情绪", "崩溃", "难受", "委屈", "生气", "育儿", "带娃", "孩子不听话", "作业", "成绩", "亲子", "沟通"]
    },
    "💻 技术顾问": {
        "emoji": "💻",
        "name": "技术顾问",
        "system": """你是渡劫情绪急救站的「技术顾问」角色。

你的职责：
1. 解答小程序使用相关问题
2. 处理APP功能咨询和使用指导
3. 技术问题排查和解决方案
4. 功能建议和改进反馈收集

回复原则：
- 简洁明了，直接解决问题
- 遇到复杂技术问题，先确认具体情况再排查
- 必要时记录问题并转交给开发团队
- 保持专业但友好的态度""",
        "keywords": ["小程序", "APP", "登录", "注册", "功能", "bug", "报错", "打不开", "使用", "操作", "怎么用", "设置"]
    },
    "📣 运营推广": {
        "emoji": "📣",
        "name": "运营推广",
        "system": """你是渡劫情绪急救站的「运营推广」角色。

你的职责：
1. 解答用户对平台活动和规则的咨询
2. 介绍平台功能和福利
3. 收集用户反馈和建议
4. 引导用户参与社区互动

回复原则：
- 热情积极，传递平台正能量
- 详细介绍活动参与方式
- 引导用户关注和参与社区话题
- 对反馈认真记录并转达""",
        "keywords": ["活动", "福利", "奖励", "积分", "社区", "话题", "参与", "建议", "反馈", "功能请求", "意见", "怎样获得"]
    },
    "🤝 社区管理": {
        "emoji": "🤝",
        "name": "社区管理",
        "system": """你是渡劫情绪急救站的「社区管理」角色。

你的职责：
1. 维护社区秩序和安全
2. 处理社区规范相关咨询
3. 引导用户遵守社区规则
4. 鼓励正向的社区互动

回复原则：
- 公正友善，维护社区氛围
- 遇到违规情况，温和但坚定地说明规则
- 鼓励用户互相支持、分享经验
- 引导建设性的社区讨论""",
        "keywords": ["规则", "规范", "禁止", "违规", "删除", "禁言", "社区", "氛围", "文明", "互助", "分享", "经验"]
    }
}

# 默认 Agent - AI中枢
DEFAULT_AGENT = {
    "emoji": "🤖",
    "name": "AI中枢",
    "system": """你是渡劫情绪急救站的「AI中枢」，负责统筹协调团队工作。

当收到用户消息时：
1. 先理解用户的核心需求
2. 快速判断应该由哪个角色处理
3. 如果不确定或问题涉及多个方面，先给出温暖、专业的通用回复
4. 必要时协调多个角色协作

渡劫的使命：帮助家长找到情绪的出口，通过社区互助和心灵陪伴，预防家长情绪暴力，让每个家庭都能找到属于自己的平静。

回复风格：温暖、专业、高效。""",
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
            print(f"[Qwen] 状态: {response.status_code}")
            
            if response.status_code == 403:
                print("[Qwen] API Key 无效或权限不足")
                return "抱歉，AI 服务配置有问题，请联系管理员。"
            
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        print(f"[HTTP Error] {e.response.status_code}: {e.response.text[:200]}")
        return "抱歉，AI 服务暂时不可用，请稍后重试。"
    except Exception as e:
        print(f"[Error] {type(e).__name__}: {e}")
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
        "bot": "渡劫情绪急救站 - 运营团队",
        "version": "6.0.0",
        "mode": "AI团队 + 留言审核 + 告警监控"
    }


@app.post("/alert")
async def send_alert(request: Request):
    """
    接收告警通知，推送到 Telegram
    POST body: {
        "title": "告警标题",
        "content": "告警内容",
        "level": "warning|error|critical"  // 可选
    }
    """
    try:
        body = await request.json()
    except Exception as e:
        print(f"[Error] JSON解析失败: {e}")
        return {"ok": False, "error": "Invalid JSON"}
    
    title = body.get("title", "🚨 告警通知")
    content = body.get("content", "")
    level = body.get("level", "warning")
    
    if not content:
        return {"ok": False, "error": "Content is empty"}
    
    # 根据告警级别选择 emoji
    level_emoji = {
        "warning": "⚠️",
        "error": "❌", 
        "critical": "🚨"
    }
    emoji = level_emoji.get(level, "⚠️")
    
    # 格式化消息
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    alert_text = f"""{emoji} **{title}**
━━━━━━━━━━━━━━━━━━
{content}
━━━━━━━━━━━━━━━━━━
⏰ 时间: {timestamp}
🤖 来源: 阿里云服务器监控"""

    # 推送到 Telegram
    admin_chat_id = os.getenv("ADMIN_CHAT_ID", "7549991042")
    result = await send_message(admin_chat_id, alert_text)
    
    if result and result.get("ok"):
        print(f"[告警] 已发送: {title}")
        return {"ok": True, "message": "Alert sent"}
    else:
        print(f"[告警] 发送失败")
        return {"ok": False, "error": "Failed to send"}


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """处理 Telegram 消息和回调 - 统一入口"""
    try:
        body = await request.json()
    except Exception as e:
        print(f"[Error] JSON解析失败: {e}")
        return {"ok": False}
    
    # ============== 处理回调按钮点击 ==============
    callback_query = body.get("callback_query")
    if callback_query:
        return await handle_callback(callback_query)
    
    # ============== 处理普通消息 ==============
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
    
    try:
        # 记录用户消息
        memory.add(user_id, "user", text)
        
        # 快速选择 Agent（不用 AI 分类）
        agent = pick_agent(text)
        agent_name = agent["name"]
        emoji = agent["emoji"]
        print(f"[路由] {agent_name}")
        
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
        print(f"[AI调用] 开始...")
        response = await call_qwen(messages)
        print(f"[AI响应] 长度={len(response)}")
        
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
        
        print(f"[完成] 回复已发送")
        return {"ok": True}
        
    except Exception as e:
        import traceback
        print(f"[Error] 处理消息异常:")
        traceback.print_exc()
        await send_message(chat_id, f"❌ 处理出错: {type(e).__name__}")
        return {"ok": True}


async def handle_callback(callback_query: Dict) -> Dict:
    """处理 Telegram InlineKeyboard 按钮回调"""
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    callback_id = callback_query.get("id")
    
    print(f"[Callback] data={data}, chat_id={chat_id}")
    
    # 解析按钮数据
    if not data.startswith("ferryman:"):
        return {"ok": True}
    
    # 回答回调（让 Telegram 停止加载动画）
    await answer_callback(callback_id)
    
    parts = data.split(":", 2)
    if len(parts) < 3:
        return {"ok": True}
    
    action = parts[1]
    user_openid = parts[2]
    
    if action == "confirm":
        # 确认发送
        pending_data = load_pending_reply(user_openid)
        if pending_data:
            reply_content = pending_data["ai_reply"]
            
            # 调用微信云函数保存回复
            save_result = await save_ferryman_reply(user_openid, reply_content)
            
            if save_result:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"✅ 已发送回复给用户\n\n💬 回复内容:\n{reply_content}",
                    []
                )
            else:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"⚠️ 回复已确认，但保存失败\n请手动保存回复内容:\n\n{reply_content}",
                    []
                )
            delete_pending_reply(user_openid)
        else:
            await send_message(chat_id, "❌ 未找到待确认的回复，可能已过期")
            
    elif action == "reject":
        # 拒绝
        await edit_message_with_buttons(
            chat_id, message_id,
            f"❌ 已拒绝该回复",
            []
        )
        delete_pending_reply(user_openid)
    
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


@app.get("/messages")
async def show_messages(limit: int = 10):
    """查看最近的留言和回复记录"""
    import os
    local_file = "/tmp/ferryman_messages.json"

    if not os.path.exists(local_file):
        return {"messages": [], "total": 0}

    try:
        with open(local_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        # 返回最新的 N 条
        recent = messages[-limit:] if len(messages) > limit else messages

        return {
            "messages": recent,
            "total": len(messages)
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/user-replies")
async def get_user_replies(openid: str = None):
    """
    根据用户 OpenId 查询该用户的新回复
    用于小程序内弹窗提醒
    """
    if not openid:
        return {"ok": False, "error": "openid is required"}

    local_file = "/tmp/ferryman_messages.json"

    if not os.path.exists(local_file):
        return {"ok": True, "replies": [], "new_count": 0}

    try:
        with open(local_file, 'r', encoding='utf-8') as f:
            messages = json.load(f)

        # 筛选该用户的回复
        user_replies = [m for m in messages if m.get("user_openid") == openid and m.get("reply_content")]

        # 返回最新的未读回复（只返回最近1条）
        recent = user_replies[-1:] if user_replies else []

        return {
            "ok": True,
            "replies": recent,
            "new_count": len(recent)
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/mark-reply-read")
async def mark_reply_read(openid: str = None):
    """
    标记用户的回复已被阅读
    """
    if not openid:
        return {"ok": False, "error": "openid is required"}

    # 将已读标记写入共享存储
    read_marker_file = "/tmp/ferryman_read_markers.json"
    markers = {}

    try:
        if os.path.exists(read_marker_file):
            with open(read_marker_file, 'r', encoding='utf-8') as f:
                markers = json.load(f)
    except:
        pass

    markers[openid] = datetime.now().isoformat()

    try:
        with open(read_marker_file, 'w', encoding='utf-8') as f:
            json.dump(markers, f, ensure_ascii=False)
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


@app.post("/notify-message")
async def notify_message(request: Request):
    """
    接收渡劫小程序用户留言通知
    POST body: {
        "userOpenId": "用户的openid",
        "content": "用户留言内容",
        "timestamp": "ISO时间戳"
    }
    """
    try:
        body = await request.json()
    except Exception as e:
        print(f"[Error] JSON解析失败: {e}")
        return {"ok": False, "error": "Invalid JSON"}
    
    user_openid = body.get("userOpenId", "unknown")
    content = body.get("content", "")
    timestamp = body.get("timestamp", "")
    
    if not content:
        return {"ok": False, "error": "Content is empty"}
    
    admin_chat_id = os.getenv("ADMIN_CHAT_ID", "7549991042")
    
    # 格式化时间
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%m-%d %H:%M")
    except:
        time_str = timestamp
    
    # 调用 AI 生成回复建议
    print(f"[渡劫] 正在生成回复建议...")
    ai_reply = await generate_ferryman_reply(content)
    
    # 保存待确认的回复（用于回调处理）- 使用文件存储
    save_pending_reply(user_openid, {
        "content": content,
        "ai_reply": ai_reply,
        "timestamp": timestamp,
        "time_str": time_str
    })
    
    # 发送确认消息给管理员（带 InlineKeyboard 按钮）
    confirm_text = f"""🔔 【渡劫小程序新留言】
━━━━━━━━━━━━━━━━━━
👤 用户: {user_openid[:12]}...
⏰ 时间: {time_str}
💬 留言:
{content}
━━━━━━━━━━━━━━━━━━
🤖 AI 回复建议:
{ai_reply}
━━━━━━━━━━━━━━━━━━

请审核以上回复，点击下方按钮确认发送或拒绝："""
    
    # 使用 InlineKeyboard
    import urllib.parse
    import urllib.request
    import json
    
    url = TELEGRAM_API_URL + "/sendMessage"
    
    # 按钮数据 URL 编码
    confirm_data = f"ferryman:confirm:{user_openid}"
    reject_data = f"ferryman:reject:{user_openid}"
    
    payload = {
        "chat_id": admin_chat_id,
        "text": confirm_text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({
            "inline_keyboard": [[
                {"text": "✅ 确认发送", "callback_data": confirm_data},
                {"text": "❌ 拒绝", "callback_data": reject_data}
            ]]
        })
    }
    
    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                return {"ok": True, "message": "已发送审核通知", "pending_id": user_openid}
    except Exception as e:
        print(f"[Telegram Error] {e}")
    
    return {"ok": True, "message": "通知发送中...", "ai_reply": ai_reply}


# ============== 文件存储的待确认回复 ==============
import json
import uuid
import os

PENDING_FILE = "/tmp/ferryman_pending_replies.json"

def save_pending_reply(user_openid: str, data: dict):
    """保存待确认的回复到文件"""
    all_pending = load_all_pending()
    all_pending[user_openid] = data
    try:
        with open(PENDING_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_pending, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[保存失败] {e}")

def load_pending_reply(user_openid: str) -> Optional[dict]:
    """读取待确认的回复"""
    all_pending = load_all_pending()
    return all_pending.get(user_openid)

def delete_pending_reply(user_openid: str):
    """删除待确认的回复"""
    all_pending = load_all_pending()
    if user_openid in all_pending:
        del all_pending[user_openid]
        try:
            with open(PENDING_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_pending, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[删除失败] {e}")

def load_all_pending() -> dict:
    """加载所有待确认回复"""
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


async def generate_ferryman_reply(user_message: str) -> str:
    """生成渡劫小程序摆渡人回复建议"""
    system_prompt = """你是渡劫情绪急救站小程序的「摆渡人」AI 助手。

渡劫是一个为家长提供情绪支持和心理疏导的平台。
当家长向你倾诉养育压力、育儿焦虑、情绪困扰时：
1. 先共情，表达理解和接纳
2. 给予温暖、正向的支持和鼓励
3. 适当给出情绪舒缓的小建议
4. 语气要温柔、亲切、像朋友聊天
5. 回复控制在 100-200 字内

注意：不要给专业的医疗或心理咨询建议，只做情绪陪伴和疏导。"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    reply = await call_qwen(messages, max_tokens=500)
    return reply


async def answer_callback(callback_id: str):
    """回答 Telegram 回调（消除加载动画）"""
    import urllib.request
    import urllib.parse
    import json
    
    url = TELEGRAM_API_URL + "/answerCallbackQuery"
    payload = {"callback_query_id": callback_id}
    data = urllib.parse.urlencode(payload).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=5):
            pass
    except:
        pass


async def edit_message_with_buttons(chat_id: str, message_id: int, text: str, buttons: list):
    """编辑消息（移除按钮或更新内容）"""
    import urllib.request
    import urllib.parse
    import json
    
    clean = ''.join(c if c.isprintable() or c == '\n' else '' for c in text)
    if len(clean) > 4000:
        clean = clean[:4000] + "..."
    
    url = TELEGRAM_API_URL + "/editMessageText"
    payload = {
        "chat_id": str(chat_id),
        "message_id": message_id,
        "text": clean,
        "parse_mode": "Markdown"
    }
    
    if buttons:
        payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    
    data = urllib.parse.urlencode(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    
    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception as e:
        print(f"[Edit Error] {e}")


async def save_ferryman_reply(user_openid: str, reply_content: str) -> bool:
    """
    保存已确认的回复到本地文件和微信云数据库
    """
    import json
    from datetime import datetime

    # 获取待确认的原始数据
    pending = load_pending_reply(user_openid)
    user_message = pending.get("content", "") if pending else ""
    timestamp = pending.get("timestamp", "") if pending else ""

    # 生成唯一 ID
    record_id = f"{user_openid}_{int(time.time() * 1000)}"

    # 记录数据
    record = {
        "id": record_id,
        "user_openid": user_openid,
        "user_message": user_message,
        "reply_content": reply_content,
        "created_at": datetime.now().isoformat(),
        "original_timestamp": timestamp
    }
    
    # 1. 保存到本地文件
    save_to_local_file(record)
    
    # 2. 保存到微信云数据库（如果配置了）
    cloud_result = await save_to_wechat_cloud(record)
    
    print(f"[渡劫] 回复已保存 - user={user_openid}, local=✓, cloud={'✓' if cloud_result else '✗'}")
    return True


def save_to_local_file(record: dict):
    """保存记录到本地 JSON 文件"""
    import os
    local_file = "/tmp/ferryman_messages.json"
    
    messages = []
    if os.path.exists(local_file):
        try:
            with open(local_file, 'r', encoding='utf-8') as f:
                messages = json.load(f)
        except:
            messages = []
    
    messages.append(record)
    
    # 只保留最近 1000 条
    if len(messages) > 1000:
        messages = messages[-1000:]
    
    try:
        with open(local_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[本地存储失败] {e}")


async def save_to_wechat_cloud(record: dict) -> bool:
    """
    保存到微信云数据库
    """
    WECHAT_APP_ID = "wx431ef83ab7fbe533"
    WECHAT_APP_SECRET = "23dec4694b4e2454fb8baff7a47befc5"
    env_id = "cloud1-7gs23ruwa46856c7"
    
    try:
        import urllib.request
        import urllib.parse
        import time
        
        # 1. 获取 access_token
        token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={WECHAT_APP_ID}&secret={WECHAT_APP_SECRET}"
        
        with urllib.request.urlopen(token_url, timeout=10) as resp:
            token_result = json.loads(resp.read().decode())
        
        if "access_token" not in token_result:
            print(f"[微信云] 获取token失败: {token_result}")
            return False
        
        access_token = token_result["access_token"]
        
        # 2. 保存到云数据库
        db_url = f"https://api.weixin.qq.com/tcb/databaseadd?access_token={access_token}"
        
        # 先构建内部 data 对象，然后对整个 query 字符串进行 json.dumps
        data_obj = {
            "user_openid": record['user_openid'],
            "user_message": record['user_message'],
            "reply_content": record['reply_content'],
            "created_at": record['created_at'],
            "status": "replied"
        }
        
        # 构建 query 字符串（云数据库的查询语句）
        query_str = "db.collection('ferryman_messages').add({data: " + json.dumps(data_obj, ensure_ascii=False) + "})"
        
        # 整个 payload 再用 json.dumps 编码，确保特殊字符正确转义
        payload = {
            "env": env_id,
            "query": query_str
        }
        
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(db_url, data=data, method='POST')
        req.add_header("Content-Type", "application/json")
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            if result.get("errcode") == 0:
                print(f"[微信云] 保存成功，ID: {result.get('id_list')}")
                return True
            else:
                print(f"[微信云] 保存失败: {result}")
                return False
    except Exception as e:
        print(f"[微信云] 保存异常: {e}")
        return False


async def notify_user_via_telegram(user_openid: str, reply_content: str) -> bool:
    """
    通过 Bot 通知用户有新的回复
    用户可以在小程序内查看完整对话
    """
    import urllib.request
    import urllib.parse
    import json
    
    # 暂时：直接通知管理员回复已发送
    # 实际：需要通过云数据库查询用户的 chat_id
    # 这里我们可以把回复存到一个共享位置，Bot 通知管理员去处理
    print(f"[渡劫] 用户 {user_openid} 收到回复: {reply_content[:30]}...")
    
    return True


@app.post("/daily-report")
async def generate_daily_report(chat_id: str = None):
    """生成每日热门服务报告"""
    print("[每日报告] 开始生成...")
    
    # 构建分析请求
    analyst = AI_TEAM["📊 情报分析师"]
    messages = [
        {"role": "system", "content": analyst["system"]},
        {"role": "user", "content": "请分析今日闲鱼热门服务，列出：\n1. TOP10热门服务（含销量估算和均价）\n2. 高需求低竞争的蓝海赛道\n3. 今日值得上架的新商品建议（3-5个）"}
    ]
    
    # 调用 AI 分析
    response = await call_qwen(messages, max_tokens=1500)
    
    report = f"""📊 【闲鱼每日热门服务报告】
━━━━━━━━━━━━━━━━━━
{response}
━━━━━━━━━━━━━━━━━━
💡 提示：以上内容由 AI 分析生成，仅供参考，请结合实际情况选择上架商品。
"""
    
    # 如果提供了 chat_id，发送报告到 Telegram
    if chat_id:
        await send_message(chat_id, report)
        return {"ok": True, "report": report}
    
    return {"ok": True, "report": report}


@app.post("/generate-product")
async def generate_product(
    service_type: str,
    chat_id: str = None
):
    """根据服务类型生成商品信息"""
    print(f"[生成商品] 类型: {service_type}")
    
    planner = AI_TEAM["🎨 商品策划师"]
    messages = [
        {"role": "system", "content": planner["system"]},
        {"role": "user", "content": f"请为「{service_type}」这个服务设计一个完整的闲鱼商品详情页，包括：商品标题、描述、价格、标签、吸引人的文案。"}
    ]
    
    response = await call_qwen(messages, max_tokens=1000)
    
    if chat_id:
        await send_message(chat_id, f"🎨 【商品策划】\n\n{response}")
        return {"ok": True}
    
    return {"ok": True, "product": response}


# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    import json
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
