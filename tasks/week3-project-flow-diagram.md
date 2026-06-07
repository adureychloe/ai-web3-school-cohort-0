# 项目流程图 — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     User (CLI / Web UI)                      │
│  python run.py discover | pay | proof | status               │
└────────────────────────────────┬────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│              agent_commerce_sandbox/engine.py                 │
│                Core 5-Step Payment Flow                      │
│                                                              │
│  [1/5] Query ServiceRegistry    → chain_client.get_service() │
│  [2/5] Submit CAW Pact          → caw_client.submit_pact()   │
│  [3/5] Wait for Human Approval  → CAW App notification       │
│  [4/5] Execute CAW Transfer     → caw_client.transfer()      │
│  [5/5] Record Delivery Proof    → chain_client.record()      │
└────────────────────────────────┬────────────────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ ServiceRegistry   │   │ Cobo Agentic     │   │ Sepolia          │
│ .sol (Sepolia)    │   │ Wallet (CAW)     │   │ Blockchain       │
│                   │   │                  │   │                  │
│ register()        │   │ Pact 提交        │   │ Tx 确认          │
│ listServices()    │   │ 手机 App 批准    │   │ Block 存证       │
│ getService()      │   │ Transfer 执行    │   │ 状态不可篡改     │
│ recordDelivery()  │   │ Policy 强制      │   │                  │
│ getProofs()       │   │ Key 自动撤销     │   │                  │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

## 数据流（时序）

```
User          run.py          ServiceRegistry        CAW            Sepolia
 │               │                   │                │               │
 │  discover     │                   │                │               │
 │──────────────>│  listServices()   │                │               │
 │               │──────────────────>│                │               │
 │               │<────[Service[]]───│                │               │
 │<─── 服务列表 ─│                   │                │               │
 │               │                   │                │               │
 │  pay <id>     │                   │                │               │
 │──────────────>│  getService(id)   │                │               │
 │               │──────────────────>│                │               │
 │               │<──Service{price,──│                │               │
 │               │   paymentAddr}    │                │               │
 │               │                   │                │               │
 │               │  pact submit      │                │               │
 │               │──────────────────────────────────>│               │
 │               │                   │                │  Pact 待批准  │
 │               │   通知用户打开 CAW App             │               │
 │               │<──────────────────────────────────│               │
 │  手机批准 Pact │                   │                │               │
 │──────────────>│                   │                │               │
 │               │  tx transfer      │                │               │
 │               │──────────────────────────────────>│               │
 │               │                   │                │   Tx 上链     │
 │               │                   │                │──────────────>│
 │               │                   │                │<──Confirmed──│
 │               │                   │                │               │
 │               │  recordDelivery() │                │               │
 │               │──────────────────>│                │               │
 │               │<──[Proof stored]──│                │               │
 │               │                   │                │               │
 │<── ✅ 完成 ───│                   │                │               │
```

## 安全边界

```
用户意图 → [Guard 检测层*] → 通过 → CAW Pact → 手机批准 → Transfer → 存证
                              ├── 拒绝 → 阻断，不提交 Pact，记录攻击报告
                              └── Guard 检测项：
                                  - Prompt injection（地址/金额篡改）
                                  - 意图与报价不一致
                                  - 目的地不在 allowlist 内
                                  * 开发中，6/8-6/9 集成
```

## 已部署组件

| 组件 | 地址 / 位置 |
|------|------------|
| ServiceRegistry.sol | `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` (Sepolia) |
| CAW Agent | Hermes (wallet: 511ef1fb-90b0-4740-a80f-ce7db6f9c6f9) |
| 注册服务 | 3 个：Research / Data Fetcher / Analyzer |
| 确认交易 | `0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf` |
