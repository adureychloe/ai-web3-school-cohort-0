# Week 3｜项目一句话说明

> 更新日期：2026-06-07

---

## 一句话说明

> **Agent Commerce Hub** — Agent 通过链上合约（ServiceRegistry.sol, Sepolia）发现付费服务，通过 Cobo Agentic Wallet（CAW）创建 Pact 获取有限支付授权，完成链上 Transfer，并将交付证明写回合约，实现真实可验证的 Agentic Commerce 闭环。

## 备选版本

| 版本 | 侧重 |
|------|------|
| **面向评委版** | An on-chain agent commerce demo: ServiceRegistry.sol on Sepolia → CAW Pact → Approval → Transfer → Delivery Proof — all real, no simulation |
| **面向同学版** | 把「Agent 怎么花钱」从概念变成了真实可运行的完整流程：合约发现服务 → CAW 授权支付 → 链上交易 → 交付存证，全程可通过 CLI 或 Web UI 体验 |
| **带标题版** | Agent Commerce Hub — 链上服务发现 × CAW 自主支付 × 交付上链存证 |

## 详细展开

- **目标**：让 Agent 成为互联网经济的一等公民 — 自主发现服务、发起支付、记录交付
- **做了什么**：ServiceRegistry.sol 部署到 Sepolia → 注册 3 个服务 → caw_client.py 包装 CAW CLI → engine.py 编排全流程 → 跑通真实链上交易
- **验证证据**：合约地址 `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` → 交易 Hash `0x9b8a70db...a4aedf` → 交付存证已确认
- **技术栈**：Solidity + Sepolia + Cobo Agentic Wallet + Python + FastAPI
- **为什么有意义**：不只是理论上的「Agent 可以付钱」，而是从服务注册到资金执行到交付存证的完整链上闭环
