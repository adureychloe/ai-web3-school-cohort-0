# Agent Commerce Hub — 当前状态与下一步

> AI × Web3 Agentic Builders Hackathon — Cobo 赛道
> 方向：Agent-Native Payments / Resource Procurement / A2A Economy

---

## 0. 说明

这个文件最初是早期 V1 实施计划。项目已经从 `ServiceRegistry.sol` 单合约 demo 迭代到 **ServiceRegistryV2 + x402 + Cobo Agentic Wallet + Buyer/Seller Web 控制台**。下面保留愿景，但以当前实现为准。

---

## 1. 当前已实现状态

### 核心闭环

- **ServiceRegistryV2 已部署到 Sepolia**
  - 地址：`0x3f945ba7BFE2181B506390c0C5e9d2328495Cc40`
  - 部署交易：`0x8e6ca555c927a5c9416a0db037ed70847c2592e650ce56ac60d4c281b6e1e18c`
- **默认服务发现走 V2/x402**
  - `/api/services`
  - `/api/procure/match`
  - `/api/procure`
  - `/api/proofs`
- **Legacy V1 已隔离**
  - 旧 `ServiceRegistry.sol` 只通过 `/api/legacy/*` 显式访问。
- **x402 Seller Server 已实现**
  - `/request` 返回 402 payment-required 语义。
  - `/register_v2` 将服务发布到链上。
  - `/seller/update_v2` 支持 Seller 自服务更新。
  - `/seller/remove_v2` 支持 Seller 自服务软下架。
- **Buyer CAW Wallet 已接入 Web UI**
  - 页面级全局连接状态。
  - `Find & Pay`、服务卡片购买、Direct x402 Checkout 复用同一地址。
  - 支持断开连接。
- **CAW 支付闭环**
  - 后端使用 server CAW wallet 创建/复用 Pact 并执行 Transfer。
  - 用户在 CAW App 中批准后继续执行。
  - 交付结果/支付证明写回链上。

### 当前架构

```text
Buyer / Seller Web UI
        │
        ▼
FastAPI Marketplace API ──────────────┐
        │                              │
        ▼                              ▼
ServiceRegistryV2 on Sepolia      x402 Seller Server
        │                              │
        └──────────────┬───────────────┘
                       ▼
             Cobo Agentic Wallet
          Pact → Approval → Transfer
                       ▼
              On-chain Delivery Proof
```

---

## 2. 产品定位

**Agent Commerce Hub 是一个面向 Agent 的 Web3 服务市场：**

1. Seller 或 Seller Agent 把服务 endpoint、价格、收款地址注册到链上。
2. Buyer 或 Buyer Agent 从链上发现服务，按需求/预算筛选。
3. 购买时使用 x402-style HTTP payment flow。
4. CAW 负责授权边界、用户批准和链上支付执行。
5. 交付证明写回合约，保留可审计历史。

---

## 3. Agent 化路线图

### Milestone A — Agent API MVP

新增两个稳定的 Agent 调用入口：

| API | 目标 |
|---|---|
| `POST /api/agent/seller/register` | Seller Agent 用自然语言服务描述自动生成 service metadata 并注册 |
| `POST /api/agent/buyer/procure` | Buyer Agent 根据任务意图自动发现、筛选、购买、返回 proof |

规则版 Buyer Agent 先不依赖复杂 LLM：

```text
intent + budget
  → list ServiceRegistryV2 services
  → keyword match + price filter
  → x402-buy
  → validate delivery
  → return content + proof
```

### Milestone B — Agent Console

在 Web UI 增加 Agent Console：

- 选择角色：Seller Agent / Buyer Agent / Broker Agent
- 输入目标：例如“发布一个 0.00002 SETH 的研究服务”或“找最便宜的市场分析服务并购买”
- 展示 timeline：discover → score → choose → pact → pay → deliver → proof
- 保留可审计记录，便于 demo 给评委看

### Milestone C — 更真实的 A2A Commerce

- 多个 Seller Agent 各自注册服务。
- Buyer Agent 自动比价并购买。
- Broker Agent 聚合多个服务并收取 fee。
- Proof 可作为下游 Agent 验收条件。

---

## 4. 安全与边界

- 普通 buyer/seller UI 不提供任意删除历史数据能力。
- Seller 更新/下架应验证服务归属或签名。
- Server-owned/admin 能力只用于 demo/debug，不作为产品化入口。
- CAW 凭证、API Key、私钥不进入仓库。
- 当前 Buyer CAW 地址在前端主要用于演示语义和记录；实际自动付款由后端 server CAW wallet 执行。

---

## 5. 已完成的早期计划（历史）

早期计划中的这些事项已经完成或被 V2 替代：

- 编译部署 V1 `ServiceRegistry.sol`。
- 跑通 CAW Pact → Approval → Transfer。
- 从 JSON/mock service 迁移到链上服务发现。
- 增加 Web UI 与 CLI 双入口。
- 增加 V2 public registration 与 x402 endpoint。
- 将 V1 legacy 路径隔离到 `/api/legacy/*`。

---

## 6. 下一步优先级

1. **落地 Agent API MVP**：`/api/agent/seller/register`、`/api/agent/buyer/procure`。
2. **Agent Console UI**：把自动决策过程可视化给评委。
3. **拒绝/取消审批体验打磨**：CAW Pact 被拒绝、取消、过期时前端必须停止 waiting 并显示终止状态。
4. **Demo script**：准备 3 分钟演示：Seller Agent 注册 → Buyer Agent 发现购买 → 链上 proof。
