# Agent Commerce Hub

> AI × Web3 Agentic Builders Hackathon — Cobo 赛道  
> 让 Agent 通过链上合约发现服务，通过 CAW 安全支付，通过智能合约存证交付

---

## 项目概览

Agent Commerce Hub 是一个 **Agent-Native Payment** 参考实现，展示 AI Agent 如何：

1. **发现服务** — 查询 `ServiceRegistry.sol` 链上合约获取服务列表
2. **授权支付** — 通过 Cobo Agentic Wallet (CAW) 创建 Pact，限定金额、链、收款地址
3. **执行转账** — 用户在 CAW App 批准后，CAW 链上执行 Transfer
4. **交付存证** — 将支付 hash 写入合约，形成不可篡改的审计追踪

## 架构

```
┌──────────────┐     ┌──────────────────────┐     ┌───────────────────┐
│  CLI (run.py)│     │  Web UI (FastAPI)     │     │  Procurement      │
│  │           │     │  │                    │     │  Agent            │
│  discover    │     │  /api/services        │     │  natural language │
│  pay         │     │  /api/pay             │     │  → match → pay    │
│  procure     │     │  /api/procure/match   │     │                   │
│  proof       │     │  /api/procure         │     │                   │
│  status      │     │  /api/pact/{id}/status│     │                   │
└──────┬───────┘     └──────────┬────────────┘     └────────┬──────────┘
       │                        │                           │
       └────────────────────────┼───────────────────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  ServiceRegistry.sol    │
                    │  (Sepolia)              │
                    │  register / list        │
                    │  get / recordDelivery   │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │  Cobo Agentic Wallet    │
                    │  (CAW)                 │
                    │  Pact → Transfer        │
                    │  Policies / Completion  │
                    └────────────────────────┘
```

## 快速开始

### 前置条件

