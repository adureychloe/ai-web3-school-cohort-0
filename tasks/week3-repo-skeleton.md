# Repo Skeleton — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 仓库结构

```
agent-commerce-sandbox/
├── contracts/                          # Solidity 合约
│   ├── ServiceRegistry.sol             # 链上服务注册合约
│   ├── ServiceRegistry.abi.json        # 编译 ABI
│   ├── ServiceRegistry.bin             # 编译 Bytecode
│   └── deployed.json                   # 部署信息（地址、tx hash）
├── agent_commerce_sandbox/             # Python 核心模块
│   ├── __init__.py
│   ├── caw_client.py                   # CAW CLI 封装（Pact/Transfer/轮询）
│   ├── chain_client.py                 # web3.py 合约交互（服务发现/存证）
│   ├── engine.py                       # 核心编排（5 步流程）
│   └── ...                             # 旧模块（逐步清理中）
├── web/                                # Web UI
│   ├── app.py                          # FastAPI 后端
│   ├── index.html                      # 暗色终端风格前端
│   └── run_web.sh                      # 启动脚本
├── run.py                              # CLI 入口
├── run.sh                              # CLI 启动脚本
├── .env                                # 部署私钥（gitignored）
├── AGENT_COMMERCE_HUB_PLAN.md          # 完整扩展计划
├── README.md                           # 项目说明
└── requirements.txt                    # Python 依赖
```

## 链上证据

| 项目 | 值 |
|------|-----|
| 合约 | ServiceRegistry.sol → Sepolia |
| 合约地址 | `0x8F7a124681327B485656Ea6be15Fa1338FA7d8E3` |
| 部署交易 | `0xf3d3c11403a733f6a57213cf5caeb05e58191a8063c4cb80a28f20e4085a9cca` |
| 注册服务 | 3 个 (Research Notes / Data Fetcher / Premium Analyzer) |
| 支付 TX | `0x9b8a70db067d15102af20b90f376f3e7d4bc696e1be169f83935c07123a4aedf` |
| CAW 钱包 | Agent: Hermes / Wallet: 511ef1fb-90b0-4740-a80f-ce7db6f9c6f9 |

## 端到端流程

```
run.py discover → ServiceRegistry.listServices()
  → 用户选择服务 → run.py pay <id>
    → engine.pay_for_service()
      → [1/5] 查询合约获取服务详情
      → [2/5] 提交 CAW Pact（动态 policy）
      → [3/5] 等待手机批准
      → [4/5] 执行 CAW Transfer
      → [5/5] recordDelivery() 写入链上证
```

## GitHub

https://github.com/adureychloe/ai-web3-school-cohort-0/tree/master/agent-commerce-sandbox
