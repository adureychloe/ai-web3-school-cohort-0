# Agent Commerce Hub

> AI × Web3 Agentic Builders Hackathon — Cobo 赛道  
> 一个 Web3 原生服务市场：Seller Agent 把服务注册到链上，Buyer Agent 用 Cobo Agentic Wallet 通过 x402 自动购买，交付结果写回链上形成可审计证明。

---

## 一句话

**Agent Commerce Hub 让 AI Agent/服务商把可调用服务发布到 `ServiceRegistryV2`，让买家或 Buyer Agent 通过 x402 + Cobo Agentic Wallet 完成授权支付，并把交付证明留存在 Sepolia 合约上。**

## 当前状态

当前版本已经不是早期的 mock/手动付款 demo，而是一个可运行的 **ServiceRegistryV2 + x402 + CAW** 闭环：

- **链上服务发现**：默认读取 Sepolia `ServiceRegistryV2`，legacy V1 仅保留在 `/api/legacy/*` 调试路径。
- **公开服务注册**：Seller 可以把服务名称、描述、价格、endpoint、收款地址发布到链上。
- **x402 服务调用**：买家访问服务 endpoint 时先收到 `402 payment_required`，再由后端 CAW 自动完成 Pact/Transfer。
- **Buyer CAW 会话**：Web UI 有全局 Buyer CAW Wallet 区块，连接一次后可复用于服务卡片、`Find & Pay` 和 Direct x402 Checkout，也可断开连接。
- **Seller 自服务管理**：Seller 连接浏览器钱包后，可查看自己注册的服务，并更新或下架自己拥有的服务；历史交付证明不删除。
- **链上交付证明**：支付和交付记录写入合约，形成可验证审计轨迹。
- **Agent 化方向清晰**：现有 Web UI 是人类控制台；同一套 API 可以给 Seller Agent、Buyer Agent 和 Broker/Procurement Agent 调用。

## 架构

```text
┌──────────────────────────────────────────────────────────────┐
│                        Web UI / CLI                          │
│  Buyer Dashboard │ Seller Dashboard │ Direct x402 Checkout   │
│  run.py discover/pay/procure/status/proof                    │
└───────────────┬───────────────────────────────┬──────────────┘
                │                               │
                ▼                               ▼
┌──────────────────────────────┐   ┌───────────────────────────┐
│ FastAPI Marketplace API       │   │ x402 Seller Server         │
│ /api/services                 │   │ /request                   │
│ /api/procure                  │   │ /services                  │
│ /api/x402-buy                 │   │ /register_v2               │
│ /api/proofs /api/status       │   │ /seller/update_v2          │
│ /api/legacy/*                 │   │ /seller/remove_v2          │
└───────────────┬──────────────┘   └──────────────┬────────────┘
                │                                 │
                ▼                                 ▼
┌──────────────────────────────────────────────────────────────┐
│             ServiceRegistryV2 on Sepolia                     │
│  public register │ list/get services │ update │ deactivate   │
│  recordDelivery │ DeliveryProof[] audit trail                 │
└──────────────────────────────┬───────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────┐
│              Cobo Agentic Wallet (CAW)                       │
│  Pact policy → user approval → server-side auto-pay Transfer │
│  Buyer CAW address is shown in UI; actual demo auto-pay uses │
│  the configured server CAW wallet.                           │
└──────────────────────────────────────────────────────────────┘
```

## Demo 流程

### 1. Seller 注册服务

1. Seller 在 Web UI 连接 MetaMask/Rabby 等浏览器钱包。
2. 填写服务名称、描述、价格、endpoint URI、收款地址。
3. 提交到 `ServiceRegistryV2`。
4. 服务进入 buyer discovery，可被 Web UI、CLI 或 Agent 发现。

### 2. Buyer 发现并购买服务

1. Buyer 在 Web UI 选择/连接 Buyer CAW Wallet。
2. 输入需求，点击 **Find Service** 或 **Find & Pay**。
3. 系统从 `ServiceRegistryV2` 拉取服务并做匹配。
4. 购买时调用 x402 endpoint，服务端返回 `402 payment_required`。
5. 后端会在 CAW 转账前用当前 x402 payment amount 重新校验最大预算，然后通过 CAW 创建/复用 Pact，用户在 CAW App 批准后自动转账。
6. 服务返回交付内容，支付/交付证明写入链上。

### 3. Seller 管理服务

1. Seller 连接注册服务时使用的钱包。
2. 在 **My Services** 中查看自己拥有的 ServiceRegistryV2/x402 服务。
3. 可更新服务 metadata，或通过 `deactivate()` 从 buyer discovery 中下架。
4. 删除是软删除：历史 proof 和链上记录仍可审计。

