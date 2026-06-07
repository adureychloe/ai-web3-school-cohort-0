# Week 3｜Hackathon Direction Card

> 更新日期：2026-06-07  
> 项目已从模拟原型升级为真实链上 + CAW 集成

---

## 1. 项目身份

| 字段 | 内容 |
|------|------|
| **项目名称** | **Agent Commerce Hub** (原 Agent Commerce Sandbox → 升级) |
| 一句话 tagline | Agent 通过链上合约发现服务 → CAW 支付 → 链上交付存证，实现真实的 Agentic Commerce 闭环 |
| 项目形态 | CLI + Web UI + 部署在 Sepolia 的 Solidity 合约 + Cobo Agentic Wallet 集成 |
| 当前阶段 | Week 4 冲刺 — 完整端到端流程已跑通，打磨 Demo 中 |

## 2. 要解决什么问题

> AI Agent 想帮用户购买服务时，如何安全地完成 **发现 → 报价 → 授权 → 支付 → 存证** 的完整流程？

痛点：
- 用户想给 Agent 花钱权限，但怕超支、付错人、被 prompt injection 欺骗
- Agent 能理解任务，但缺乏在链上发现服务、自主发起支付、记录交付证明的能力
- 现有方案要么给全量 API Key（太危险），要么次次手动签名（无法自动化）
- Cobo Agentic Wallet 提供了 Pact 授权模型，但缺少一个完整的「服务发现→支付→交付」Demo

## 3. 解决方案

**Agent Commerce Hub** — Agent 通过链上合约发现服务 → 创建 CAW Pact 获取有限支付授权 → 执行 Transfer → 记录交付存证回链上：

```
ServiceRegistry.sol (Sepolia)
       ↓ Agent 查询合约获取服务列表+报价
CLI (run.py) / Web UI
       ↓ Agent 创建 CAW Pact
CAW Pact → 手机 App 批准
       ↓ CAW 执行链上 Transfer
链上交易确认
       ↓ Agent 调用合约 recordDelivery()
交付 Hash 写入链上存证
```

**核心特点：**
- ✅ **真实链上交互** — ServiceRegistry.sol 已部署到 Sepolia
- ✅ **真实 CAW 支付** — 通过 Cobo Agentic Wallet Pact + Transfer 完成
- ✅ **动态 Policy** — Pact policy 从合约字段动态生成，限制支付对象和金额
- ✅ **端到端已跑通** — 合约查询 → Pact → 批准 → Transfer → 链上证（tx: `0x9b8a70db...a4aedf`）
- ✅ **实时可忽略攻击** — 防 prompt injection 的 Guard 层在 Pact 提交前拦截

## 4. Target User

- AI Agent 开发者：需要一个即开即用的「Agent 如何安全支付」参考实现
- Cobo Agentic Wallet 用户：展示 Pact 在真实场景中的运作
- Hackathon 评委：展示 Agent 商业闭环 + 风险边界 + CAW 集成完整度

## 5. 关键组件

| 组件 | 说明 | 状态 |
|------|------|------|
| `contracts/ServiceRegistry.sol` | 链上服务注册合约，支持 register / listServices / getService / recordDelivery | ✅ 已部署 Sepolia |
| `agent_commerce_sandbox/caw_client.py` | Python 封装 `caw` CLI：Pact 提交、Transfer 执行、状态轮询 | ✅ 已实现 |
| `agent_commerce_sandbox/chain_client.py` | web3.py 封装合约交互：服务发现、交付存证 | ✅ 已实现 |
| `agent_commerce_sandbox/engine.py` | 核心编排：5 步流程（发现→Pact→等待→转账→存证） | ✅ 已实现 |
| `run.py` | CLI 入口：discover / pay / proof / status 命令 | ✅ 已实现 |
| `web/app.py + index.html` | FastAPI + 暗色终端主题 Web 界面 | ✅ 已实现 |
| Guard 安全层 | Pact 提交前的 Prompt Injection / 地址篡改检测 | 🚧 集成中 |

## 6. Tech Stack

| 层 | 技术 |
|----|------|
| 合约层 | Solidity 0.8.20 → Sepolia (chain_id: 11155111) |
| 支付层 | Cobo Agentic Wallet — `caw` CLI (Pact → Transfer) |
| 客户端 | Python 3.11 + web3.py + FastAPI |
| 前端 | 原生 HTML/CSS/JS → 暗色终端风格 |
| 钱包 | CAW Agent: Hermes (0x9e0131...) + EOA 部署钱包 |
| 代码 | GitHub: `github.com/adureychloe/ai-web3-school-cohort-0` |

## 7. AI × Web3 交叉点

| 环节 | AI 做什么 | Web3 / CAW 做什么 |
|------|----------|------------------|
| Intent | 解析用户目标（procurement agent 即将加入） | — |
| Service Discovery | 匹配语义→选择最佳服务 | ServiceRegistry.sol 链上查询 |
| Authorization | 解释风险→生成 Pact 草案 | CAW Pact 策略创建 |
| Payment | 自动发起支付流程 | CAW Transfer → 链上确认 |
| Proof | 生成交付摘要 | ServiceRegistry.recordDelivery() 存证 |
| Security | Guard 层检测 prompt injection | CAW 链上 Policy 强制执行 |

## 8. 为什么它不是纯 AI 或纯 Web3

- **纯 AI**：可以解析意图和做决策，但不能安全地执行链上支付
- **纯 Web3**：可以转账和存证，但不会理解用户到底需要什么服务
- **交叉点**：AI 负责商业决策和安全检查，CAW 负责受权的资金执行，合约负责不可篡改的记录

## 9. 成功标准

- [x] CLI 能完整跑通: `discover` → `pay` → `proof`
- [x] CAW Pact 创建 → 手机批准 → Transfer → 链上确认
- [x] 交付 proof 写入 Sepolia 合约
- [x] Web UI 可展示全流程
- [ ] Demo 视频录制（3-5 分钟）
- [ ] README 完整更新