- Python 3.11+
- Cobo Agentic Wallet CLI (`caw`) — [安装指南](https://www.cobo.com/products/agentic-wallet/manual/start-here/introduction)
- CAW 钱包已配对 ([iOS](https://apps.apple.com/app/id6761912352) / [Android](https://play.google.com/store/apps/details?id=com.cobo.agenticwallet))
- Sepolia ETH（合约部署用）

### 安装

```bash
cd agent-commerce-sandbox
pip install -r requirements.txt
```

### 配置

CAW 凭证自动从 `~/.cobo-agentic-wallet/` 读取。合约部署信息在 `contracts/deployed.json`。

### CLI 用法

```bash
# 查看链上服务列表
python run.py discover

# 自然语言采购（推荐）
python run.py procure "帮我写一份ETH市场分析报告"

# 指定服务 ID 支付
python run.py pay 1 "帮我做Web3市场研究"

# 查看交付存证
python run.py proof

# 系统状态
python run.py status
```

### Web UI

```bash
python -m uvicorn web.app:app --host 0.0.0.0 --port 8080
```

打开浏览器访问 `http://localhost:8080`

支持两种操作模式：
- **Find Service** — 输入需求 → 匹配排名 → 手动确认支付
- **Find & Pay** 🚀 — 输入需求 → 自动匹配 → 一键全流程

## CAW 集成说明

### 核心集成点

| 模块 | 位置 | 说明 |
|------|------|------|
| CAW CLI 封装 | `agent_commerce_sandbox/caw_client.py` | Python subprocess 调用 `caw` CLI |
| 支付编排 | `agent_commerce_sandbox/engine.py` | 5步流程：查合约→Pact→批准→Transfer→存证 |
| 余额检查 | `agent_commerce_sandbox/procurement_agent.py` | `get_balance()` 查询 SETH 余额 |
| Web API | `web/app.py` | `/api/pay`, `/api/pact/{id}/status` |

### CAW 支付流程

```
1. caw pact submit --intent "..." --policies '[...]' --completion-conditions '[...]'
2. User approves in CAW App (手机批准)
3. caw tx transfer --pact-id <uuid> --src-address <addr> --dst-address <addr> --amount <n> --token-id SETH --chain-id SETH
4. caw tx get --tx-id <uuid> → 确认链上交易
```

策略 (Policies) 动态生成，限制：
- 只能向指定服务商地址付款
- 只能在 SETH 链上使用 SETH
- 单笔上限 $5.00 USD

### 关键 CAW 凭证

| 项目 | 值 |
|------|-----|
| Agent | Hermes |
| Wallet UUID | `511ef1fb-90b0-4740-a80f-ce7db6f9c6f9` |
| SETH 地址 | `0x9e01312e8e96a8133a3c73bed58a5808ecfceaf5` |
| API Base | `https://api.agenticwallet.cobo.com` |

## 链上证据

### 合约

| 项目 | 值 |
|------|-----|
| 合约 | `ServiceRegistry.sol` |
| 网络 | Sepolia (chain_id: 11155111) |
| 地址 | [`0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3`](https://sepolia.etherscan.io/address/0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3) |
| 部署 Tx | `0xf3d3c11403a733f6a57213cf5caeb05e58191a8063c4cb80a28f20e4085a9cca` |

### 已注册服务

| ID | 名称 | 价格 (SETH) |
|----|------|------------|
| 1 | Research Notes Generator | 0.00001 |
| 2 | On-chain Data Fetcher | 0.00002 |
| 3 | Premium Market Analyzer | 0.00005 |

### 支付交易

| 交易 | Hash |
|------|------|
| CAW Transfer | [`0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf`](https://sepolia.etherscan.io/tx/0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf) |

## 技术栈

| 层 | 技术 |
|----|------|
| 链上 | Solidity 0.8.x, Sepolia |
| 后端 | Python 3.11+, FastAPI, web3.py |
| 钱包 | Cobo Agentic Wallet (CAW), `caw` CLI |
| 前端 | HTML + CSS + vanilla JS |
| 工具 | Claude Code, Codex CLI |

## 项目结构

```
agent-commerce-sandbox/
├── agent_commerce_sandbox/
│   ├── __init__.py
│   ├── chain_client.py          # web3.py 合约交互
│   ├── caw_client.py            # CAW CLI 封装
│   ├── engine.py                # 5步支付编排
│   └── procurement_agent.py     # 自然语言采购
├── contracts/
│   ├── ServiceRegistry.sol      # Solidity 合约
│   ├── ServiceRegistry.abi.json
│   └── deployed.json            # 部署信息
├── web/
│   ├── app.py                   # FastAPI 后端
│   └── index.html               # 前端页面
├── run.py                       # CLI 入口
└── README.md
```

## 安全边界

- **Pact 策略限制** — 每笔支付都通过 CAW Pact 限定链、代币、金额和收款地址
- **测试网资产** — 所有交互使用 Sepolia 测试网 SETH，无真实资金风险
- **API Key 隔离** — CAW API Key 存储于 `~/.cobo-agentic-wallet/`，不提交到 Git
- **Web API 安全** — Pact 数据返回浏览器前自动剥离 `api_key` 等敏感字段
- **人工审批** — 每笔支付需用户在 CAW App 批准，Agent 不能单方面执行

## 评审标准对齐

| 维度 | 实现 |
|------|------|
| 场景贴合度 | Agent 通过链上合约发现付费服务，通过 CAW 完成支付和存证 |
| CAW 关键性 | CAW 是支付流程中不可替代的核心组件（Pact → Transfer） |
| 资金流程完整度 | 任务触发 → 合约查询 → Pact 创建 → App 批准 → Transfer → 链上存证 |
| 可演示性 | CLI + Web UI 双入口，支持自然语言采购一键流程 |
| 风险边界说明 | Pact 策略、测试网隔离、API Key 保护、人工审批机制 |

## 开发

```bash
# 编译检查
python3 -m py_compile run.py
python3 -m py_compile web/app.py

# 跑通全链路（需要 CAW 钱包）
python run.py status
python run.py discover
python run.py procure "测试"
```

## 许可证

MIT
