# Agent Commerce Hub — 完整扩展计划

> AI × Web3 Agentic Builders Hackathon — Cobo 赛道
> 方向 01-05 合并叙事：让 Agent 成为互联网经济的一等公民
> 提交截止：2026-06-13 12:00 UTC+8 | Demo Day：2026-06-14

---

## 一、当前状态（骨架）

```
agent-commerce-sandbox/
├── contracts/
│   └── ServiceRegistry.sol          ← 已写好，待编译部署
├── agent_commerce_sandbox/
│   ├── cobo_client.py               ← 旧代码，待重写为 caw CLI 调用
│   ├── engine.py                     ← 核心流程，需适配合约
│   ├── mock_services.py              ← 将被合约替换
│   ├── policy_checker.py             ← 将被 CAW Pact Policy 替换
│   ├── guard_detector.py             ← 将删除
│   ├── attack_reporter.py            ← 将删除
│   ├── proof_logger.py               ← 将改为链上存证
│   └── chain.py                      ← web3.py 连接，用于合约交互
├── run.py                            ← CLI 入口，需要重写
├── services.json                     ← 被合约替换
├── .env                              ← CAW 凭证已配
└── output/                           ← 输出目录
```

**已验证：** CAW Pact → 批准 → Transfer → 链上交易 ✅

---

## 二、完整愿景 — Agent Commerce Hub

### 一句话

> Agent 通过链上合约发现服务，通过 CAW 完成支付，通过智能合约保障交付，最终形成一个多 Agent 经济体。

### 架构总览

```
┌────────────────────────────────────────────────────────────┐
│                      run.py (CLI)                          │
│  discover | quote | pay | deliver | proof | history       │
└────────────────────┬───────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────┐
│                  ServiceRegistry.sol (Sepolia)              │
│                                                             │
│  register()    — 服务商注册（owner only）                    │
│  listServices() — Agent 发现服务列表                        │
│  getService()   — 单个服务详情                              │
│  recordDelivery() — 交付存证                                │
│  DeliveryProof[] — 完整链上审计追踪                         │
└────────────────────┬───────────────────────────────────────┘
                     │
┌────────────────────▼───────────────────────────────────────┐
│              Cobo Agentic Wallet (CAW)                     │
│                                                             │
│  Pact → 创建权限合约 → 手机批准 → 链上 Transfer             │
│  CAW 处理：钱包管理、权限隔离、链上执行                      │
└─────────────────────────────────────────────────────────────┘
```

### 5 个方向的对应实现

| 方向 | 在项目中的体现 | 关键代码/合约 |
|------|-------------|-------------|
| **① Agent-Native Payments** | Agent 通过 CAW Pact + Transfer 完成支付 | `caw pact submit` → `caw tx transfer` |
| **② Trustless Work Agreements** | 付款通过 CAW Pact 锁定，交付后存证到合约 | `recordDelivery()` 在 ServiceRegistry |
| **③ Resource Procurement** | Agent 查询 ServiceRegistry 合约发现+比价 | `listServices()` + 报价比较逻辑 |
| **④ Autonomous Trading** | (扩展) Agent 执行链上 Swap 等交易 | `caw tx call` 调用 DEX 合约 |
| **⑤ A2A Economy** | 多个 Agent 钱包互付，自动分账 | 配对第二个 CAW Agent |

---

## 三、分阶段实施

### Phase 1 — 核心闭环（P0，1-2 天）

**目标：** 跑通从合约查询 → CAW 支付 → 交付存证的完整链路

| 步骤 | 内容 | 文件/产出 |
|------|------|----------|
| 1.1 | 编译部署 ServiceRegistry.sol 到 Sepolia | `contracts/ServiceRegistry.sol` |
| 1.2 | 注册 3 个 demo 服务到合约（费用写 0.00001 SETH 以适配测试网余额） | `scripts/seed_services.py` |
| 1.3 | 写 `service_registry_client.py` — Python 封装合约调用 | `agent_commerce_sandbox/service_registry_client.py` |
| 1.4 | 重写 `engine.py`：查询合约 → 报价 → CAW Pact → Transfer | `engine.py` |
| 1.5 | 重写 `run.py`：`discover`、`pay` 命令 | `run.py` |
| 1.6 | 验证：`python run.py pay premium-analyzer-04` 跑通全链路 | Demo 验证 |

