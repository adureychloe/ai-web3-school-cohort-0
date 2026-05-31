# Week 3｜赛道选择说明

日期：2026-05-31
WCB 任务：Week 3｜最低完成路径｜赛道选择说明

---

## 1. 选择的赛道：Cobo Agentic Wallet 赛道

Agent Commerce Sandbox 的核心是 **agent 如何在用户授权边界内完成商业交易**——这正是 Cobo Agentic Wallet / Smart Account / Policy 基础设施要解决的问题。

## 2. 为什么选 Cobo 赛道

| 项目需求 | Cobo 赛道匹配点 |
|----------|----------------|
| 模拟 wallet policy（budget、allowlist、limit） | Cobo 的 CaW（Custodial Agentic Wallet）和 Pact 任务级授权正是做这件事 |
| 安全检查后执行支付 | Safe / guard / session key 模式 |
| 人工确认 vs 自动执行的阈值 | 任务级授权 + 人工确认门 |
| 权限可撤销、可审计 | Session Key 到期失效、policy 日志 |
| 需要一个身份/权限层来管理 agent | Cobo Agentic Wallet 的方向就是 agent 钱包 |

Cobo 的 CaW + Pact 的方案非常务实：授权围绕一次具体任务生成，任务结束权限失效。这正好解决了"agent 不能持有长期权限"的问题。

## 3. 备选考虑：Z.AI 赛道

Z.AI 更偏 agent infra 和 agent identity（ERC-8004 等）。

| 为什么暂不选 Z.AI | 说明 |
|-------------------|------|
| ERC-8004 身份协议很重要 | 但我的 project 还没到需要 onchain identity 的阶段 |
| 更偏 infra 层 | 我更适合先做应用层验证 |
| 后续可以接入 | receipt hash 锚定、agent profile 上链都在 roadmap 上 |

**结论**：选 Cobo 赛道作为主要对齐方向，Z.AI 相关的 ERC-8004 identity 可以作为 Week 4 的扩展功能。

## 4. 与 Cobo 赛道的具体对齐点

| Agent Commerce Sandbox 模块 | 对应 Cobo / CaW 概念 | 实现方式 |
|---------------------------|---------------------|---------|
| policy.json | Wallet policy / guard | 用配置文件模拟 policy 规则 |
| Budget / limit check | Task-level budget | 单笔限额 + 累计限额检查 |
| Human confirmation gate | Human-in-the-loop | 新服务 / 超额时暂停 |
| Session-based permission | Session key | 一次对话一个 session，结束后权限失效 |
| receipt.json / proof log | Audit trail | JSON lines 输出 + receipt hash（远期） |
| Service allowlist | Allowlist | 只有白名单服务可自动支付 |

## 5. 赛道资源参考

- Cobo Agentic Wallet (CaW) — https://cobo.com
- CaW Pact 任务级授权模式
- Safe / guard / session key 机制
