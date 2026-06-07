# Week 4｜Sprint Plan

> 更新日期：2026-06-07  
> 实际进展已大幅超前原计划

---

## 实际完成情况（截至 6/7）

| 里程碑 | 状态 | 详情 |
|--------|------|------|
| ServiceRegistry.sol 编译部署 | ✅ | Sepolia `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` |
| 3 个服务注册 | ✅ | Research / Data Fetcher / Analyzer |
| CAW Pact 提交 + 批准 | ✅ | Pact 已激活 |
| 链上 Transfer | ✅ | `0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf` |
| 交付存证上链 | ✅ | Block 11008291 |
| caw_client.py + chain_client.py | ✅ | Python 封装 |
| engine.py 5 步流程 | ✅ | 发现→Pact→等待→转账→存证 |
| CLI (run.py) | ✅ | discover / pay / proof / status |
| Web UI (FastAPI) | ✅ | 暗色终端风格，前后端分离 |

---

## Week 4 冲刺计划 (6/8 – 6/13)

### Day 1 (6/8) — 自主采购 Agent

| 任务 | 优先级 |
|------|--------|
| 写 `procurement_agent.py`（自然语言意图→比价→选最优→支付） | P0 |
| `run.py procure "..."` 命令 | P0 |
| Guard 安全层集成到 engine.py（Pact 提交前拦截） | P0 |

### Day 2 (6/9) — HTTP 402 + Demo 场景

| 任务 | 优先级 |
|------|--------|
| 本地付费 API endpoint（返回 402 → CAW 支付 → 解锁） | P0 |
| `run.py fetch-paid` 命令 | P1 |
| 攻击场景 demo（prompt injection 拦截） | P0 |

### Day 3-4 (6/10-6/11) — Demo 打磨

| 任务 | 优先级 |
|------|--------|
| Web UI 完善：采购流程 + 风险面板 + 时间线 | P1 |
| Guard 阻断场景 UI 展示 | P1 |
| Demo 视频录制（3-5 分钟） | P0 |
| README 完整更新（含架构图 + 运行说明 + 链上证据） | P0 |

### Day 5 (6/12) — 提交准备

| 任务 | 优先级 |
|------|--------|
| Demo 最终测试（从零跑通） | P0 |
| 链上证据整理（合约地址、tx hash、钱包地址） | P0 |
| 视频上传 + 截图 | P0 |
| GitHub Repo 最终检查 | P0 |

### Day 6 (6/13 12:00 UTC+8) — 截止

| 任务 | 优先级 |
|------|--------|
| 最终提交 | P0 |

---

## Week 4 冲刺时间线

```
6/7   6/8     6/9     6/10    6/11    6/12    6/13
│     │       │       │       │       │       │noon
├已完─┤       │       │       │       │       │
│成   ├P0─────┤       │       │       │       │
│核   │采购Agent+Guard  │       │       │       │
│心   │       ├P0─────┤       │       │       │
│闭   │       │402 API+攻击Demo│       │       │
│环   │       │       ├P1─────┤       │       │
│     │       │       │UI打磨+视频│       │       │
│     │       │       │       ├P0─────┤       │
│     │       │       │       │提交准备│       │
│     │       │       │       │       │ 截止  │
```

---

## WCB 后续打卡任务

| 任务 | 素材来源 | 计划 |
|------|---------|------|
| Cobo 赛道对齐任务 | 完整 CAW 集成证据 ✅ | 6/8 提交 |
| Sponsor SDK / API Integration Plan | caw_client.py 文档 | 6/8 提交 |
| 技术验证计划 | 合约部署 + 链上交易证据 | 6/8 提交 |
| 项目流程图 | 架构图 + 时序图 | 6/8 提交 |
| 6.12 Live Reflection | Demo 展示 | 6/12 |
