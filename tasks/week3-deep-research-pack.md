# 深度研究包 — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 研究对象

围绕 Agent Commerce Hub 的核心方向，选择了 3 个关键标准/协议/SDK 进行深度研究：

---

### 1. Cobo Agentic Wallet — Pact 授权模型

| 维度 | 内容 |
|------|------|
| **解决什么问题** | Agent 在不持有完整私钥的情况下，获得有限、可撤销的链上操作权限 |
| **核心机制** | Pact（协议）：Intent + Execution Plan + Policies + Completion Conditions 四部分 |
| **安全模型** | MPC 2/2 阈值签名：Agent + Cobo 各持一半，任何一方不能单独签名 |
| **边界** | 只支持 EVM 链和 Solana；无原生跨链；Policy 是服务器端执行，Agent 端不可见 |
| **还缺什么** | 缺少 Agent 侧的本地安全预处理（如 prompt injection 检测）；Pact 中的 policy 验证是黑盒 |
| **项目集成** | 已通过 `caw` CLI 完成 Pact 提交和 Transfer，计划迁移至 Python SDK |

### 2. Cobo Agentic Wallet Python SDK (`cobo-agentic-wallet`)

| 维度 | 内容 |
|------|------|
| **解决什么问题** | 提供原生 Python API 替代 CLI subprocess 调用，支持类型安全、原生异常处理 |
| **核心能力** | `WalletAPIClient`：pact 提交、transfer 执行、policy 拒绝处理、审计日志查询 |
| **安装** | `pip install cobo-agentic-wallet` |
| **环境变量** | `AGENT_WALLET_API_URL` / `AGENT_WALLET_API_KEY` / `AGENT_WALLET_WALLET_ID` |
| **边界** | 目前不支持合约部署（CAW 不可部署合约）；不支持 Man-in-the-middle 签名；依赖 API 可用性 |
| **还缺什么** | 缺少 Agent 侧的 intent 级安全检测（如 prompt injection）；没有原生 procurement/采购模式 |
| **项目集成** | 当前使用 CLI，计划 6/8-6/9 迁移至 SDK |

### 3. x402 / HTTP 402 Payment Protocol

| 维度 | 内容 |
|------|------|
| **解决什么问题** | 让 HTTP API 返回 402 状态码要求链上支付，Agent 自动完成支付后解锁资源 |
| **工作方式** | GET /resource → 402 + payment_required（含 price/address/token）→ Agent 支付 → 重试 → 获得资源 |
| **CAW 集成** | Cobo 提供 x402 Payment Recipe：`caw fetch` 命令 |
| **边界** | 未标准化，各实现互不兼容；需要服务端支持 402 + proof 验证；不适合高并发低延迟场景 |
| **还缺什么** | 缺少通用的 Agent 端 402 处理框架；服务端 proof 验证需要标准化的签名方案 |
| **项目集成** | 计划 6/9 实现本地 HTTP 402 付费 API Demo |

---

## 总结

| 技术 | 解决的核心问题 | 项目中的角色 | 优先级 |
|------|-------------|-------------|--------|
| CAW Pact | Agent 受权链上操作 | ✅ 支付层核心 | P0 |
| CAW Python SDK | 原生 Python 集成 | 🔄 迁移中（6/8-6/9） | P1 |
| HTTP 402 | Agent 自动解锁付费资源 | 📅 计划中（6/9） | P1 |
