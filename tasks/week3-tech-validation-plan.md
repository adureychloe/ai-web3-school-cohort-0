# 技术验证计划 — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 验证范围

Week 4 需验证的关键技术点，按优先级排列：

### P0 — 已全部验证通过 ✅

| 验证项 | 方法 | 结果 |
|--------|------|------|
| Solidity 合约编译 | `solc` 标准 JSON + viaIR | ✅ 编译成功 |
| 合约部署到 Sepolia | web3.py 部署 `ServiceRegistry.sol` | ✅ Tx: `0xf3d3c114...a9cca` |
| 合约读写 | `listServices()` / `getService()` / `getProofs()` | ✅ 返回正确数据 |
| CAW CLI 安装与配对 | `caw` 命令 + 手机 App 配对 | ✅ Agent: Hermes |
| CAW Pact 提交 | `caw pact submit` 含 intent/policies/completion_conditions | ✅ Pact 已激活 |
| CAW Transfer 执行 | `caw tx transfer` 指定目的地、金额、代币 | ✅ Tx: `0x9b8a70db...a4aedf` |
| 交付存证上链 | `recordDelivery()` 写入合约 | ✅ Block 11008291 |
| Python CLI 全流程 | `run.py discover → pay → proof` | ✅ 端到端跑通 |
| Web UI 展示 | FastAPI + 暗色终端前端 | ✅ 已上线 |

### P1 — 计划中（6/8-6/10）

| 验证项 | 方法 | 预计 |
|--------|------|------|
| Python SDK 替换 CLI | `cobo-agentic-wallet` → WalletAPIClient | 6/8 |
| 自主采购 Agent | `procurement_agent.py` + `run.py procure` | 6/8 |
| Guard 安全层集成 | 在 Pact 提交前检测 prompt injection | 6/8-6/9 |
| HTTP 402 付费 API | 本地 endpoint → 402 → CAW 支付 → 解锁 | 6/9 |

### P2 — 视时间

| 验证项 | 方法 |
|--------|------|
| ServiceRegistry V2（加强存证结构） | 含 pactId / intentHash / policyHash / artifactHash |
| 多 Agent 经济（A2A） | 第二个 CAW 钱包互付 |
| caw tx call 合约调用 | Agent 直接调用 DEX 等合约 |

---

## 测试网环境

| 项目 | 值 |
|------|-----|
| 网络 | Sepolia (chain_id: 11155111) |
| RPC | `https://ethereum-sepolia-rpc.publicnode.com` |
| 合约地址 | `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` |
| CAW 钱包 | Hermes (`0x9e01312e8e96a8133a3c73bed58a5808ecfceaf5`) |
| 余额 | 0.01 SETH（够 Demo） |

---

## Demo 验证流程

```
1. python run.py discover          → 显示 3 个链上服务
2. python run.py pay 1             → CAW Pact → 手机批准 → Transfer → 存证
3. python run.py proof             → 显示链上交付记录
4. python run.py status            → 显示钱包+合约状态
```
