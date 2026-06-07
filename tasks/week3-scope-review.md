# Scope Review — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 项目范围声明

Agent Commerce Hub 在 Week 4 的核心范围是：
> Agent 通过链上合约发现服务 → CAW Pact 授权支付 → 执行 Transfer → 交付存证

## 不做 / 延后的功能

| # | 功能 | 决定 | 原因 |
|---|------|------|------|
| 1 | **ServiceRegistry V2 合约** | 延后 | 当前合约（含 register/listServices/getService/recordDelivery/getProofs）已满足 Demo 需求。V2 加入更强的存证结构（pactId/intentHash/artifactHash）是锦上添花，不是必要的。 |
| 2 | **多 Agent 经济（A2A）** | 延后 | 需要第二个 CAW 钱包（另一台手机/另一个 App 实例），配置复杂。Demo 展示单 Agent 支付完全足够证明 CAW 关键性。 |
| 3 | **Autonomous Trading（caw tx call DEX 交互）** | 延后 | 偏离核心叙事（Agent 找工作流而非自主交易）。CAW 的 contract call 能力作为扩展方向标注即可。 |
| 4 | **完整的 x402 标准实现** | 简化 | 实现本地模拟 402 端点即可展示概念，不需要完全兼容 x402 规范。CAW 的 `caw fetch` recipe 已有标准实现。 |
| 5 | **Web UI 大范围美化** | 简化 | 暗色终端风格已可用，不花时间做复杂的动画/交互。核心是功能演示。 |
| 6 | **多语言支持** | 砍掉 | Demo 使用中文 CLI 输出即可，不考虑国际化。 |

## 保留的核心范围

| 功能 | 理由 |
|------|------|
| CLI (run.py) + Web UI (FastAPI) | 双入口，评委可以用最舒服的方式体验 |
| CAW Pact + Transfer | 赛道核心要求 |
| 链上服务注册 + 存证 | Web3 不可篡改性证明 |
| procurement agent（自然语言采购） | P0 改进，增加自主感 |
| Guard 安全层 | 直接对评审"风险边界"标准 |
| HTTP 402 付费 API | 让 Demo 有真实产出物 |

## 时间分配

```
6/8-6/9: 只做 P0（采购 Agent + Guard + 402 API）
6/10-6/11: Demo 打磨 + 录视频
6/12: 提交准备（不做新功能）
6/13 中午: 截止
```