## Agent 化设计

Web UI 只是演示控制台；真正的目标是让 Agent 自动完成注册、发现、购买、验证。

| Agent | 能力 | 当前对应能力 | 当前 Agent API |
|---|---|---|---|
| **Seller Agent** | 根据服务描述自动发布/更新服务 | `POST /api/agent/seller/register`, `/api/x402/seller/update_v2` | `POST /api/agent/seller/register` |
| **Buyer Agent** | 根据任务意图发现、预算过滤、购买、验收 | `/api/services`, `/api/procure`, `/api/x402-buy` | `POST /api/agent/buyer/procure` |
| **Broker / Procurement Agent** | 多服务比价、选择最优服务、返回 proof | `procurement_agent.py`, `run.py procure` | 规则版 → LLM reasoning |

MVP Agent 路径：

```text
user intent
  → Buyer Agent parses budget / desired output
  → reads ServiceRegistryV2 services
  → ranks candidates by keyword + price + availability
  → calls x402 endpoint
  → CAW Pact / Transfer
  → validates delivery
  → returns content + on-chain proof
```

## 快速开始

### 前置条件

- Python 3.11+
- Node.js（用于前端脚本检查，可选）
- Cobo Agentic Wallet CLI (`caw`) 和已配对的钱包
- Sepolia ETH / SETH 测试资产
- 浏览器钱包（Seller 注册、更新、下架服务时使用）

### 安装

```bash
cd agent-commerce-sandbox
pip install -r requirements.txt
```

### 配置

- CAW 凭证由本机 `caw` CLI 读取，不提交到 Git。
- V2 合约部署信息在 `contracts/deployed_v2.json`。
- Legacy V1 合约部署信息在 `contracts/deployed.json`，仅用于 `/api/legacy/*` 调试路径。

### 启动 Web Demo

```bash
python3 -m uvicorn web.app:app --host 0.0.0.0 --port 8080 --timeout-keep-alive 600
```

打开：`http://localhost:8080`

### CLI 用法

```bash
# 查看链上服务列表
python run.py discover

# 自然语言采购
python run.py procure "帮我写一份 ETH 市场分析报告"

# Buyer Agent API 匹配（需先启动 Web API，可选预算 SETH）
python run.py buyer-agent "Find market analysis for an AI commerce launch" 3

# Seller Agent API 注册（需先启动 Web API；如配置 DEMO_ADMIN_TOKEN，CLI 会自动带上）
python run.py seller-agent "Sell weekly AI x Web3 market intelligence" 0.00005 https://seller.example.com 0x1111111111111111111111111111111111111111

# 指定服务 ID 支付
python run.py pay 1 "帮我做 Web3 市场研究"

# 查看交付存证
python run.py proof

# 系统状态
python run.py status

# 启动 x402 seller 服务
python run.py serve 8888

# 指定服务 ID 走 x402 auto-pay
python run.py request 1 "生成一份研究摘要"
```

## 主要 API

### Buyer / Marketplace

| Method | Path | 说明 |
|---|---|---|
| `GET` | `/api/services` | 默认 V2/x402 服务发现 |
| `GET` | `/api/services/all` | V2 服务，可选包含 legacy |
| `POST` | `/api/procure/match` | 根据需求匹配服务 |
| `POST` | `/api/procure` | 匹配并购买 |
| `POST` | `/api/agent/seller/register` | Seller Agent：根据服务 brief 生成 V2/x402 metadata，并复用注册安全门槛写入 ServiceRegistryV2 |
| `POST` | `/api/agent/buyer/procure` | Buyer Agent：按预算过滤 V2/x402 服务、排序，`auto_pay=true` 时会在 CAW transfer 前重新校验当前 x402 价格不超过最大预算 |
| `POST` | `/api/x402-buy` | 指定服务直接走 x402/CAW auto-pay |
| `GET` | `/api/proofs` | V2 交付证明 |
| `GET` | `/api/status` | 系统状态 |

Buyer Agent example:

```bash
curl -X POST http://127.0.0.1:8080/api/agent/buyer/procure \
  -H 'Content-Type: application/json' \
  -d '{"request":"Find market analysis","budget_seth":"3","auto_pay":false}'
```

### x402 Seller

