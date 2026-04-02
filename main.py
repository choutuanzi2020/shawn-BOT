"""
Shawn AI Team Bot
"""
import os
import urllib.request
import urllib.parse
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "sk-91fcc62518024138a8adf65ba3514775")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
QWEN_MODEL = "qwen-plus"

TELEGRAM_BOT_TOKEN = "8768169528:AAFFQzdG973w655DknEs3BFLkIiWvGqqwlI"
TELEGRAM_API_URL = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN

AI_TEAM = {
 "小红书运营官": {
 "emoji": "🎨",
 "system": "你是一位资深小红书运营专家，擅长创作爆款内容。为渡劫APP创作推广笔记。",
 "keywords": ["小红书", "笔记", "文案", "爆款", "标题", "种草", "写作", "推广"]
 },
 "数据分析师": {
 "emoji": "📊",
 "system": "你是一位数据分析专家，擅长从数据中发现规律。",
 "keywords": ["分析", "数据", "报告", "统计", "趋势", "增长", "用户", "转化"]
 },
 "智能客服": {
 "emoji": "💬",
 "system": "你是一位专业亲切的客服，善于解决用户问题。",
 "keywords": ["客服", "问题", "帮助", "咨询", "怎么用", "收费", "功能"]
 },
 "技术顾问": {
 "emoji": "💻",
 "system": "你是一位全栈技术专家，精通微信小程序开发。",
 "keywords": ["代码", "报错", "bug", "开发", "部署", "小程序", "云开发"]
 },
 "AI中枢": {
 "emoji": "🤖",
 "system": "你是Shawn的私人AI助手，聪明、高效、有个性。",
 "keywords": []
 }
}

app = FastAPI(title="Shawn AI Team Bot")

app.add_middleware(
 CORSMiddleware,
 allow_origins=["*"],
 allow_credentials=True,
 allow_methods=["*"],
 allow_headers=["*"],
)

def pick_agent(message):
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

async def call_llm(message, agent_name="AI中枢"):
 agent = AI_TEAM.get(agent_name, AI_TEAM["AI中枢"])
 emoji = agent["emoji"]
 system_prompt = agent["system"]
 headers = {
 "Authorization": "Bearer " + QWEN_API_KEY,
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
 print(f"[{agent_name}] API: {response.status_code}")
 response.raise_for_status()
 data = response.json()
 reply = data["choices"][0]["message"]["content"]
 return emoji + " " + agent_name + "\n\n" + reply
 except Exception as e:
 print(f"[{agent_name}] Error: {e}")
 return "Error: " + str(e)

def clean_text(text):
 result = []
 for c in text:
 if c.isprintable() or c == '\n':
 result.append(c)
 text = ''.join(result)
 if len(text) > 4000:
 text = text[:4000] + "..."
 return text

async def send_telegram_message(chat_id, text):
 clean_content = clean_text(text)
 url = TELEGRAM_API_URL + "/sendMessage"
 data = urllib.parse.urlencode({
 "chat_id": str(chat_id),
 "text": clean_content
 }).encode('utf-8')
 try
