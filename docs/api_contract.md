# CodeCoach API Contract

本文档描述当前前后端使用的稳定接口。开发环境还可以通过 `/docs` 查看 FastAPI 生成的 OpenAPI 页面。

相关文档：

| 文档 | 用途 |
|---|---|
| `README.md` | 安装、运行和验证入口 |
| `docs/architecture.md` | 系统边界和请求流程 |
| `docs/deployment.md` | Docker 与生产部署注意事项 |

## 1. Base URL

| 环境 | 地址 |
|---|---|
| 本地后端 | `http://localhost:8000` |
| 前端代理 | Vite 将 `/api` 和 `/health` 代理到 `http://localhost:8000` |

## 2. Health Check

```http
GET /health
```

响应：

```json
{ "status": "ok" }
```

## 3. Chat 主接口

所有智能体服务统一走 `/api/chat`。

```http
POST /api/chat
Content-Type: application/json
```

### 3.1 Request

```json
{
  "user_id": "demo_user",
  "user_level": "beginner",
  "mode": "debug",
  "message": "我这个代码为什么过不了？",
  "problem_text": "输入一个整数 n，输出 n。",
  "code": "#include <stdio.h>\nint main(){ int n; scanf(\"%d\", n); printf(\"%d\", n); return 0; }",
  "session_id": "session_001"
}
```

### 3.2 Request Fields

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `user_id` | string | 是 | 演示用户 ID，默认 `demo_user` |
| `user_level` | `beginner` \| `basic` \| `advanced` | 是 | 用户水平，用于控制解释深度 |
| `mode` | `auto` \| `knowledge` \| `problem` \| `hint` \| `debug` \| `data` \| `review` \| `followup` | 否 | 前端选择的服务类型。后端优先使用 `mode`，否则走 Router |
| `message` | string | 是 | 用户自然语言问题。无代码问知识、问数、追问都只需填这个字段 |
| `problem_text` | string | 否 | 题目文本。题目拆解、提示场景建议填写 |
| `code` | string | 否 | C 语言代码。只有代码纠错必填 |
| `session_id` | string | 否 | 会话 ID。多轮追问必须沿用同一个值 |

### 3.3 Mode Semantics

| `mode` | 用户看到的服务 | 后端目标意图 | 典型输入 |
|---|---|---|---|
| `auto` | 自动判断 | Router 决定 | 任意问题 |
| `knowledge` | 问一个知识点 | `KNOWLEDGE_QA` | `scanf 为什么要加 &？` |
| `problem` | 看不懂题目 | `UNDERSTAND_PROBLEM` | `这个题目的输入输出是什么意思？` |
| `hint` | 没思路，给我提示 | `NEED_HINT` | `先别告诉答案，给点提示。` |
| `debug` | 帮我检查代码 | `DEBUG_CODE` | `我这个代码为什么过不了？` + `code` |
| `data` | 查看学习数据 | `DATA_QA` | `我最近最常犯什么错误？` |
| `review` | 生成复盘 | `REVIEW_SUMMARY` | `帮我生成本次错误复盘。` |
| `followup` | 继续追问 | 结合上下文判断 | `为什么要传地址？` |

### 3.4 Response

完整 MVP 响应示例：