**验收标准：**
- Agent 从合约查到服务列表（不再是 JSON）
- CAW Pact 创建 + 手机批准
- Transfer 链上确认
- 交付 hash 写入合约

---

### Phase 2 — Demo 打磨（P1，1-2 天）

| 步骤 | 内容 |
|------|------|
| 2.1 | 3 个 Demo 场景：成功支付 / 余额不足 / Policy 拒绝 |
| 2.2 | 彩色 CLI 输出（rich 或 colorama） |
| 2.3 | README：项目定位、架构图、运行说明、CAW 集成说明 |
| 2.4 | Demo 视频脚本（3-5 分钟） |
| 2.5 | 链上证据整理：合约地址、交易 hash、钱包地址 |

---

### Phase 3 — 扩展功能（P2，视时间）

| 步骤 | 内容 | 方向 |
|------|------|------|
| 3.1 | **第二个 Agent 钱包** — 用不同手机再配一个 CAW Agent，模拟 A2A | ⑤ |
| 3.2 | **分账逻辑** — Research Agent 支付后自动拆分给数据提供方和模型方 | ⑤ |
| 3.3 | **caw tx call** — Agent 直接调用 Uniswap 等合约做 Swap | ④ |
| 3.4 | **比价逻辑** — Agent 比较多个服务报价后推荐最优 | ③ |

---

### Phase 4 — 提交准备（P0，截止前）

| 步骤 | 内容 |
|------|------|
| 4.1 | 确保所有代码在 GitHub 上 |
| 4.2 | README 完整 |
| 4.3 | Demo 视频上传 |
| 4.4 | WCB 打卡提交 |

---

## 四、技术细节

### ServiceRegistry 合约部署参数

| 参数 | 值 |
|------|-----|
| 网络 | Sepolia (chain_id: 11155111) |
| Token | SETH (CAW 中 Sepolia ETH) |
| Gas | ~1,000,000 (预计) |
| 部署方式 | 需要 EOA 私钥 + Sepolia ETH（或通过 Remix） |

> 注意：CAW 钱包是 MPC，无法直接用于部署合约。需要用户提供一个外部 EOA 钱包来接部署费用。或者用 Remix IDE + MetaMask 部署。

### Demo 服务初始注册（3 个）

| ID | 名称 | 价格 (SETH) | 等价 USD |
|----|------|------------|---------|
| 1 | Research Notes Generator | 0.00001 | ~$0.00002 |
| 2 | On-chain Data Fetcher | 0.00002 | ~$0.00004 |
| 3 | Premium Market Analyzer | 0.00005 | ~$0.00010 |

> 价格设得很低，因为钱包只有 0.01 SETH，需要留出 gas 费。

### CAW CLI 替代 cobo_client

旧的 `cobo_client.py` 调用 REST API 路径不匹配。改为 Python 调用 `caw` CLI：

```python
import subprocess, json

def submit_pact(intent, policies_json, completion_conditions, execution_plan):
    result = subprocess.run([
        "caw", "pact", "submit",
        "--intent", intent,
        "--policies", policies_json,
        "--completion-conditions", completion_conditions,
        "--execution-plan", execution_plan
    ], capture_output=True, text=True)
    return json.loads(result.stdout)
```

---

## 五、时间线（距截止 6 天）

```
今天        6/8    6/9    6/10   6/11   6/12   6/13 noon
├──Phase 1──┤      │       │      │      │     │
│ 部署+核心跑通     │       │      │      │     │
            ├──Phase 2──────┤      │      │     │
            │ Demo打磨      │      │      │     │
            │       ├──Phase 3─────┤      │     │
            │       │ 扩展功能     │      │     │
            │       │       ├──Phase 4────┤     │
            │       │       │ 提交准备     │     │
            │       │       │              │截止│
```

## 六、当前紧急事项

**优先级最高：**
1. 编译 + 部署 ServiceRegistry.sol（需要 EOA 钱包/私钥/测试网 ETH）
2. 写 service_registry_client.py
3. 重写 run.py 新命令

**需要你提供：**
- 用于部署合约的 Sepolia 钱包私钥（或通过 Remix 部署后给我地址）
- 或者在 CAW App 里看看能不能通过 CAW 部署（可能不行）
