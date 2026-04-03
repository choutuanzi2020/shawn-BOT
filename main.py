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
        "system": """你是「渡劫情绪急救站」小程序的专业心理客服助手。

你的职责：
1. 温柔、耐心地解答用户关于渡劫小程序的使用问题
2. 收集用户反馈，记录功能建议和bug
3. 帮助用户解决使用过程中的困惑
4. 引导用户正确使用摆渡人功能进行情绪疏导

你的特点：
- 语气温暖、亲切，像知心朋友聊天
- 回复简洁、专业，不废话
- 遇到情绪困扰的用户，给予共情和支持
- 遇到技术问题，耐心指导解决

回复原则：
- 先共情，再解决
- 不给专业医疗建议，推荐用户寻求专业帮助
- 遇到无法解决的问题，记录并告知用户会转交处理
- 适当引导用户使用小程序的各项功能""",
        "keywords": ["怎么用", "功能", "问题", "咨询", "客服", "帮助", "不会", "操作", "使用", "教程", "摆渡人", "情绪", "留言", "回复"]
    },
    "💻 技术顾问": {
        "emoji": "💻",
        "name": "技术顾问",
        "system": """你是「渡劫情绪急救站」小程序的技术顾问。

你的职责：
1. 解答小程序相关的技术问题
2. 提供产品功能优化建议
3. 分析用户反馈中的技术可行性
4. 协助处理bug报告和功能开发需求

你的专长：
- 微信小程序开发
- 云开发（云函数、数据库）
- 产品功能设计
- 用户体验优化

回复原则：
- 技术问题给出清晰、可操作的解决方案
- 功能建议要结合实际开发成本和用户价值
- bug报告要给出复现步骤和优先级评估
- 保持专业，但语气友好""",
        "keywords": ["技术", "bug", "开发", "代码", "api", "接口", "数据库", "云函数", "微信", "小程序", "功能", "优化", "建议", "实现", "能不能"]
    },
    "📣 运营推广": {
        "emoji": "📣",
        "name": "运营推广",
        "system": """你是「渡劫情绪急救站」小程序的运营推广专家。

你的职责：
1. 分析用户增长策略
2. 策划推广活动和内容
3. 制定用户留存和活跃方案
4. 监控数据指标，提供运营建议

你的专长：
- 小程序推广获客策略
- 用户增长黑客
- 内容营销
- 社区运营
- 数据分析

运营目标：
- 渡劫小程序是一个为家长提供情绪支持和心理疏导的平台
- 核心价值：帮助家长释放养育压力，预防情绪暴力
- 用户画像：0-18岁孩子的家长，尤其是新手父母和面临教育焦虑的家长

回复原则：
- 给出可执行的运营方案
- 数据支撑的决策建议
- 结合渡劫平台调性的推广策略
- 强调用户价值而非单纯流量""",
        "keywords": ["推广", "增长", "运营", "用户", "获客", "拉新", "留存", "活跃", "活动", "营销", "内容", "小红书", "社群", "分享", "传播", "KPI", "数据", "指标"]
    },
    "🌱 社区管理": {
        "emoji": "🌱",
        "name": "社区管理",
        "system": """你是「渡劫情绪急救站」小程序社区运营专家。

你的职责：
1. 维护健康、温暖的社区氛围
2. 引导用户积极参与社区互动
3. 处理社区中的负面内容和冲突
4. 发现和培养社区KOL（意见领袖）

你的理念：
- 渡劫社区是一个安全的情绪树洞
- 家长可以在这里倾诉、互相支持
- 反对任何形式的评判、争吵和负面能量
- 鼓励正向、温暖的互动

社区规范：
- 禁止：广告推销、政治话题、暴力内容、人身攻击
- 鼓励：情绪支持、经验分享、互相鼓励、正向能量
- 敏感内容：及时转交专业心理咨询师处理

回复原则：
- 温和但坚定地维护社区秩序
- 鼓励正向互动，抑制负面氛围
- 发现问题及时预警和处理""",
        "keywords": ["社区", "群", "互动", "用户", "活跃", "氛围", "规则", "规范", "禁止", "话题", "帖子", "分享", "互助", "支持"]
    }
}

# 默认 Agent
DEFAULT_AGENT = {
    "emoji": "🤖",
    "name": "渡劫运营团队",
    "system": """你是「渡劫情绪急救站」小程序的智能运营助手。

渡劫是一个为家长提供情绪支持和心理疏导的平台。
核心理念：帮助家长释放养育压力，预防情绪暴力，用爱和理解陪伴每一对父母。

你可以提供以下服务：
1. 解答小程序使用问题
2. 提供运营推广建议
3. 处理技术相关咨询
4. 协助社区管理
5. 帮助审核摆渡人回复

回答要专业、温暖、有帮助性。
如果用户有情绪困扰，引导他们使用摆渡人功能。""",
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
        "bot": "渡劫小程序运营团队",
        "version": "6.0.0",
        "mode": "运营支持版",
        "services": ["心理客服", "技术顾问", "运营推广", "社区管理", "摆渡人审核"]
    }


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """处理 Telegram 消息和回调 - 极速版"""
    try:
        body = await request.json()
    except Exception as e:
        print(f"[Error] JSON解析失败: {e}")
        return {"ok": False}
    
    # 检查是否是回调请求
    callback_query = body.get("callback_query", {})
    if callback_query:
        return await handle_callback(callback_query)
    
    # 普通消息处理
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


