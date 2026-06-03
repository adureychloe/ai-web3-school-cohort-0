# 合并方向实现计划：Secure Agent Commerce

> 日期：2026-06-03
> 将方向①（Agent 当卖家）与方向③（Payment Guard）合并为一个完整项目

---

## 项目统一叙事

```
Secure Agent Commerce
├── 方向①: Agent Service Node — Agent 托管 x402 付费 endpoint，收钱即交付
├── 方向③: Payment Guard — 在交付前检测 prompt injection 攻击，拦截异常支付
└── 合并价值: Agent 不仅能赚钱，还能安全地赚钱
```

Demo 故事线（3 幕）：
1. 正常用户付钱 → Agent 交付结果 ✅
2. 攻击者试图用 prompt injection 让 Agent 转错账 → Guard 拦截 🚫
3. Guard 生成攻击分析报告 → 链上存证 🔒

---

## 架构总览

```
┌────────────────────────────────────────────────┐
│                  run.py (CLI)                   │
│  serve | guard-demo | attack-sim | guard-report │
└──────────────────────┬─────────────────────────┘
                       │
┌──────────────────────▼─────────────────────────┐
│              agent_service_node.py              │
│  x402 endpoint (FastAPI) + verify + deliver     │
└──────┬───────────────────────────┬─────────────┘
       │                           │
       ▼                           ▼
┌──────────────┐         ┌──────────────────────┐
│  engine.py   │         │   guard_detector.py   │
│ (复用现有流程) │         │  新模块               │
│              │         │                      │
│  intent →    │         │ injection_patterns   │
│  discover →  │         │ amount_anomaly       │
│  quote →     │         │ address_mismatch     │
│  policy →    │  ───>   │ rate_anomaly         │
│  pay →       │  Guard  │ context_analysis     │
│  deliver     │  检查     │                      │
└──────┬───────┘         └──────────┬───────────┘
       │                            │
       ▼                            ▼
┌──────────────┐         ┌──────────────────────┐
│ payment_     │         │  attack_reporter.py   │
│ engine.py    │         │  新模块               │
│ (复用)       │         │                      │
│              │         │ 生成攻击分析报告       │
│ x402 收/付款  │         │ (JSON + Markdown)     │
│ 测试网/模拟   │         │ 链上存证 (可选)       │
└──────────────┘         └──────────────────────┘
```

---

## 阶段划分

### Phase 1: Guard 检测层（方向③ 核心，≈2天）

**目标**：在现有 engine 的 policy_check 之后插入一个 guard 检测层

#### Step 1.1 — 创建 `guard_detector.py`

检测维度：
| 检测项 | 触发条件 | 等级 |
|--------|---------|------|
| 金额异常 (amount_anomaly) | 报价金额 ≠ 预期定价的 ±20% | HIGH |
| 地址异常 (address_mismatch) | 收款方不在已知 allowlist 或与上次不一致 | HIGH |
| 付款频率异常 (rate_anomaly) | 同一 session 内频繁发起支付（>3次/分钟） | MEDIUM |
| 上下文注入 (context_injection) | request 中包含已知 injection signature | HIGH |
| 定价篡改 (price_tampering) | service 返回的 price 与 services.json 不符 | CRITICAL |

输出：
```python
class GuardResult:
    passed: bool
    checks: list[GuardCheck]  # 每个 check 的结果
    risk_score: float          # 0.0 ~ 1.0
    verdict: str               # "pass" | "review" | "block"
    blocking_reasons: list[str]
    report_data: dict          # 传递给 attack_reporter
```

#### Step 1.2 — 创建 `attack_reporter.py`

- 接受 GuardResult → 生成攻击分析报告
- 报告包含：攻击类型、检测到的异常、原始请求/响应、时间戳
- 输出格式：JSON（机器可读）+ Markdown（人类可读）
- 可选：链上存证（用现有 chain.py 的测试网连接，存 hash）

#### Step 1.3 — 在 `engine.py` 中插入 Guard

```
Flow:
  discovery → quote → policy_check
                    → [NEW] guard_detector.check(quote, context)
                        → 如 BLOCK: 触发 attack_reporter, 停止流程
                        → 如 REVIEW: 标记需要人工确认
                        → 如 PASS: 继续
                    → payment → delivery → proof_log
```

