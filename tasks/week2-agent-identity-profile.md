# Week 2｜Agent Identity｜Agent Profile 与能力声明草图

日期：2026-05-30
WCB 任务：Week 2｜Agent Identity｜Agent Profile 与能力声明草图
状态：Proof-of-Work 草稿（知识扩展）

## 1. 背景

本周主线是 Payment / Commerce / Settlement，项目名 Agent Commerce Sandbox。这里为这个项目中的核心 agent 设计一份 profile 草图。

## 2. Agent Profile: "Commerce Agent"

### 基本信息

| 字段 | 内容 |
|------|------|
| 名称 | Commerce Agent |
| 类型 | 会话式 commerce executor |
| 维护者 | 项目 owner（人工） |
| 部署位置 | 本地或用户信任环境 |
| 通信接口 | 自然语言 prompt → 结构化指令 |

### 它能做什么（Capability Manifest）

```
Capabilities:
  - parse_intent: 用户说"帮我买份研究资料" → {target, budget, deadline}
  - discover_service: 从 services.json 里匹配可用服务
  - request_quote: 向服务发送询价 → {price, deliverable, ETA}
  - check_policy: 对照 policy.json 检查预算/合约/操作允许
  - confirm_with_user: 高风险/超预算时请求人工确认
  - execute_payment: 在预算内执行 x402 → EIP-3009 支付
  - verify_delivery: 检查交付物是否符合预期
  - log_receipt: 生成 receipt.json → 写入 proof log
  - handle_dispute: 交付不符合时触发争议流程
```

### 如何被调用

- 输入：自然语言任务描述 + 可选的 policy / budget 约束
- 输出：任务状态（pending / in_progress / completed / disputed）+ receipt JSON
- 约束：必须在用户定义的 policy.json 范围内执行

### 如何收费

- 本阶段：不收费，实验环境
- 未来设想：按任务计费或 subscription，由 agent wallet 自动结算

### 如何被验证

- 任务历史：所有 actions 记录在 receipt.log（JSON lines）
- 链上锚定（未来）：receipt hash 上链作为 proof-of-work
- 人工抽检：用户可随时回放 agent 的决策过程和执行记录

### 失败如何处理

| 失败类型 | 处理方式 |
|----------|----------|
| 找不到服务 | 返回候选列表，请用户指定 |
| 超预算 | 暂停，请求用户确认或调整 budget |
| 交付不符 | 记录差异，触发人工 review 或退款流程 |
| 执行超时 | 超时回滚，返回错误状态 |
| policy 拒绝 | 记录拒绝原因，返回给用户 |

## 3. 一句话理解

> Identity 不是 NFT 名片，而是"你是谁、能做什么、怎么被找到、失败了谁负责"的完整描述。把能力列清楚，比发一个链上 ID 更重要。

## 4. 对比：MCP vs A2A vs ERC-8004

| 协议 | 解决哪段 | 适合谁用 |
|------|----------|----------|
| MCP | Agent ↔ Tool 接口 | 让 agent 能调用外部工具 |
| A2A | Agent ↔ Agent 协作 | 多 agent 分工完成任务 |
| ERC-8004 | Agent ↔ 链上 Registry | onchain agent identity / reputation |
| MPP / x402 | Agent ↔ Payment 接口 | 机器间自动支付结算 |

**结论**：这几个协议不冲突，它们在不同层级。Commerce Agent 需要全部：MCP 读取 services.json，A2A 协调子 agent，ERC-8004 注册身份，x402/MPP 完成支付。
