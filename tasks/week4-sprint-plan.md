# Week 4｜Sprint Plan

日期：2026-06-01
WCB 任务：Week 3｜最低完成路径｜Week 4 Sprint Plan
前置：Week 3 Repo Skeleton（agent-commerce-sandbox/）

---

## 0. 总体时间线

| 阶段 | 时间 | 目标 |
|------|------|------|
| Week 3 | 6/1 – 6/5 | 搭建核心闭环 CLI 原型，跑通 3 个场景 |
| Week 4 冲刺 | 6/6 – 6/13 | 迭代、完善、准备 Demo |
| Demo 展示 | 6/14 | Hackathon 结营展示 |

> 注意：Week 3 和 Week 4 是连续开发的——Week 3 做 MVP 核心，Week 4 做打磨和展示准备。

---

## 1. Week 3 剩余计划 (6/1 – 6/5)

| 日期 | 任务 | 产出 | WCB 任务对齐 |
|------|------|------|-------------|
| 6/1 (一) | Repo Skeleton + Sprint Plan | agent-commerce-sandbox/ 目录结构 | 最低完成路径：Repo Skeleton |
| 6/2 (二) | 核心引擎完善 + 场景强化 | engine.py 完成 3 个完整场景跑通 | 加分挑战：技术验证计划 |
| 6/3 (三) | 流程可视化 + mermaid 流程图 | README 含完整流程图，与代码一致 | 加分挑战：项目流程图 |
| 6/4 (四) | 测试用例 + 边界场景 | 超预算、未知服务、prompt injection 等防御场景 | 推荐完成：Risk / Assumption Memo |
| 6/5 (五) | Week 3 例会分享准备 | 准备 3 分钟演示 + 关键截图 | Week 3 例会 + 6.05 Live Reflection |

### 可选任务（视时间）

- 加分挑战：完整 Week 4 Ready Pack
- Sponsor Workshop：Cobo 赛道对齐任务
- Sponsor 问题收集

---

## 2. Week 4 Sprint (6/6 – 6/13)

### Day 1-2: 产品完善 (6/6 – 6/7)

**目标**：从 MVP 原型升级为可重复演示的完整工具

| 任务 | 详情 | 优先级 |
|------|------|--------|
| 输出格式标准化 | receipt.json + proof.md 结构统一，markdown 可读 | P0 |
| 场景参数化 | 支持从命令行指定服务、金额、意图 | P0 |
| 错误处理 | policy 拒绝理由清晰可读，不崩溃 | P0 |
| 彩色 CLI 输出 | rich 或 colorama 让输出更易读 | P1 |

### Day 3-4: 风险场景强化 (6/8 – 6/9)

**目标**：展示不止正常流程，还有防御能力

| 任务 | 详情 | 优先级 |
|------|------|--------|
| Prompt Injection 测试 | 模拟 service 返回诱导 agent 忽略 policy 的场景 | P0 |
| 多笔累计超限 | 连续小额支付累计超出 session budget | P0 |
| 被篡改的报价 | 服务返回虚假的收款地址或金额 | P1 |
| 审批疲劳 | 大量确认请求导致用户盲目确认的场景 | P1 |

### Day 5-6: Cobo 赛道对齐 (6/10 – 6/11)

**目标**：展示项目与 Cobo Agentic Wallet 的技术对齐

| 任务 | 详情 | 优先级 |
|------|------|--------|
| 研究 Cobo CAW SDK | 理解 Pact / recipe / skill 如何工作 | P0 |
| 撰写对齐文档 | 说明 mock policy.json → Cobo Pact 的映射 | P0 |
| 标注「可替换」点 | 代码注释标明哪部分可替换为真实 x402 或 CAW SDK | P0 |
| Sponsor 问题清单 | 列出要问 Cobo 团队的问题 | P1 |

### Day 7-8: 演示准备 (6/12 – 6/13)

**目标**：准备结营 Demo

| 任务 | 详情 | 优先级 |
|------|------|--------|
| 演示脚本 | 3 分钟：项目定位 → 架构 → 3 个场景演示 → 未来路径 | P0 |
| 截屏 / GIF | CLI 运行过程的录制或截图 | P0 |
| README 完善 | 安装、运行、场景说明、技术栈 | P0 |
| 风险 / 限制说明 | 哪些做了、哪些没做、为什么 | P1 |
| 彩蛋 / 亮点 | 比如「anti-prompt-injection」或「意外发现的 x402 insight」 | P2 |