```json
{
  "session_id": "session_001",
  "turn_id": "turn_20260709_001",
  "is_follow_up": false,
  "conversation_title": "scanf 输入错误",
  "answer": "问题可能出在 scanf 这一行。scanf 读取普通变量时通常需要变量地址，所以 n 前面应检查是否缺少 &。",
  "intent": "DEBUG_CODE",
  "knowledge_type": "MEMORIZE",
  "knowledge_tags": ["C语言", "scanf", "输入", "取地址"],
  "similar_memory": {
    "matched": true,
    "title": "scanf 输入错误",
    "mistake_summary": "你之前在 scanf 中忘记给普通变量加 &。",
    "review_tip": "看到 scanf 读取普通变量，先检查参数是不是地址。",
    "score": 0.82
  },
  "review_card": {
    "id": "review_scanf_missing_address_001",
    "title": "scanf 输入错误",
    "error_type": "C语法错误",
    "knowledge_type": "MEMORIZE",
    "knowledge_tags": ["C语言", "scanf", "输入", "取地址"],
    "mistake_summary": "用户在 scanf 中忘记给普通变量加 &。",
    "review_tip": "读取普通变量时通常要传变量地址。",
    "remember_points": ["scanf 读取普通变量时通常要加 &"],
    "understand_points": ["scanf 需要变量地址，才能把输入值写回变量"],
    "common_mistakes": ["把 scanf(\"%d\", &n) 写成 scanf(\"%d\", n)", "混淆普通变量和数组名是否需要 &"],
    "next_review_at": "2026-07-10"
  },
  "next_actions": [
    { "label": "再讲简单点", "message": "再用更简单的话解释一下。", "mode": "followup" },
    { "label": "举个例子", "message": "能举一个更小的例子吗？", "mode": "followup" },
    { "label": "生成复盘", "message": "帮我生成本次错误复盘。", "mode": "review" }
  ],
  "agent_trace": [
    { "node": "Profile Agent", "status": "done", "detail": "beginner" },
    { "node": "Intent Router", "status": "done", "detail": "DEBUG_CODE" },
    { "node": "Code Analyzer", "status": "done", "detail": "scanf_missing_address" },
    { "node": "RAG Agent", "status": "done", "detail": "2 docs" },
    { "node": "Review Agent", "status": "done", "detail": "review card generated" },
    { "node": "Memory Agent", "status": "done", "detail": "review saved" }
  ]
}
```

### 3.5 Response Fields

| 字段 | 类型 | 当前兼容 | 前端用途 |
|---|---|---:|---|
| `session_id` | string | 新增 | 多轮会话 |
| `turn_id` | string | 新增 | 单轮消息 ID |
| `is_follow_up` | boolean | 新增 | 标识本轮是否追问 |
| `conversation_title` | string | 新增 | 对话标题 |
| `answer` | string | 已有 | 中间辅导回答 |
| `intent` | enum | 已有 | 映射为“本次服务” |
| `knowledge_type` | enum | 已有 | 映射为“学习策略” |
| `knowledge_tags` | string[] | 已有 | 相关知识点 |
| `similar_memory` | object | 已有，待扩展 | 历史相似错误提醒 |
| `review_card` | object | 已有，待扩展 | 本次错题档案 |
| `next_actions` | object[] | 新增 | 快捷追问按钮 |
| `agent_trace` | object[] | 已有 | 系统分析过程 |

前端必须兼容新增字段不存在的情况。

## 4. Enumerations

### 4.1 Intent

| 值 | 用户侧文案 | 说明 |
|---|---|---|
| `KNOWLEDGE_QA` | 知识讲解 | C 语言或算法知识问答 |
| `DATA_QA` | 学习数据分析 | 查询错题、薄弱点、复习计划 |
| `DEBUG_CODE` | 代码纠错 | 分析 C 代码常见错误 |
| `NEED_HINT` | 分层提示 | 不直接给答案，逐层提示 |
| `REVIEW_SUMMARY` | 错题复盘 | 生成或查看复盘建议 |
| `UNDERSTAND_PROBLEM` | 题目拆解 | 拆输入、处理、输出、边界 |

### 4.2 Knowledge Type

| 值 | 用户侧文案 | 说明 |
|---|---|---|
| `MEMORIZE` | 先记住 | 固定语法、规则或模板 |
| `UNDERSTAND` | 要理解 | 算法思想、推导或边界设计 |
| `MIXED` | 先记再懂 | 固定写法 + 原理理解 |
| `UNKNOWN` | 待判断 | 暂未分类 |

### 4.3 Agent Trace Status

| 值 | 说明 |
|---|---|
| `waiting` | 等待中 |
| `running` | 执行中 |
| `done` | 已完成 |
| `warning` | 有提醒，例如命中相似记忆 |
| `error` | 工具或 Agent 出错 |

## 5. Supporting APIs

```http
GET /api/memories?user_id=demo_user
GET /api/memories/{id}?user_id=demo_user
GET /api/stats/summary?user_id=demo_user
GET /api/reviews/due?user_id=demo_user
GET /api/knowledge/sources
```

当前代码可能尚未实现 `/api/memories/{id}`，该接口为 P1 目标。

## 6. Memories

```http
GET /api/memories?user_id=demo_user
```

响应：