#### Step 1.4 — 创建 3 个 guard demo 场景

| 场景 | 描述 | Guard 预期 |
|------|------|-----------|
| `guard-normal` | 正常支付，价格匹配 | PASS |
| `guard-price-tamper` | 服务返回被篡改的价格（模拟攻击） | BLOCK (price_tampering) |
| `guard-address-swap` | 收款方被替换（模拟攻击） | BLOCK (address_mismatch) |

---

### Phase 2: Agent Service Node（方向① 核心，≈2-3天）

**目标**：Agent 变成一个可部署的 x402 付费 endpoint

#### Step 2.1 — 创建 `agent_service_node.py`

FastAPI server with:
```
POST /v1/service/{service_id}
  Headers: X-Payment-TxHash: 0x...
  Body: {"prompt": "..."}
  → Verify tx on chain
  → [Guard check] ← Phase 1 的检测层在此复用
  → Execute service logic
  → Return result + receipt
  
GET /v1/services
  → List available services with pricing
  
GET /v1/service/{service_id}/quote
  → Return quote with 402 Payment Required hint
  
GET /v1/health
  → Health check
```

#### Step 2.2 — x402 验证集成

- 收到请求时，从 `X-Payment-TxHash` header 提取 tx hash
- 用 web3.py 验证交易：收款地址匹配、金额匹配、确认数 ≥ 1
- 验证通过后执行服务逻辑
- 支持模拟模式（不接真实链，用 mock tx hash 做演示）

#### Step 2.3 — Demo 场景

| 场景 | 描述 |
|------|------|
| `serve normal` | 正常启动 server + 测试一次付费调用 |
| `serve simulate` | 模拟模式下的完整 x402 收付款循环 |
| `serve attack` | 带 prompt injection 的调用 → Guard 拦截 |

#### Step 2.4 — 整合 CLI

`run.py` 增加新命令：
```
python run.py serve                    # 启动 agent service node
python run.py guard-demo normal        # 运行 guard 正常场景
python run.py guard-demo price-tamper  # 运行 guard 价格篡改场景
python run.py guard-demo address-swap  # 运行 guard 地址替换场景
python run.py guard-report <session>   # 查看攻击报告
```

---

### Phase 3: Demo 打磨与整合（≈1-2天）

- 3 幕故事的 automated demo script
- 统一的输出格式（proof log 增加 guard 证据）
- 攻击报告的链上存证 demo
- README 更新

---

## 已有代码复用情况

| 模块 | 复用方式 | 改动 |
|------|---------|------|
| `engine.py` | 插入 guard 检测点 | 小改（+ guard hook）|
| `payment_engine.py` | 完全复用 | 不改 |
| `policy_checker.py` | 保留，guard 是独立层 | 不改 |
| `chain.py` | 复用（验证交易用） | 不改 |
| `proof_logger.py` | 扩展（增加 guard 证据字段）| 小改 |
| `mock_services.py` | 复用 + 增加攻击场景服务 | 小改 |
| `run.py` | 大幅扩展 | 新增命令 |

---

## 时间线估算（每天 1 小时）

| Phase | 天数 | 产出 |
|-------|------|------|
| Phase 1.1: guard_detector.py | 1 | 检测模块 |
| Phase 1.2: attack_reporter.py | 0.5 | 报告模块 |
| Phase 1.3: engine 集成 | 0.5 | guard 流程跑通 |
| Phase 1.4: guard demo 场景 | 1 | 3 个演示场景 |
| Phase 2.1: agent_service_node.py | 1.5 | FastAPI server |
| Phase 2.2: x402 验证 | 0.5 | 链上验证逻辑 |
| Phase 2.3-2.4: demo + CLI | 1 | 完整 CLI |
| Phase 3: 打磨 | 1 | Demo 脚本 + README |
| **总计** | **≈7 天** | |

---

## 关键设计决策

1. **Guard 独立于 policy_checker**：不混在一起，guard 是安全层，policy 是授权层，职责分开
2. **先做 Guard 再做 Service Node**：Guard 改动量小、见效快；Service Node 复用 Guard 的逻辑
3. **所有模式都支持 sim/real**：没有测试网也能完全演示
4. **攻击报告上链可选**：先用模拟，最后一天如果时间够再加

---

## 下一步

确认这个计划后，从 Phase 1.1 开始实现。
