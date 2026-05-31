# Week 3｜项目一句话说明

日期：2026-05-31
WCB 任务：Week 3｜最低完成路径｜项目一句话说明

---

## 一句话说明

> **Agent Commerce Sandbox**：一个模拟 x402 paywall + wallet policy + receipt log 的最小验证环境，展示 AI agent 从理解用户目标、发现付费服务、检查安全策略、执行人工确认，到完成模拟支付和产出售后记录的完整商业闭环。

## 备选版本

| 版本 | 侧重 |
|------|------|
| 面向评委版 | A minimal CLI simulator showing how AI agents discover, pay for, and verify paid services within configurable wallet policies |
| 面向同学版 | 一个跑过就能看懂 agent commerce 全流程的命令行 demo，帮你理解 x402 / policy / proof log 到底在解决什么问题 |
| 带标题版 | Agent Commerce Sandbox — 让 agent 学会花钱，但不超过你设定的规矩 |

## 详细展开

- **目标**：让任何人跑一次 CLI 就能看到 agent 从 intent 到 payment 到 proof 的完整流程
- **不做什么**：不接触真实资金，不持有私钥，不连接任何区块链
- **做什么**：services.json + policy.json → mock 402 endpoint → policy check engine → payment simulator → receipt.json + proof.md
- **为什么有意义**：x402、EIP-3009、agent wallet、task-level policy —— 这些概念孤立看都懂，但连起来跑一遍，感觉完全不同
