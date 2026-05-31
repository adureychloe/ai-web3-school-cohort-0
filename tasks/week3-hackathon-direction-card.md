# Week 3｜Hackathon Direction Card

日期：2026-05-31
WCB 任务：Week 3｜最低完成路径｜Hackathon Direction Card
前置：Week 2 总交付 Proposal（Agent Commerce Sandbox）

---

## 1. 项目身份

| 字段 | 内容 |
|------|------|
| 项目名称 | **Agent Commerce Sandbox** |
| 一句话 tagline | 模拟 agent 从 intent → payment → proof 的完整商业闭环 |
| 项目形态 | CLI 原型 + mermaid 流程图 + 决策日志 |
| 当前阶段 | Week 3 — Hackathon 启动，原型搭建 |

## 2. 要解决什么问题

> AI agent 帮用户购买服务时，钱怎么付、谁来确认、怎么验证、失败了怎么办？

具体痛点：
- 用户不想每次小额付款都亲自签名交易，但又怕 agent 超预算或付错人
- Agent 能理解任务，但没法"签合同、付钱、拿收据"
- 现有方案要么太松（直接给 API Key），要么太紧（每次确认，无法自动化）
- x402、EIP-3009、ERC-8004 等新标准没有可演示的集成环境

## 3. 解决方案

一个 **最小验证环境**，模拟 agent commerce 的完整流程：

```
User Intent → Service Discovery → Quote (x402) → Policy Check →
Human Confirmation (高风险时) → Payment Simulation (x402/EIP-3009 mock) →
Service Delivery → Acceptance Check → Proof Log
```

特点是：
- **不接触真实资金** — 所有支付是模拟的，安全边界验证
- **不持有私钥** — 不存在热钱包风险
- **可演示** — 跑一遍 CLI 就能看到整个流程和决策输出
- **可攻击** — 内置超预算、未知服务、prompt injection 等测试用例

## 4. Target User

- AI × Web3 School 同学：想理解 x402 / agent wallet / policy 如何工作
- Hackathon 参赛者：需要一个可演示的 demo 原型
- 产品学习者：想理解 agent commerce 的最小闭环长什么样

## 5. 关键组件

| 组件 | 说明 | 文件/形态 |
|------|------|-----------|
| services.json | 模拟服务列表，含名称、价格、交付物 | 配置文件 |
| policy.json | 预算、allowlist、单笔限额、操作规则 | 配置文件 |
| Mock 402 Endpoint | 服务返回报价（静态模拟） | 本地模拟 |
| Policy Check Engine | 检查是否允许执行 | 逻辑核心 |
| Human Confirmation Gate | 新服务/超额时暂停 | 交互流程 |
| Payment Simulator | 模拟 x402 / EIP-3009 支付 | 模拟输出 |
| receipt.json | 每次交易的完整记录 | JSON 输出 |
| proof.md | 可读的 proof-of-work 摘要 | 输出文件 |

## 6. Tech Stack

- **语言**：Python 3（轻量，无额外框架）
- **存储**：本地 JSON 文件（simulation mode）
- **无**：数据库、区块链节点、钱包、智能合约
- **未来可扩展**：真实 x402 SDK、CAW / Safe 集成

## 7. AI × Web3 交叉点

| 环节 | AI 做什么 | Web3 / 协议做什么 |
|------|----------|------------------|
| Intent | 理解"帮我买份研究资料"→ 结构化任务 | — |
| Discovery | 匹配 services.json 中的服务 | ERC-8004（未来） |
| Quote | 比较报价和交付条件 | x402 / HTTP 402 |
| Policy Check | 解释风险，生成决策摘要 | wallet policy / guard |
| Payment | 发起模拟付款 | EIP-3009（未来） |
| Receipt | 生成可读的交付摘要 | proof log / receipt hash |
| Dispute | 判断交付是否符合预期 | 争议记录（未来） |

## 8. 为什么它不是纯 AI 或纯 Web3

- **纯 AI**：可以做 intent parsing 和 risk explanation，但钱不能只听一句话就付出去
- **纯 Web3**：可以做转账和签名验证，但不会理解用户到底想买什么
- **交叉点**：AI 帮用户做商业决策和理解，Web3 帮用户做权限边界和可验证记录

## 9. 成功标准

- [ ] CLI 运行一次能看到完整流程
- [ ] 三种场景演示：正常支付、超预算拒绝、未知服务拦截
- [ ] 每次运行产出 receipt.json + proof.md
- [ ] mermaid 流程图与代码流程一致
- [ ] Week 4 可以展示给 mentor 和同学

## 10. 风险提示

| 风险 | 缓解 |
|------|------|
| Week 3 只有 1 小时/天 | 先做核心闭环（intent → payment），不做 UI |
| 模拟环境无法演示真实 x402 | 在代码注释中标注"此处可替换为真实 x402 SDK" |
| 项目太抽象难以演示 | 准备 3 个固定测试场景，跑一次 CLI 就能看到 |