---

## 3. 技术路线图

```
Week 3 (6/1-6/5)                  Week 4 (6/6-6/13)
┌─────────────────────┐           ┌──────────────────────┐
│ CLI skeleton         │    →     │ 完善输出 + 错误处理   │
│ 3 scenarios basic    │    →     │ 风险场景扩展          │
│ policy.json          │    →     │ Cobo SDK 对齐研究     │
│ receipt.json + proof │    →     │ 标准化输出格式        │
└─────────────────────┘           └──────────────────────┘
                                         │
                                         ↓
                                  ┌──────────────────────┐
                                  │ 演示脚本 + README     │
                                  │ Cobo 赛道对齐文档     │
                                  │ Week 4 结营展示       │
                                  └──────────────────────┘
```

---

## 4. 演示脚本 (3 分钟)

### 开场 (30s)

> **Agent Commerce Sandbox** — 模拟 agent 从理解用户目标、发现付费服务、检查安全策略、执行模拟支付到产出 proof log 的完整商业闭环。

### 架构概要 (30s)

> 核心是 3 个 JSON 配置 + 1 个 Python 引擎：
> - `services.json`定义 mock 服务列表
> - `policy.json`定义预算、allowlist、单笔限额
> - `engine.py`按 `intent → quote → policy check → payment → proof` 顺序执行

### 场景演示 (90s)

1. **正常支付** — allowlist 内的服务，小额自动通过
2. **超预算拦截** — 累计超出 session limit，policy 直接拒绝
3. **未知服务** — 未在 allowlist 中的服务，触发人工确认

### 未来路径 (30s)

> 下一步：将 mock policy 替换为真实 Cobo CAW Pact、将 x402 mock 替换为真实 caw fetch recipe、加入 ERC-8004 服务发现层。

---

## 5. 成功标准

| 检查项 | Week 3 结束 | Week 4 结束 |
|--------|-------------|-------------|
| CLI 可运行 | ✅ 3 场景基本可用 | ✅ 参数化 + 彩色输出 |
| Policy 拒绝理由清晰 | ✅ 有 reason 字段 | ✅ 人类可读的中英文 |
| receipt.json 结构完整 | ✅ 基本结构 | ✅ 标准化 |
| proof.md 可导出 | ✅ 有文件输出 | ✅ markdown 可分享 |
| 3 个演示场景可运行 | ✅ 全部跑通 | ✅ 含风险扩展场景 |
| Cobo 对齐文档 | — | ✅ 含具体映射表 |
| 演示脚本 | — | ✅ 3 分钟完整脚本 |

---

## 6. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 每天只有 1 小时开发时间 | 核心闭环最优先，非核心功能标记 backlog |
| Cobo CAW SDK 集成可能需要更多学习 | Week 4 先做研究和对齐文档，不一定非要实际集成 |
| 演示时间只有 3 分钟 | 要确保 CLI 能在 30 秒内跑完一个场景，避免现场等待 |
| 缺乏评审和反馈 | 参加 Week 3 例会分享获取反馈，也可以直接问课程群 |

---

## 7. 与 WCB 任务对齐

| WCB 任务 | 对应计划 |
|----------|----------|
| 最低完成路径：Hackathon Direction Card | ✅ 已完成 |
| 最低完成路径：赛道选择说明 | ✅ 已完成 |
| 最低完成路径：项目一句话说明 | ✅ 已完成 |
| 最低完成路径：组队/单人参赛确认 | ✅ 已完成 |
| 最低完成路径：Repo Skeleton | ✅ 已完成 (agent-commerce-sandbox/) |
| 最低完成路径：Week 4 Sprint Plan | ✅ 本文件 |
| 推荐完成：Risk / Assumption Memo | Week 3 6/4 计划 |
| 推荐完成：Scope Review | Week 3 可选 |
| 加分挑战：技术验证计划 | Week 3 6/2 计划 |
| 加分挑战：项目流程图 | Week 3 6/3 计划 |
| Sponsor Workshop：Cobo 赛道对齐 | Week 4 Day 5-6 计划 |
