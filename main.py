"""
Shawn AI Team Bot - 多 Agent 系统
真正的独立 Agent 架构，支持协作、记忆和主动任务
"""

import os
import json
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
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
app = FastAPI(title="Shawn AI Team Bot - Multi-Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Agent 消息系统 ==============
class MessageType(Enum):
    TASK = "task"           # 任务消息
    RESULT = "result"       # 结果消息
    QUERY = "query"         # 查询消息
    RESPONSE = "response"   # 响应消息
    BROADCAST = "broadcast" # 广播消息


@dataclass
class AgentMessage:
    """Agent 间通信消息"""
    id: str
    sender: str
    receivers: List[str]
    msg_type: MessageType
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class MessageBus:
    """Agent 消息总线"""
    
    def __init__(self):
        self.subscribers: Dict[str, asyncio.Queue] = {}
        self.message_history: List[AgentMessage] = []
        self.max_history = 1000
    
    def subscribe(self, agent_name: str) -> asyncio.Queue:
        """订阅消息"""
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = asyncio.Queue()
        return self.subscribers[agent_name]
    
    async def publish(self, message: AgentMessage):
        """发布消息"""
        self.message_history.append(message)
        if len(self.message_history) > self.max_history:
            self.message_history = self.message_history[-self.max_history:]
        
        for receiver in message.receivers:
            if receiver in self.subscribers:
                await self.subscribers[receiver].put(message)
        
        # 广播给所有人
        if "*" in self.subscribers:
            await self.subscribers["*"].put(message)
    
    def get_history(self, agent_name: str, limit: int = 50) -> List[AgentMessage]:
        """获取历史消息"""
        return [m for m in self.message_history if agent_name in m.receivers or "*" in m.receivers][-limit:]


# 全局消息总线
message_bus = MessageBus()


# ============== 记忆系统 ==============
class MemoryStore:
    """Agent 记忆存储"""
    
    def __init__(self):
        # 用户对话历史
        self.user_conversations: Dict[str, List[Dict]] = {}
        # Agent 知识库
        self.agent_knowledge: Dict[str, List[str]] = {}
        # 任务状态
        self.task_states: Dict[str, Dict] = {}
    
    def add_message(self, user_id: str, role: str, content: str):
        """添加对话消息"""
        if user_id not in self.user_conversations:
            self.user_conversations[user_id] = []
        self.user_conversations[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
        # 保留最近 100 条
        if len(self.user_conversations[user_id]) > 100:
            self.user_conversations[user_id] = self.user_conversations[user_id][-100:]
    
    def get_conversation(self, user_id: str, limit: int = 20) -> List[Dict]:
        """获取对话历史"""
        return self.user_conversations.get(user_id, [])[-limit:]
    
    def add_knowledge(self, agent_name: str, knowledge: str):
        """添加 Agent 知识"""
        if agent_name not in self.agent_knowledge:
            self.agent_knowledge[agent_name] = []
        self.agent_knowledge[agent_name].append(knowledge)
    
    def get_knowledge(self, agent_name: str) -> List[str]:
        """获取 Agent 知识"""
        return self.agent_knowledge.get(agent_name, [])
    
    def set_task_state(self, task_id: str, state: Dict):
        """设置任务状态"""
        self.task_states[task_id] = state
    
    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.task_states.get(task_id)


# 全局记忆存储
memory_store = MemoryStore()


# ============== 工具系统 ==============
class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, callable] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        self.register("web_search", self._web_search)
        self.register("calculate", self._calculate)
        self.register("get_time", self._get_time)
        self.register("send_message", self._send_message)
    
    def register(self, name: str, func: callable):
        """注册工具"""
        self.tools[name] = func
    
    def get_tools(self, agent_name: str) -> List[Dict]:
        """获取 Agent 可用的工具"""
        # 不同 Agent 有不同工具
        base_tools = ["get_time"]
        
        if agent_name == "数据分析师":
            return base_tools + ["calculate"]
        elif agent_name == "技术顾问":
            return base_tools + ["web_search"]
        elif agent_name == "小红书运营官":
            return base_tools + ["web_search"]
        else:
            return base_tools
    
    def execute(self, tool_name: str, **kwargs) -> Any:
        """执行工具"""
        if tool_name in self.tools:
            return asyncio.get_event_loop().run_until_complete(
                self.tools[tool_name](**kwargs)
            )
        return {"error": f"Tool {tool_name} not found"}
    
    async def _web_search(self, query: str) -> Dict:
        """搜索工具（模拟）"""
        return {"result": f"搜索结果: {query}", "source": "web"}
    
    async def _calculate(self, expression: str) -> Dict:
        """计算工具"""
        try:
            result = eval(expression)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def _get_time(self) -> Dict:
        """获取时间"""
        return {"time": datetime.now().isoformat()}
    
    async def _send_message(self, chat_id: str, text: str) -> Dict:
        """发送消息"""
        await send_telegram_message(chat_id, text)
        return {"sent": True}


# 全局工具注册表
tool_registry = ToolRegistry()


# ============== Agent 基类 ==============
class BaseAgent:
    """Agent 基类"""
    
    def __init__(self, name: str, emoji: str, description: str):
        self.name = name
        self.emoji = emoji
        self.description = description
        self.system_prompt = self._get_system_prompt()
        self.inbox: asyncio.Queue = message_bus.subscribe(name)
        self.tools = tool_registry.get_tools(name)
    
    def _get_system_prompt(self) -> str:
        """获取系统提示"""
        return f"你是 {self.name}，{self.description}"
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        raise NotImplementedError
    
    async def think(self, user_message: str, context: List[Dict]) -> str:
        """让 AI 思考"""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(context)
        messages.append({"role": "user", "content": user_message})
        
        return await call_qwen_api(messages)
    
    async def run(self):
        """运行 Agent"""
        while True:
            try:
                message = await self.inbox.get()
                response = await self.process_message(message)
                if response:
                    await message_bus.publish(response)
            except Exception as e:
                print(f"[{self.name}] Error: {e}")
                await asyncio.sleep(1)


# ============== 专家 Agent ==============
class ExpertAgent(BaseAgent):
    """专家 Agent"""
    
    def __init__(self, name: str, emoji: str, description: str, expertise: str, tools: List[str] = None):
        super().__init__(name, emoji, description)
        self.expertise = expertise
        if tools:
            self.tools = tools + ["get_time"]
    
    def _get_system_prompt(self) -> str:
        """获取专家系统提示"""
        knowledge = memory_store.get_knowledge(self.name)
        knowledge_text = "\n".join([f"- {k}" for k in knowledge]) if knowledge else "暂无专业知识积累"
        
        return f"""你是 {self.name} {self.emoji}
{description}

你的专业领域：{self.expertise}

你的知识库：
{knowledge_text}

能力特点：
- 专注在你的专业领域
- 可以主动向其他 Agent 提问或协作
- 会主动学习和积累知识
- 使用 {', '.join(self.tools)} 等工具
"""
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理任务消息"""
        if message.msg_type != MessageType.TASK:
            return None
        
        context = []
        if message.metadata.get("user_id"):
            context = memory_store.get_conversation(message.metadata["user_id"])
        
        # AI 思考
        response_text = await self.think(message.content, context)
        
        # 记住这次对话
        if message.metadata.get("user_id"):
            memory_store.add_message(message.metadata["user_id"], "assistant", response_text)
        
        return AgentMessage(
            id=f"result_{message.id}",
            sender=self.name,
            receivers=[message.sender],
            msg_type=MessageType.RESULT,
            content=response_text,
            metadata={
                "original_task": message.id,
                "user_id": message.metadata.get("user_id")
            }
        )


# ============== Orchestrator Agent ==============
class OrchestratorAgent(BaseAgent):
    """调度 Agent - 负责任务分析和分配"""
    
    def __init__(self):
        super().__init__(
            name="AI中枢",
            emoji="🤖",
            description="Shawn的私人AI助手，聪明、高效、有个性，负责协调团队工作"
        )
        self.team_members = {
            "小红书运营官": "🎨",
            "数据分析师": "📊",
            "智能客服": "💬",
            "技术顾问": "💻"
        }
    
    def _get_system_prompt(self) -> str:
        """获取调度系统提示"""
        team_info = "\n".join([f"- {e} {name}" for name, e in self.team_members.items()])
        
        return f"""你是 {self.name} {self.emoji}
{self.description}

你的团队成员：
{team_info}

你的职责：
1. 分析用户需求，判断需要哪个专家处理
2. 复杂任务分解为多个子任务，分配给不同专家
3. 协调多 Agent 协作，确保结果质量
4. 当需要多个专家时，发起并行处理
5. 整合各专家结果，给用户完整答案

决策规则：
- 简单问题直接回答
- 需要专业知识的问题，分配给对应专家
- 复杂问题分解后并行处理
- 保持对话上下文和记忆
"""
    
    async def classify_intent(self, message: str) -> Dict:
        """意图分类"""
        classification_prompt = f"""分析用户消息，确定意图和最佳处理方式。

用户消息：{message}

选项：
1. DIRECT - 直接回答，不需要专家
2. 小红书运营官 - 内容创作、推广相关
3. 数据分析师 - 数据、统计、分析相关
4. 智能客服 - 问题咨询、功能使用
5. 技术顾问 - 代码、开发、技术问题
6. COLLABORATIVE - 需要多个专家协作

只输出选项编号和简短理由。"""

        messages = [
            {"role": "system", "content": "你是意图分类专家"},
            {"role": "user", "content": classification_prompt}
        ]
        
        result = await call_qwen_api(messages)
        return {"raw": result}
    
    async def decompose_task(self, task: str) -> List[Dict]:
        """任务分解"""
        decomposition_prompt = f"""将复杂任务分解为多个子任务。

任务：{task}

输出格式（JSON数组）：
[
  {{"agent": "专家名称", "subtask": "子任务描述", "priority": 1-3}}
]

如果任务简单，返回空数组。"""

        messages = [
            {"role": "system", "content": "你是任务分解专家"},
            {"role": "user", "content": decomposition_prompt}
        ]
        
        result = await call_qwen_api(messages)
        return {"subtasks": result}
    
    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        """处理消息"""
        if message.msg_type == MessageType.TASK:
            user_message = message.content
            user_id = message.metadata.get("user_id")
            
            # 意图分类
            intent = await self.classify_intent(user_message)
            
            # 获取上下文
            context = memory_store.get_conversation(user_id) if user_id else []
            
            # 根据意图处理
            raw_result = intent.get("raw", "").upper()
            
            if "COLLABORATIVE" in raw_result or "协作" in raw_result:
                # 需要多 Agent 协作
                return await self._handle_collaborative(user_message, message, context)
            elif any(kw in raw_result for kw in ["小红书", "运营", "内容", "爆款"]):
                return await self._delegate_to_agent("小红书运营官", user_message, message, context)
            elif any(kw in raw_result for kw in ["数据", "分析", "统计"]):
                return await self._delegate_to_agent("数据分析师", user_message, message, context)
            elif any(kw in raw_result for kw in ["代码", "开发", "技术", "bug"]):
                return await self._delegate_to_agent("技术顾问", user_message, message, context)
            elif any(kw in raw_result for kw in ["客服", "问题", "咨询"]):
                return await self._delegate_to_agent("智能客服", user_message, message, context)
            else:
                # 默认直接回答
                return await self._direct_response(user_message, message, context)
        
        return None
    
    async def _direct_response(self, message: str, original_msg: AgentMessage, context: List[Dict]) -> AgentMessage:
        """直接回答"""
        response_text = await self.think(message, context)
        
        return AgentMessage(
            id=f"result_{original_msg.id}",
            sender=self.name,
            receivers=[original_msg.sender],
            msg_type=MessageType.RESULT,
            content=response_text,
            metadata={"user_id": original_msg.metadata.get("user_id")}
        )
    
    async def _delegate_to_agent(self, agent_name: str, message: str, original_msg: AgentMessage, context: List[Dict]) -> AgentMessage:
        """委托给专家 Agent"""
        emoji = self.team_members.get(agent_name, "📋")
        
        # 创建任务消息
        task_msg = AgentMessage(
            id=f"task_{original_msg.id}",
            sender=self.name,
            receivers=[agent_name],
            msg_type=MessageType.TASK,
            content=message,
            metadata={
                "user_id": original_msg.metadata.get("user_id"),
                "context": context
            }
        )
        await message_bus.publish(task_msg)
        
        # 直接给出初始响应
        initial_response = await self.think(
            f"用户询问了关于【{agent_name}】领域的问题。\n\n问题：{message}\n\n请给出专业的初始回答，并说明正在为您安排专家处理。",
            context
        )
        
        return AgentMessage(
            id=f"result_{original_msg.id}",
            sender=self.name,
            receivers=[original_msg.sender],
            msg_type=MessageType.RESULT,
            content=f"{emoji} 已转交给 {agent_name} 处理\n\n{initial_response}",
            metadata={"user_id": original_msg.metadata.get("user_id")}
        )
    
    async def _handle_collaborative(self, message: str, original_msg: AgentMessage, context: List[Dict]) -> AgentMessage:
        """处理协作任务"""
        # 分解任务
        decomposition = await self.decompose_task(message)
        
        # 广播给所有相关专家
        for agent_name in self.team_members.keys():
            task_msg = AgentMessage(
                id=f"task_{original_msg.id}_{agent_name}",
                sender=self.name,
                receivers=[agent_name],
                msg_type=MessageType.TASK,
                content=f"团队协作任务：{message}",
                metadata={"user_id": original_msg.metadata.get("user_id")}
            )
            await message_bus.publish(task_msg)
        
        # 给出协调响应
        response = await self.think(
            f"收到复杂协作任务，正在协调多个专家处理...\n\n任务：{message}\n\n请说明您正在组织团队协作。",
            context
        )
        
        return AgentMessage(
            id=f"result_{original_msg.id}",
            sender=self.name,
            receivers=[original_msg.sender],
            msg_type=MessageType.RESULT,
            content=f"🤝 团队协作模式启动\n\n{response}",
            metadata={"user_id": original_msg.metadata.get("user_id")}
        )


# ============== 初始化 Agent 团队 ==============
orchestrator = OrchestratorAgent()

team_agents = {
    "小红书运营官": ExpertAgent(
        name="小红书运营官",
        emoji="🎨",
        description="资深小红书运营专家",
        expertise="内容创作、爆款笔记、种草推广、标题优化",
        tools=["web_search"]
    ),
    "数据分析师": ExpertAgent(
        name="数据分析师",
        emoji="📊",
        description="数据分析专家",
        expertise="数据统计、趋势分析、用户增长、转化分析",
        tools=["calculate"]
    ),
    "智能客服": ExpertAgent(
        name="智能客服",
        emoji="💬",
        description="专业客服代表",
        expertise="问题解答、用户咨询、功能介绍、投诉处理"
    ),
    "技术顾问": ExpertAgent(
        name="技术顾问",
        emoji="💻",
        description="全栈技术专家",
        expertise="代码开发、bug修复、架构设计、技术选型",
        tools=["web_search"]
    ),
    "AI中枢": orchestrator
}


# ============== Agent 协作者 ==============
class AgentCollaborator:
    """Agent 协作管理器"""
    
    def __init__(self):
        self.pending_tasks: Dict[str, asyncio.Future] = {}
    
    async def request_agent_help(self, from_agent: str, to_agent: str, question: str, user_id: str = None) -> str:
        """请求其他 Agent 帮助"""
        task_id = f"{from_agent}_to_{to_agent}_{datetime.now().timestamp()}"
        
        # 创建查询消息
        query_msg = AgentMessage(
            id=task_id,
            sender=from_agent,
            receivers=[to_agent],
            msg_type=MessageType.QUERY,
            content=question,
            metadata={"user_id": user_id}
        )
        
        # 创建 Future 等待结果
        future = asyncio.Future()
        self.pending_tasks[task_id] = future
        
        # 发布消息
        await message_bus.publish(query_msg)
        
        # 等待结果（超时 60 秒）
        try:
            result = await asyncio.wait_for(future, timeout=60.0)
            return result
        except asyncio.TimeoutError:
            return "抱歉，Agent 协作超时"
        finally:
            self.pending_tasks.pop(task_id, None)
    
    def complete_task(self, task_id: str, result: str):
        """完成任务"""
        if task_id in self.pending_tasks:
            self.pending_tasks[task_id].set_result(result)


collaborator = AgentCollaborator()


# ============== LLM 调用 ==============
async def call_qwen_api(messages: List[Dict], model: str = None) -> str:
    """调用通义千问 API"""
    headers = {
        "Authorization": "Bearer " + QWEN_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model or QWEN_MODEL,
        "messages": messages,
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(QWEN_API_URL, headers=headers, json=payload)
            print("[Qwen] API:", response.status_code)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("[Qwen] Error:", e)
        return f"API 调用失败: {str(e)}"


# ============== 文本清理 ==============
def clean_text(text: str) -> str:
    """清理文本"""
    result = []
    for c in text:
        if c.isprintable() or c == '\n':
            result.append(c)
    text = ''.join(result)
    if len(text) > 4000:
        text = text[:4000] + "..."
    return text


# ============== Telegram 发送 ==============
async def send_telegram_message(chat_id: str, text: str):
    """发送 Telegram 消息"""
    clean_content = clean_text(text)
    url = TELEGRAM_API_URL + "/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": str(chat_id),
        "text": clean_content
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            print("Telegram 发送:", resp.status)
    except Exception as e:
        print("Telegram 发送失败:", e)


# ============== Agent 任务处理器 ==============
async def process_agent_result(message: AgentMessage):
    """处理 Agent 返回的结果"""
    if message.msg_type == MessageType.RESULT:
        # 如果是发给用户的结果，发送到 Telegram
        user_id = message.metadata.get("user_id")
        if user_id:
            # 存储到记忆
            memory_store.add_message(user_id, "assistant", message.content)
        
        # 发送给原始请求者
        for receiver in message.receivers:
            if receiver == "user" and message.metadata.get("user_id"):
                await send_telegram_message(
                    message.metadata["user_id"],
                    message.emoji if hasattr(message, 'emoji') else "" + message.content
                )


# ============== 异步任务处理 ==============
async def agent_result_listener():
    """监听 Agent 结果"""
    inbox = message_bus.subscribe("*")  # 订阅所有消息
    
    while True:
        try:
            message = await inbox.get()
            if message.msg_type in [MessageType.RESULT, MessageType.RESPONSE]:
                await process_agent_result(message)
        except Exception as e:
            print("[Listener] Error:", e)
            await asyncio.sleep(1)


# ============== 主动任务系统 ==============
class ProactiveTaskManager:
    """主动任务管理器"""
    
    def __init__(self):
        self.tasks: List[Dict] = []
        self.running = False
    
    def add_task(self, name: str, schedule: str, action: callable):
        """添加定时任务"""
        self.tasks.append({
            "name": name,
            "schedule": schedule,
            "action": action,
            "last_run": None
        })
    
    async def run_pending_tasks(self):
        """检查并执行待运行任务"""
        # TODO: 实现定时任务调度
        pass


proactive_manager = ProactiveTaskManager()


# ============== 路由 ==============
@app.get("/")
async def root():
    """根路由"""
    return {
        "status": "ok",
        "bot": "Shawn AI Team Bot",
        "version": "4.0.0",
        "architecture": "Multi-Agent",
        "agents": [
            {"name": name, "emoji": agent.emoji, "description": agent.description}
            for name, agent in team_agents.items()
        ]
    }


@app.post("/telegram")
async def telegram_webhook(request: Request):
    """Telegram Webhook"""
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
    
    message = body.get("message", {})
    if not message:
        return {"ok": True}
    
    # 忽略机器人消息
    if message.get("from", {}).get("is_bot"):
        return {"ok": True}
    
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    user_id = str(chat_id)  # 使用 chat_id 作为用户标识
    
    if not text or not chat_id:
        return {"ok": True}
    
    print(f"[收到消息] {text}")
    
    # 存储用户消息
    memory_store.add_message(user_id, "user", text)
    
    # 创建任务消息
    task_msg = AgentMessage(
        id=f"task_{datetime.now().timestamp()}",
        sender="user",
        receivers=["AI中枢"],
        msg_type=MessageType.TASK,
        content=text,
        metadata={"user_id": user_id}
    )
    
    # 处理任务（同步方式，简化处理）
    response = await orchestrator.process_message(task_msg)
    
    if response:
        await send_telegram_message(chat_id, response.content)
    
    return {"ok": True}


@app.get("/team")
async def show_team():
    """显示团队状态"""
    return {
        "team": [
            {
                "name": name,
                "emoji": agent.emoji,
                "description": agent.description,
                "tools": agent.tools
            }
            for name, agent in team_agents.items()
        ],
        "memory_stats": {
            "users": len(memory_store.user_conversations),
            "knowledge_entries": sum(len(v) for v in memory_store.agent_knowledge.values())
        }
    }


@app.get("/memory/{user_id}")
async def get_user_memory(user_id: str):
    """获取用户记忆"""
    return {
        "user_id": user_id,
        "conversation": memory_store.get_conversation(user_id)
    }


@app.post("/memory/{user_id}")
async def add_user_memory(user_id: str, role: str, content: str):
    """添加用户记忆"""
    memory_store.add_message(user_id, role, content)
    return {"ok": True}


# ============== 启动 ==============
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