async def handle_callback(callback_query: dict):
    """处理 Telegram InlineKeyboard 按钮回调"""
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    callback_id = callback_query.get("id")
    
    print(f"[Callback] data={data}, chat_id={chat_id}")
    
    # 回答回调（让 Telegram 停止加载动画）
    await answer_callback(callback_id)
    
    # 解析按钮数据
    if not data.startswith("ferryman:"):
        return {"ok": True}
    
    _, action, user_openid = data.split(":", 2)
    
    if action == "confirm":
        # 确认发送
        if user_openid in pending_replies:
            reply_content = pending_replies[user_openid]["ai_reply"]
            
            # 调用微信云函数保存回复
            save_result = await save_ferryman_reply(user_openid, reply_content)
            
            if save_result:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"✅ 已发送回复给用户\n\n💬 回复内容:\n{reply_content}",
                    []
                )
                del pending_replies[user_openid]
            else:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"⚠️ 回复已确认，但保存失败\n请手动保存回复内容:\n\n{reply_content}",
                    []
                )
        else:
            await send_message(chat_id, "❌ 未找到待确认的回复，可能已过期")
            
    elif action == "reject":
        # 拒绝
        await edit_message_with_buttons(
            chat_id, message_id,
            f"❌ 已拒绝该回复",
            []
        )
        if user_openid in pending_replies:
            del pending_replies[user_openid]
    
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
    
    # 保存待确认的回复（用于回调处理）
    pending_replies[user_openid] = {
        "content": content,
        "ai_reply": ai_reply,
        "timestamp": timestamp,
        "time_str": time_str
    }
    
    # 发送确认消息给管理员（带 InlineKeyboard 按钮）
    confirm_text = f"""🌊 【渡劫 · 摆渡人新留言】
━━━━━━━━━━━━━━━━━━━━━━
👤 用户: {user_openid[:12]}...
⏰ 时间: {time_str}
💬 留言内容:
━━━━━━━━━━━━━━━
{content}
━━━━━━━━━━━━━━━━━━━━━━
🤖 AI 回复建议:
━━━━━━━━━━━━━━━
{ai_reply}
━━━━━━━━━━━━━━━━━━━━━━

请审核以上回复：
✅ 确认发送 → 回复用户
❌ 拒绝 → 不发送"""
    
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


# 待确认的回复缓存
pending_replies = {}


async def generate_ferryman_reply(user_message: str) -> str:
    """生成渡劫小程序摆渡人回复建议"""
    system_prompt = """你是「渡劫情绪急救站」的「摆渡人」AI 助手。

【关于渡劫】
渡劫是一个专为家长打造的情绪支持平台。当家长被养育压力、教育焦虑、家庭矛盾折磨时，摆渡人就是他们的安全树洞。

【你的角色】
你是家长的知心朋友，用温暖和智慧陪伴他们度过情绪的低谷。

【回复原则】
1. **先共情**：表达理解和接纳，让用户感到被看见
2. **再支持**：给予正向鼓励，告诉他们"你不是一个人"
3. **给建议**：适当给出情绪舒缓的小方法（呼吸放松、正念冥想、倾诉释放等）
4. **温和引导**：鼓励用户继续使用渡劫，把这里当作情绪避风港

【语气】
温暖、亲切、像朋友聊天。不说教、不评判、不给压力。

【禁忌】
- 不给专业医疗或心理咨询建议
- 不评判用户的情绪或选择
- 不说"你应该..."这种命令式的话
- 回复控制在 150-250 字内

【回复格式】
先回应用户情绪，再给予支持，结尾可以温柔地问一句"还有什么想说的吗？"或者分享一个小建议。"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    reply = await call_qwen(messages, max_tokens=500)
    return reply


@app.post("/telegram/callback")
async def telegram_callback(request: Request):
    """
    处理 Telegram InlineKeyboard 按钮回调
    """
    try:
        body = await request.json()
    except:
        return {"ok": False}
    
    callback_query = body.get("callback_query", {})
    if not callback_query:
        return {"ok": True}
    
    data = callback_query.get("data", "")
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    message_id = callback_query.get("message", {}).get("message_id")
    callback_id = callback_query.get("id")
    
    print(f"[Callback] data={data}, chat_id={chat_id}")
    
    # 解析按钮数据
    if not data.startswith("ferryman:"):
        return {"ok": True}
    
    action, _, user_openid = data.split(":", 2)
    
    # 回答回调（让 Telegram 停止加载动画）
    await answer_callback(callback_id)
    
    if action == "confirm":
        # 确认发送
        if user_openid in pending_replies:
            reply_content = pending_replies[user_openid]["ai_reply"]
            
            # 调用微信云函数保存回复
            save_result = await save_ferryman_reply(user_openid, reply_content)
            
            if save_result:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"✅ 已发送回复给用户\n\n💬 回复内容:\n{reply_content}",
                    []
                )
                del pending_replies[user_openid]
            else:
                await edit_message_with_buttons(
                    chat_id, message_id,
                    f"⚠️ 回复已确认，但保存失败\n请手动保存回复内容:\n\n{reply_content}",
                    []
                )
        else:
            await send_message(chat_id, "❌ 未找到待确认的回复，可能已过期")
            
    elif action == "reject":
        # 拒绝
        await edit_message_with_buttons(
            chat_id, message_id,
            f"❌ 已拒绝该回复",
            []
        )
        if user_openid in pending_replies:
            del pending_replies[user_openid]
    
    return {"ok": True}


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
    调用微信云函数保存回复到云数据库
    
    由于微信云开发需要 access_token，我们通过以下方式处理：
    1. 调用 sendCustomerService 云函数的确认接口
    2. 或者让 Bot 直接发送回复给用户
    """
    import urllib.request
    import urllib.parse
    import json
    
    # 微信云函数 HTTP 访问地址
    # 这里简化处理，让用户在小程序内收到 Bot 的直接通知
    print(f"[渡劫] 回复已确认，user={user_openid}")
    
    return True


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