```json
{
  "items": [
    {
      "id": "review_001",
      "title": "scanf 输入错误",
      "error_type": "C语法错误",
      "knowledge_type": "MEMORIZE",
      "knowledge_tags": ["C语言", "scanf", "输入"],
      "mistake_summary": "用户在 scanf 中忘记给普通变量加 &。",
      "review_tip": "读取普通变量时通常要传变量地址。",
      "remember_points": ["普通变量输入通常要加 &"],
      "understand_points": ["scanf 需要地址来写入变量"],
      "common_mistakes": ["普通变量和数组名是否加 & 混淆"],
      "last_seen_at": "2026-07-08",
      "next_review_at": "2026-07-10",
      "mastery": 0.42,
      "mastery_status": "reviewing"
    }
  ]
}
```

## 7. Stats Summary

```http
GET /api/stats/summary?user_id=demo_user
```

响应：

```json
{
  "metric": "common_errors",
  "time_range": "7d",
  "total_records": 4,
  "top_errors": [
    { "error_type": "C语法错误", "count": 2 },
    { "error_type": "循环边界错误", "count": 1 }
  ],
  "weak_tags": ["scanf", "数组", "二分查找"],
  "review_due_count": 2,
  "mastery_avg": 0.44,
  "recommended_actions": [
    "优先复习 scanf 输入规则。",
    "检查数组循环边界是否会访问 a[n]。"
  ]
}
```

`recommended_actions` 为新增目标字段，前端需要兼容不存在。

## 8. Reviews Due

```http
GET /api/reviews/due?user_id=demo_user
```

响应：

```json
{
  "metric": "today_review",
  "time_range": "today",
  "due_reviews": [
    {
      "id": "review_001",
      "title": "scanf 输入错误",
      "error_type": "C语法错误",
      "knowledge_tags": ["C语言", "scanf"],
      "review_tip": "读取普通变量时通常要传变量地址。",
      "next_review_at": "2026-07-10"
    }
  ]
}
```

## 9. Knowledge Sources

```http
GET /api/knowledge/sources
```

响应：

```json
{
  "total_cards": 31,
  "categories": ["c_basic", "c_mistake", "algorithm", "problem_pattern"],
  "sources": [
    {
      "name": "CodeCoach contributors",
      "license": "MIT",
      "description": "CodeCoach 第一方 C 语言教学知识卡片"
    }
  ]
}
```

## 10. Frontend Compatibility Rules

1. `message` 是唯一始终必填的用户输入字段。
2. `problem_text` 和 `code` 都是可选字段；无代码问知识必须可用。
3. 前端可以先传 `mode`，后端未支持时仍可通过 `auto` 和 Router 兜底。
4. 前端不要直接把 `intent`、`knowledge_type` 显示给用户，必须映射为中文服务文案。
5. 前端必须兼容 `review_card`、`similar_memory`、`next_actions` 缺字段。
6. 同一轮连续追问必须沿用同一个 `session_id`。
7. 代码纠错成功后，前端应刷新 `/api/stats/summary` 和 `/api/memories`。
8. 后端新增字段不得破坏旧字段：`answer`、`intent`、`knowledge_type`、`knowledge_tags`、`similar_memory`、`review_card`、`agent_trace` 必须保留。

## 11. Demo Requests

### 11.1 无代码问知识

```json
{
  "user_id": "demo_user",
  "user_level": "beginner",
  "mode": "knowledge",
  "message": "scanf 为什么要加 &？",
  "problem_text": "",
  "code": "",
  "session_id": "session_001"
}
```

### 11.2 代码纠错

```json
{
  "user_id": "demo_user",
  "user_level": "beginner",
  "mode": "debug",
  "message": "我这个代码为什么过不了？",
  "problem_text": "输入一个整数 n，输出 n。",
  "code": "#include <stdio.h>\nint main(){ int n; scanf(\"%d\", n); printf(\"%d\", n); return 0; }",
  "session_id": "session_001"
}
```

### 11.3 继续追问

```json
{
  "user_id": "demo_user",
  "user_level": "beginner",
  "mode": "followup",
  "message": "为什么普通变量要传地址？",
  "problem_text": "",
  "code": "",
  "session_id": "session_001"
}
```

### 11.4 问学习数据

```json
{
  "user_id": "demo_user",
  "user_level": "beginner",
  "mode": "data",
  "message": "我最近最常犯什么错误？",
  "problem_text": "",
  "code": "",
  "session_id": "session_001"
}
```
