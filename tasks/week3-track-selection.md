# Week 3｜赛道选择说明

> 更新日期：2026-06-07  
> 项目已从模拟原型升级为真实链上 + CAW 集成

---

## 1. 选择的赛道：Cobo Agentic Wallet 赛道 ✅

**已确认：Agent Commerce Hub → Cobo 赛道**

原因：Agent Commerce Hub 的核心是 **Agent 通过 CAW 完成从服务发现到链上支付到交付存证的完整资金闭环**——这正是 Cobo 赛道要解决的 Agentic Commerce 问题。

---

## 2. 为什么选 Cobo（对比 Z.AI / Open）

| 维度 | Cobo ✅ | Z.AI | Open |
|------|---------|------|------|
| 核心能力 | Agent 安全支付+钱包权限 | 多步推理+工具调用 | 自由选题 |
| 项目匹配度 | **极高** — CAW 是支付关键组件 | 低 — 不依赖长程推理 | 中 |
| 集成深度 | 已集成 `caw` CLI (Pact→Transfer) | 未使用 GLM-5.1 | — |
| CAW 关键性 | **不可替换** — 全部资金操作通过 CAW | 无关 | 无关 |

---

## 3. 项目与 Cobo 赛道 5 个方向的对齐

| 方向 | 在项目中的体现 | 实现状态 |
|------|-------------|---------|
| ① Agent-Native Payments | Agent 通过 CAW Pact + Transfer 自动支付 | ✅ 已跑通 |
| ② Trustless Work Agreements | ServiceRegistry.recordDelivery() 存证 | ✅ 已部署 |
| ③ Agent Resource Procurement | Agent 查询合约发现服务+比价 | 🚧 procurement agent 开发中 |
| ④ Autonomous Trading | (扩展) caw tx call 调用 DEX | P2 待做 |
| ⑤ A2A Economy | 多 Agent 钱包互付 | P2 待做 |

---

## 4. 实际 CAW 集成情况

| 组件 | 状态 | 详情 |
|------|------|------|
| CAW CLI 安装 | ✅ | `~/.local/bin/caw` |
| 钱包配对 | ✅ | Agent: Hermes (caw_agent_d1a55c...) |
| Pact 提交 | ✅ | `caw pact submit` → 手机批准 |
| 链上 Transfer | ✅ | Tx: `0x9b8a70db...a4aedf` (Sepolia) |
| caw_client.py | ✅ | Python subprocess 封装 |
| Policy 动态生成 | ✅ | 从合约 paymentAddress 动态构建 |

---

## 5. 区块链证据

| 项目 | 值 |
|------|-----|
| ServiceRegistry 合约 | `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` (Sepolia) |
| CAW Wallet | `0x9e01312e8e96a8133a3c73bed58a5808ecfceaf5` |
| 已注册服务 | 3 个 (Research / Data Fetcher / Analyzer) |
| 确认交易 | `0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf` |
| 交付存证 | 已写入合约 (block 11008291) |
| GitHub Repo | `github.com/adureychloe/ai-web3-school-cohort-0` |
