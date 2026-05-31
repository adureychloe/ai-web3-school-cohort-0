# Week 3｜赛道选择说明

日期：2026-05-31
WCB 任务：Week 3｜最低完成路径｜赛道选择说明

---

## 0. 三个赛道一览

Hackathon 共有 **3 个赛道**可选（来自 WCB 赛道选择任务）：

| 赛道 | 全称 | 侧重 | 赞助商 |
|------|------|------|--------|
| **Cobo** | Agentic Economy × Cobo Agentic Wallet | Agent 在可控边界内持有钱包、管理预算、执行支付/交易 | Cobo（联合赞助） |
| **Z.AI** | Web3 × Long-Horizon Task | AI Agent 拆解复杂任务、持续调用工具、迭代修复 | Z.AI / 智谱（领衔赞助） |
| **Open** | 开放赛道 | 自由选题，不绑定赞助商 | — |

---

## 1. 选择的赛道：Cobo Agentic Wallet 赛道

Agent Commerce Sandbox 的核心是 **agent 如何在用户授权边界内完成商业交易**——这正是 Cobo Agentic Wallet / Pact / Policy 基础设施要解决的问题。

---

## 2. Cobo 赛道详解

### 来源
- 官网：https://www.cobo.com/agentic-wallet
- 课程 workshop：Week 2 Cobo Product Manager 分享回放可用

### 核心概念：Pact（协议）

Cobo Agentic Wallet 的核心理念是 **Pact**：Agent 不拿私钥，而是每次任务创建一个 Pact（受权协议）。

一个 Pact 包含 4 个部分：

| Pact 组成部分 | 含义 | Agent Commerce Sandbox 对应 |
|--------------|------|---------------------------|
| **Intent**（任务目标） | Agent 要完成什么任务 | User intent → 结构化目标 |
| **Execution Plan**（执行计划） | 如何完成任务的可审查路线 | 流程图：discover → quote → policy → pay → verify |
| **Policies**（策略） | budget、allowlist、chain/token 约束、人工确认阈值 | policy.json 全部内容 |
| **Completion Conditions**（完成条件） | 什么情况下 Pact 自动结束：超时、预算花完、任务完成 | receipt.json + proof log |

### Pact 生命周期

```
你描述意图 → Agent 起草 Pact（intent + plan + policies + conditions）
→ 你在手机 App 审核 → 批准后 Wallet 按 policy 自动执行
→ 达到完成条件后 Pact 自动结束，key 自动撤销
```

### 安全模型：MPC（多方计算）

- **非托管**（non-custodial）：用户持有自己的 key share
- MPC 阈值签名：Agent + Cobo 各持一半密钥，任何一方都不能单独签名
- 两组签名权限：
  - Agent + Cobo 组（2/2）：处理 Pact 授权的自动交易
  - Human + Cobo 组（2/2）：处理高价值审批和治理
- 用户可以随时从自己的备份恢复完整私钥所有权

### 提供的 Recipes（现成可用的集成示例）

| Recipe | 说明 |
|--------|------|
| x402 Payment | 用 `caw fetch` 调用 x402 端点的 Base 主网支付 |
| Token Transfer | 跨 EVM 和 Solana 的转账 |
| Uniswap V3 Swap | 去中心化兑换 |
| Jupiter Swap (Solana) | Solana 生态兑换 |
| Aave V3 Lending | 借贷协议交互 |
| Superfluid Streaming | 每秒支付流 |
| DCA Order Executor | 定投执行器 |

### 提供的工具

| 工具 | 用途 |
|------|------|
| npx skill | `npx skills add CoboGlobal/cobo-agentic-wallet --skill cobo-agentic-wallet` |
| CLI / SDK | Python 或 TypeScript |
| Mobile App | 审核 Pact、确认交易、查看活动日志 |

### 关键对齐点

| 项目需求 | Cobo 赛道匹配点 |
|----------|----------------|
| 模拟 wallet policy（budget、allowlist、limit） | Pact policies 就是做这个 |
| 安全检查后执行支付 | Pact + MPC 签名模式 |
| 人工确认 vs 自动执行的阈值 | Human + Cobo 组 vs Agent + Cobo 组 |
| 权限可撤销、可审计 | Pact 结束后 key 自动撤销 |
| 将 intent → payment → proof 串成闭环 | Pact 生命周期完美对应 |

---

## 3. Z.AI 赛道详解

### 来源
- Z.AI / 智谱：领衔赞助商，提供 GLM-5.1 / GLM-5 大模型
- 官网：https://z.ai/
- 侧重：核心算力 + 开发者激励

### 侧重点

Z.AI 赛道（Web3 × Long-Horizon Task）更偏 **Agent 的自主推理和多步工具调用**：

- Agent 拆解复杂任务
- 持续调用多个工具
- 根据中间结果迭代修复
- 完成从需求到交付的完整 Web3 工作流

### 适合的项目类型

- 需要 Agent 做多步链上分析或操作的项目
- Agent 需要跨多个合约/协议协调工作
- Agent 需要根据链上状态变化自我修正

### 为什么我的项目暂不选 Z.AI

| 原因 | 说明 |
|------|------|
| 核心不是多步推理 | Agent Commerce Sandbox 的核心是 **安全边界和授权流程**，不是 AI 推理能力 |
| 支付层是重点 | 我的项目聚焦于 x402、policy、receipt log——这些都是 Cobo 赛道的问题域 |
| 后续可以接入 | Z.AI 的 GLM 模型可以用作 intent parsing 和 risk explanation 的替换后端 |

---

## 4. Open 赛道

不绑定任何赞助商，自由选题。

如果你的项目不属于 Cobo 或 Z.AI 的明确范围，可以直接走 Open 赛道。
Agent Commerce Sandbox 也可以走 Open，但选择 Cobo 赛道可以获得更准确的对齐和反馈。

---

## 5. 结论

**选 Cobo 赛道**。理由：

1. Agent Commerce Sandbox 的核心闭环（intent → policy check → payment simulation → proof log）与 Cobo 的 Pact 模式完全一致
2. 我模拟的 policy.json / budget / allowlist / human confirmation 正好是 Cobo 赛道要解决的核心问题
3. Cobo 提供的 x402 Payment recipe 直接对应我项目中的支付模拟层
4. 后续可以将 mock policy engine 替换为真实的 Cobo CAW SDK

## 6. 赛道资源参考

- Cobo Agentic Wallet 官网：https://www.cobo.com/agentic-wallet
- Cobo CAW Skill：`npx skills add CoboGlobal/cobo-agentic-wallet`
- Cobo Recipe：x402 Payment / Token Transfer / Swap
- Z.AI / 智谱 GLM：https://z.ai/
- WCB 赛道选择任务：Cobo / Z.AI / Open
