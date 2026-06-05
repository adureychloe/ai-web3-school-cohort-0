# Secure Agent Commerce — 项目全景回顾与方向确认

> 2026-06-05 | 黑客松项目状态评估
> Cobo 赛道：Agentic Economy × Cobo Agentic Wallet

---

## 一、项目演进时间线

```
Week 2 (5/25-5/29)
└── 选定 Payment/Commerce 主方向
    └── Agent Commerce Sandbox 原始提案
        └── intent → quote → policy → payment → proof 的本地模拟闭环

Week 3 (5/31-6/4)
├── 选定 Cobo 赛道 ✅
├── 3 个方向脑暴：① Agent 当卖家 / ② 多 Agent 市场 / ③ Anti-PI Guard
├── 6/3: 合并 ①+③ → "Secure Agent Commerce"
│   ├── Agent 托管 x402 付费 endpoint（卖家端）
│   └── 内置 prompt injection 支付防护（安全层）
└── 6/4: 写了学习笔记，代码未开始

当前 (6/5)
└── 刚写了 Guard 层开发计划，但：❌ 未考虑 Cobo API 集成
```

---

## 二、当前项目状态 vs 黑客松评审标准

### 评审 4 维度评估

| 维度 | 当前状态 | 评分 (1-10) | 问题 |
|------|---------|------------|------|
| **API 集成度** | 零 Cobo API 调用。所有 policy / payment / audit 纯本地模拟 | **0/10** | ⚠️ Cobo 赞助的黑客松，完全不调 Cobo API 等于没参赛 |
| **创新性** | "Agent 当卖家"在 Cobo 生态中无现成 Recipe，"安全层"方向也无竞品 | **7/10** | ✅ 方向有创新空间 |
| **产品完整度** | CLI 原型可跑 3 个场景，有输出文件 | **5/10** | ⚠️ 还不够完整 |
| **演示呈现** | 有 3 幕故事线想法，无实际 demo 脚本 | **3/10** | ⚠️ 没准备好 |

### 最大问题：API 集成度为 0

Cobo 现有的 API 能力，我们一个都没用：

| 我们的本地实现 | 应该替换为 Cobo 的 | Cobo API 端点 |
|--------------|-------------------|--------------|
| `policy.json` + `policy_checker.py` | Pact 提交 → 政策引擎执行 | `POST /api/v1/pacts/submit` |
| `payment_simulator.py` | Transfer / Payment API | `POST /api/v1/wallets/{id}/transfer` |
| `proof_logger.py` | Audit 日志查询 | `GET /api/v1/audit_logs` |
| 本地地址白名单 | Address allowlists | Pact policy 的 `destination_address_in` |
| 本地频率限制 | Rolling window limits | Pact policy 的 `usage_limits` |

---

## 三、我们真正的创新点在哪里

Cobo 已有 | Cobo 没有（我们的机会）
---------|---------------------
x402 Payment Recipe（Agent 当消费者） | ❌ **Agent 当卖家** — 托管 x402 endpoint 等人付钱
Token Transfer / Swap 等基础操作 | ❌ **Agent 支付安全层** — prompt injection 防护、定价防篡改
Pact 政策引擎（链上行为控制） | ❌ **前置语义检测** — Cobo 看不到用户的 prompt 文本

我们的项目不应该是"用 Cobo API 替代本地模拟"这么简单。而是：

> **Guard 层（Cobo 做不到的事）+ Cobo API（Cobo 能做的事）= Secure Agent Commerce**

```
用户请求文本 ──→ Guard 语义检测（Cobo 看不到的）──→ Pact 提交到 Cobo（政策引擎）
                                                       │
                                                       ├── 通过 → Cobo 执行转账
                                                       └── 拒绝 → Cobo 返回 denial 原因
```

我们的 Guard 做 Cobo 做不了的事，Cobo API 做我们不该重复实现的事。

---

## 四、方向确认：到底做什么

### 项目定位（更新版）

> **Secure Agent Commerce** — 一个 AI agent 安全地经营付费服务的完整 demo。
>
> Agent 通过 Cobo Agentic Wallet 持有钱包、提交 Pact、执行 x402 支付；
> 同时内置 Guard 检测层，在 pact 提交前拦截 prompt injection 和定价篡改攻击。
>
> 填两个空白：Cobo 生态中"卖家端"的空缺 +  Agent 支付安全的空缺。

### 4 个评审维度的得分目标

| 维度 | 目标分 | 怎么做 |
|------|-------|--------|
| **API 集成度** | 8/10 | 提交 Pact、通过 Pact 执行转账、查询审计日志。至少 3 个 Cobo API 端点 |
| **创新性** | 8/10 | "AI Agent 卖家 + 支付安全"在 Cobo 生态中无竞品。Demo 3 幕故事展示完整创新链 |
| **产品完整度** | 7/10 | CLI 可重复演示、有攻击报告输出、双模式（有/无 Cobo Key 都能跑）、README 完整 |
| **演示呈现** | 7/10 | 3 分钟演示脚本 + 截图/GIF + 清晰的 README 架构图 |

### 当前最核心的决策问题

**现在要做的是「Guard 检测层」还是「Cobo API 集成」？**

我的建议：**先做 Cobo API 集成，再做 Guard 检测层**。理由：

1. API 集成度是 0 → 这是最明显的短板，也是 Cobo 评委最在意的
2. Cobo API 集成 = 提交一个 Pact + 执行一个转账，改动量不大（~150 行 `cobo_client.py`）
3. Guard 本地检测可以独立于 Cobo 集成，两件事不冲突
4. 演示顺序：先演示"集成 Cobo 后的正常流程"→ 再演示"Guard 拦截攻击"

但最终听你的。你想先做哪个？或者有其他想法？