| Method | Path | 说明 |
|---|---|---|
| `POST` | `/api/x402/request` | x402 payment-required probe |
| `POST` | `/api/x402/register_v2` | 注册 V2 服务 |
| `GET` | `/api/x402/seller/services_v2` | Seller 查看自己服务 |
| `POST` | `/api/x402/seller/update_v2` | Seller 自服务更新 |
| `POST` | `/api/x402/seller/remove_v2` | Seller 自服务下架 |
| `GET` | `/api/x402/health` | x402 seller server 健康检查 |

### Legacy

旧版 V1 路径保留在 `/api/legacy/*`，不再作为默认 buyer/seller 流程。

## 链上证据

### ServiceRegistryV2

| 项目 | 值 |
|---|---|
| 合约 | `ServiceRegistryV2.sol` |
| 网络 | Sepolia (`chain_id: 11155111`) |
| 地址 | [`0x3f945ba7BFE2181B506390c0C5e9d2328495Cc40`](https://sepolia.etherscan.io/address/0x3f945ba7BFE2181B506390c0C5e9d2328495Cc40) |
| 部署 Tx | [`0x8e6ca555c927a5c9416a0db037ed70847c2592e650ce56ac60d4c281b6e1e18c`](https://sepolia.etherscan.io/tx/0x8e6ca555c927a5c9416a0db037ed70847c2592e650ce56ac60d4c281b6e1e18c) |

### Legacy ServiceRegistry V1

| 项目 | 值 |
|---|---|
| 合约 | `ServiceRegistry.sol` |
| 网络 | Sepolia (`chain_id: 11155111`) |
| 地址 | [`0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3`](https://sepolia.etherscan.io/address/0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3) |

## 技术栈

| 层 | 技术 |
|---|---|
| 链上 | Solidity 0.8.x, Sepolia, `ServiceRegistryV2` |
| 后端 | Python 3.11+, FastAPI, web3.py |
| 支付 | Cobo Agentic Wallet, CAW Pact, x402-style HTTP payment flow |
| 前端 | HTML + CSS + vanilla JS |
| Agent | `procurement_agent.py`, `run.py procure`, planned Agent APIs |

## 项目结构

```text
agent-commerce-sandbox/
├── agent_commerce_sandbox/
│   ├── caw_client.py            # CAW CLI 封装与 Pact/Transfer 编排
│   ├── chain_client.py          # Legacy V1 合约客户端
│   ├── chain_client_v2.py       # ServiceRegistryV2 合约客户端
│   ├── engine.py                # Legacy 支付编排
│   ├── procurement_agent.py     # 自然语言采购 / 匹配逻辑
│   ├── x402_client.py           # Buyer 侧 x402/CAW 客户端
│   └── x402_server.py           # Seller 侧 x402 服务与 V2 管理 API
├── contracts/
│   ├── ServiceRegistry.sol
│   ├── ServiceRegistryV2.sol
│   ├── deployed.json
│   └── deployed_v2.json
├── scripts/
│   ├── deploy_v2.py
│   └── register_demo_services_v2.py
├── web/
│   ├── app.py                   # FastAPI marketplace API
│   └── index.html               # Buyer/Seller Web 控制台
├── run.py                       # CLI 入口
└── README.md
```

## 安全边界

- **CAW 授权边界**：资金操作通过 CAW Pact 限定链、代币、金额、收款地址和操作类型。
- **测试网隔离**：当前演示使用 Sepolia / SETH 测试资产。
- **密钥不入库**：CAW 凭证、私钥、API Key 不写入 README，不提交到 Git。
- **前端只展示地址语义**：Buyer CAW 地址用于 UI/记录/演示；实际 demo auto-pay 由后端配置的 server CAW wallet 执行。
- **Seller 自服务权限**：Seller 更新/下架需要证明自己拥有对应服务；server-owned/debug 管理能力不暴露为普通 buyer/seller 删除入口。
- **历史可审计**：下架是 `deactivate()`，历史 proof 和链上记录保留。

## 评审标准对齐

| 维度 | 实现 |
|---|---|
| 场景贴合度 | Agent 发现链上服务，通过 x402/CAW 购买，交付结果链上存证 |
| CAW 关键性 | CAW Pact/Transfer 是支付授权和执行核心 |
| Agent-Native | Web UI 与 CLI 只是控制面；服务注册、发现、购买、验收均可由 Agent API 调用 |
| 可演示性 | Buyer Dashboard + Seller Dashboard + Direct x402 Checkout + CLI |
| 风险边界 | Pact policy、测试网、敏感信息隔离、Seller ownership/self-service 校验 |

## 开发检查

```bash
python3 -m py_compile web/app.py agent_commerce_sandbox/*.py
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
HTMLParser().feed(Path('web/index.html').read_text())
print('html parser ok')
PY
```

## License

MIT
