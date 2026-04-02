# Shawn AI Team Bot 🤖

AI 团队中枢 Bot - 消息分发器（OpenClaw Gateway 驱动）

## 功能

- 🎯 **意图识别**：根据关键词自动分配最合适的 AI 角色
- 👥 **多角色团队**：小红书运营、数据分析、客服、技术顾问、AI中枢
- 🔄 **模型路由**：通过 OpenClaw Gateway 统一调度模型

## 架构

```
用户消息 → Telegram Bot → 意图识别 → 自动分配角色
                                        ↓
        ┌───────────┬───────────┬───────────┬───────────┐
        ↓           ↓           ↓           ↓           ↓
    🎨 小红书     📊 数据      💬 客服      💻 技术      🤖 AI中枢
       运营官      分析师                    顾问       (兜底)
        ↓           ↓           ↓           ↓           ↓
        └───────────┴───────────┴───────────┴───────────┘
                                ↓
                        OpenClaw Gateway
                        (modelroute 模型路由)
```

## AI 团队角色

| 角色 | 触发关键词 | 专长 |
|------|-----------|------|
| 🎨 小红书运营官 | 小红书、笔记、文案、爆款、种草 | 爆款内容创作、账号运营 |
| 📊 数据分析师 | 分析、数据、报告、趋势、转化 | 数据洞察、运营复盘 |
| 💬 智能客服 | 客服、投诉、退款、帮助、反馈 | 用户问题解答、投诉处理 |
| 💻 技术顾问 | 代码、报错、bug、部署、API | 技术问题排查、代码示例 |
| 🤖 AI中枢 | (兜底) | 通用问题、统筹协调 |

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENCLAW_GATEWAY_URL` | OpenClaw Gateway 地址 | `http://127.0.0.1:28789` |
| `OPENCLAW_API_KEY` | Gateway auth token | `openclaw-default-token` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | (已配置) |
| `PORT` | Bot 服务端口 | `8000` |

## API 接口

### Webhook 通用接口
```
POST /webhook
{
  "message": "写一篇小红书文案",
  "user_id": "user123"
}
```

### QQ 机器人接口
```
POST /qq
{
  "message": "...",
  "user_id": "...",
  "group_id": "..."
}
```

### 飞书机器人接口
```
POST /feishu
{
  "event": {
    "text": "...",
    "sender": {"user_id": "..."}
  }
}
```

## 本地运行

```bash
cd bot
pip install -r requirements.txt
uvicorn bot.main:app --reload --port 8000
```
