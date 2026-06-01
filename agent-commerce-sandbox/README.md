# Agent Commerce Sandbox

模拟 AI agent 从 intent → quote → policy check → payment simulation → delivery → proof log 的完整商业闭环。

## 快速开始

```bash
cd agent-commerce-sandbox
python run.py
```

## 项目结构

```
agent-commerce-sandbox/
├── README.md                  # 本文件
├── requirements.txt           # 依赖
├── run.py                     # CLI 入口
├── services.json              # 模拟服务列表
├── policy.json                # 钱包策略配置
├── scenarios/                 # 测试场景
│   ├── normal_payment.py      # 正常支付场景
│   ├── over_budget.py         # 超预算场景
│   └── unknown_service.py     # 未知服务场景
└── agent_commerce_sandbox/    # 核心 Python 模块
    ├── __init__.py
    ├── engine.py              # 核心流程引擎
    ├── policy_checker.py      # 策略检查引擎
    ├── payment_simulator.py   # 模拟 x402 / EIP-3009 支付
    ├── mock_services.py       # 模拟服务定义
    └── proof_logger.py        # 收据和证明日志
```

## 核心流程

```
User Intent → Service Discovery → Quote → Policy Check →
  ├─ 通过 + 低风险 → Payment Simulation → Delivery → Proof Log
  └─ 未授权 / 高风险 → Human Confirmation →
        ├─ 确认 → Payment
        └─ 拒绝 → Stop + Log
```

## 三种演示场景

| 场景 | 说明 | 预期结果 |
|------|------|----------|
| normal_payment | 用户在 allowlist 中、预算内，购买已知服务 | 自动通过，输出 receipt |
| over_budget | 请求金额超过预算限制 | 被 policy 拒绝，记录原因 |
| unknown_service | 请求的服务不在 allowlist 中 | 触发人工确认流程 |

## 设计原则

- **不接触真实资金** — 所有支付是模拟的
- **不持有私钥** — 不存在热钱包风险
- **可演示** — 跑一次 CLI 就能看到完整流程
- **安全边界清晰** — 预算、allowlist、单笔限额、人工确认门

## 未来扩展

- 接入真实 Cobo CAW SDK / x402 Payment recipe
- 集成 EIP-3009 transferWithAuthorization
- 连接 ERC-8004 服务发现和 reputation
- 替换为真实 smart account / safe guard

## License

MIT
