# Proposal Memo — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 项目名称

**Agent Commerce Hub** — 链上服务发现 × CAW 自主支付 × 交付上链存证

## 一句话

Agent 通过链上合约（ServiceRegistry.sol, Sepolia）发现付费服务 → 创建 CAW Pact 获取有限授权 → 执行链上 Transfer → 将交付证明写回合约。

## 目标用户

- AI Agent 开发者：需要一个即开即用的「Agent 如何安全花钱」参考实现
- Cobo Agentic Wallet 用户/开发者：看到 Pact 在真实场景中的完整运作
- Hackathon 评委：评估 Agentic Commerce 从任务触发到资金操作到存证的完整度

## 真实场景

用户想让 Agent 帮忙买一份市场研究报告：

```
1. Agent 查询 ServiceRegistry 合约 → 发现 Research Notes 服务 (0.00001 SETH)
2. Agent 创建 CAW Pact → policy 限定只能付给该服务商、上限 0.00001 SETH
3. 用户手机 CAW App 批准 Pact
4. CAW 执行链上 Transfer
5. Agent 调用 recordDelivery() 将支付存证写入合约
```

## 最小功能（✅ 已全部实现）

| 功能 | 状态 |
|------|------|
| 链上服务注册与查询 | ✅ ServiceRegistry.sol (Sepolia) |
| CAW Pact 创建与提交 | ✅ 动态 policy 从合约字段生成 |
| 手机批准流程 | ✅ CAW App 通知用户 |
| 链上 Transfer | ✅ 确认交易 `0x9b8a70db...a4aedf` |
| 交付存证上链 | ✅ Block 11008291 |
| CLI 操作 | ✅ `discover / pay / proof / status` |
| Web UI | ✅ FastAPI + 暗色终端前端 |

## 验证方式

```bash
python run.py discover                    # 查看 3 个链上服务
python run.py pay 1                       # 付款全流程
python run.py proof                       # 查看链上交付证明
python run.py status                      # 钱包+合约状态
```

## 赛道

**Cobo 赛道** — Agentic Economy × Cobo Agentic Wallet

项目覆盖全部 5 个方向：
- ① Agent-Native Payments → CAW Transfer
- ② Trustless Work Agreements → ServiceRegistry.recordDelivery()
- ③ Agent Resource Procurement → 合约服务发现（procurement agent 开发中）
- ④ Autonomous Trading → 扩展预留
- ⑤ A2A Economy → 扩展预留

## 风险边界

| 风险 | 控制方式 |
|------|---------|
| Agent 超额支付 | CAW Pact Policy: deny_if.amount_usd_gt |
| Agent 付错人 | Policy: destination_address_in 锁定到合约注册的支付地址 |
| Prompt Injection 篡改目的地 | Guard 层检测（开发中）+ CAW Policy 二次校验 |
| Pact 过期后残留权限 | completion_conditions: tx_count=1 一次交易后自动结束 |
| 测试网资金不足 | 已预留 0.01 SETH + faucet 备用
