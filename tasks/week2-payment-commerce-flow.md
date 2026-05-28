# Week 2｜Payment / Commerce｜最小支付与商业流程拆解

日期：2026-05-28
WCB 任务：Week 2｜Payment / Commerce｜最小支付与商业流程拆解
状态：Proof-of-Work 草稿

## 1. 今天为什么做这个任务

前两次 Week 2 的学习里，我先做了 AI × Web3 问题地图，并把主线选到 Payment / Commerce / Settlement；随后又补了一份 Agent Wallet / Permission 策略，明确 agent 不能拥有无限钱包控制权。

今天我把这两部分合起来，拆一个最小的“agent 帮人完成任务并收款”的商业闭环。我的目标不是证明 agent 可以完全无人监管地花钱，而是理解：

- 谁下单、谁执行、谁验收、谁付款、谁仲裁。
- 报价、预算授权、交付、验收、付款、退款、争议和记录证明分别发生在哪里。
- x402、EIP-3009、ERC-8004、wallet policy 这些机制分别解决商业流程中的哪一段。

## 2. 场景设定：付费研究资料助手

场景：用户需要研究一个 AI × Web3 主题，例如“x402 + agent wallet 是否适合作为 Hackathon 项目方向”。用户希望 agent 可以搜索公开资料，也可以在预算范围内购买小额付费数据或分析结果。

最小版本里有 5 类参与方：

| 参与方 | 角色 | 需要承担的责任 |
| --- | --- | --- |
| 用户 / Buyer | 下单方、预算提供方、最终验收方 | 描述目标、设置预算、确认高风险付款、验收结果 |
| Research Agent | 执行方 | 分解任务、搜索资料、选择服务、整理交付物 |
| Paid Data / Model Service | 服务方 | 给出报价、提供 API / 推理 / 数据结果 |
| Agent Wallet / Smart Account | 付款执行层 | 根据 policy 执行小额付款，保存 receipt |
| Policy / Dispute Layer | 规则与仲裁层 | 检查预算、allowlist、质量失败、退款或争议路径 |

用户目标可以写成：

> “帮我整理 x402、ERC-8004、Cobo CAW / agent wallet 之间的关系。总预算不超过 5 USDC。任何新服务的首次付款必须让我确认。”

## 3. 最小 payment / commerce flow

```text
[1] 下单 / Intent
    用户提交研究目标、预算、交付格式和风险边界。
    例子：总预算 5 USDC；单笔自动付款上限 0.50 USDC；新服务首次付款需要人工确认。

        ↓

[2] 任务拆解 / Plan
    Agent 把目标拆成资料检索、项目对比、流程图、风险清单、结论草稿。
    这一步不涉及付款，可以自动化。

        ↓

[3] 服务发现 / Discovery
    Agent 查找可用服务：公开网页、文档、付费 API、其他 agent endpoint。
    如果使用 ERC-8004，可以从 identity registry 找到服务型 agent，并查看它声明的 endpoint 与 reputation。

        ↓

[4] 报价 / Quote
    服务返回价格、交付内容、网络、token、过期时间和退款条件。
    如果使用 x402，服务可以先返回 HTTP 402 Payment Required，说明 payment requirements。

        ↓

[5] 预算与权限检查 / Policy Check
    Wallet policy 检查：
    - 服务是否在 allowlist 或可信列表内？
    - 金额是否低于单笔限额？
    - 累计金额是否低于 session budget？
    - token / network 是否允许？
    - 是否涉及 approval、delegation、module install 等高风险动作？

        ↓

[6] 人工确认 / Human Review
    如果是新服务、超过阈值、合约不明、报价异常或 policy 变化，则用户必须确认。
    如果是已 allowlist 的低额固定价格服务，可以自动执行。

        ↓

[7] 执行与交付 / Execute + Deliver
    Agent 调用服务，完成付款或签署支付授权。
    服务返回数据、模型输出或研究结果。

        ↓

[8] 验收 / Acceptance
    Agent 先做格式检查、来源检查、重复性检查。
    用户对主观质量和最终结论做人工验收。

        ↓

[9] 付款 / Refund / Dispute
    如果服务有效，付款完成并记录 receipt。
    如果服务失败，进入退款、重试或争议路径。

        ↓

[10] 记录证明 / Proof
    保存：报价、payment receipt / tx hash、policy decision、交付摘要、人工确认记录、失败原因。
```

## 4. 报价、预算授权、执行、交付、验收、付款、退款、记录证明

| 阶段 | 最小实现 | 自动化边界 | 证明材料 |
| --- | --- | --- | --- |
| 报价 | 服务返回固定价格和交付说明 | Agent 可以比较报价，但不能自动接受高风险报价 | quote id、价格、有效期、服务 endpoint |
| 预算授权 | 用户设置 session budget 和单笔限额 | 预算必须由用户确认 | policy config、确认记录 |
| 执行 | Agent 调用 API / agent endpoint | 搜索和低风险调用可自动化；付款前要过 policy | request id、工具日志 |
| 交付 | 服务返回数据或结果 | Agent 可做格式校验 | response metadata、结果摘要 |
| 验收 | Agent 初筛 + 用户最终复核 | 主观质量不应完全自动判定 | acceptance note、人工确认 |
| 付款 | x402 / wallet 完成小额付款 | allowlist + 低于限额才自动付款 | tx hash、payment response、receipt |
| 退款 / 争议 | 服务失败时请求退款或标记 dispute | 金额小可自动标记；升级争议需人工 | failure reason、dispute id |
| 记录证明 | 保存完整流程，不含敏感信息 | 可自动化 | markdown note、JSON log、链上记录 |

## 5. x402、EIP-3009、ERC-8004、wallet policy 分别解决哪一段

### 5.1 x402：把“付款要求”放回 HTTP 工作流

x402 适合解决“付费 API / 付费 agent endpoint 怎么收小额款”的问题。它使用 HTTP 402 Payment Required：

1. Client 请求资源。
2. Server 返回 402，并说明价格、网络、token、收款方等 payment requirements。
3. Client 在授权范围内签署支付。
4. Client 带支付证明重试请求。
5. Server 验证并结算后返回结果。

在这个商业流程里，x402 主要覆盖：报价、付款要求、付款验证、交付前置条件。

它不自动解决的问题：

- 用户是否真的想买这个服务。
- 服务质量是否达标。
- agent 是否被 prompt injection 诱导付款。
- 超预算、退款、争议和长期信誉。

### 5.2 EIP-3009：让 x402 的付款更像“签一次授权”

EIP-3009 的重点是 transferWithAuthorization，也就是用签名授权 token 转移。对 agent commerce 来说，它的价值是：

- 用户或 agent wallet 可以签署一个有金额、期限、nonce 的支付授权。
- 服务端或 facilitator 可以用这个授权完成结算。
- 付款不一定要求用户每次自己发起一笔 gas 交易。

在这个流程里，EIP-3009 主要解决：付款执行和结算效率。

但它不是权限策略本身。即使有 EIP-3009，也需要 wallet policy 限制金额、token、收款方、有效期和可调用服务。

### 5.3 ERC-8004：让 agent / 服务有可发现的身份和信誉

ERC-8004 可以用于 agent identity 和 reputation。它适合解决：

- 这个服务型 agent 是谁？
- 它的 endpoint 是什么？
- 是否有历史评价或验证记录？
- 其他用户或 agent 是否给过它质量、可用性、响应等反馈？

在这个商业流程里，ERC-8004 主要覆盖：服务发现、身份验证、信誉筛选、交付后的反馈。

它不替代用户判断，也不保证服务永远可信。它更像“可验证身份 + 可累计信誉”的基础层。

### 5.4 Wallet policy / guard：商业自动化的安全边界

Wallet policy 是防止 agent commerce 失控的关键。它负责回答：

- 这个 token 能不能付？
- 这个地址能不能收款？
- 单笔金额是否超限？
- 本次任务累计金额是否超预算？
- 是否在安装 module、修改 owner、设置 approval？
- 是否需要人工确认？

如果没有 policy，agent payment 只是危险的自动化；有了 policy，它才有机会变成可审计、可撤销、可限制的商业流程。

## 6. 最小 JSON 记录格式

我希望每次商业动作都能留下结构化记录，方便提交 proof，也方便未来做 audit：

```json
{
  "task_id": "research-x402-agent-wallet-2026-05-28",
  "buyer_goal": "research x402 and agent wallet for AI x Web3 project",
  "session_budget": "5 USDC",
  "single_auto_pay_limit": "0.50 USDC",
  "service": {
    "name": "example paid research endpoint",
    "endpoint": "https://example.com/api/research",
    "identity": "erc8004:optional-agent-id",
    "reputation_checked": true
  },
  "quote": {
    "amount": "0.25 USDC",
    "network": "eip155:8453",
    "token": "USDC",
    "expires_at": "2026-05-28T23:59:00Z"
  },
  "policy_decision": {
    "allowed": true,
    "reason": "allowlisted service, fixed price, below single payment limit",
    "human_confirmation_required": false
  },
  "payment": {
    "protocol": "x402",
    "authorization": "EIP-3009 signed authorization or equivalent",
    "tx_hash_or_receipt": "placeholder"
  },
  "delivery": {
    "status": "accepted",
    "summary": "service returned source list and comparison notes"
  },
  "sensitive_data_saved": false
}
```

## 7. 失败和争议处理

| 失败情况 | 最小处理方式 | 是否需要人工介入 |
| --- | --- | --- |
| 服务返回 402 但价格超过预算 | 拒绝付款，提示用户 | 需要用户修改预算才继续 |
| 服务未在 allowlist | 暂停，展示服务信息 | 需要人工确认 |
| 付款后没有返回结果 | 保存 receipt，标记 failed，尝试一次查询 | 金额较大时人工介入 |
| 返回内容低质或与报价不符 | 标记 disputed，保留证据 | 需要人工验收 |
| 工具输出要求忽略付款规则 | 判定 prompt injection，拒绝钱包动作 | 需要人工复核 incident |
| facilitator / 链上结算失败 | fail closed，不重试无限循环 | 需要检查网络或服务状态 |
| 用户取消任务 | 撤销 session permission，停止付款 | 用户已介入 |

## 8. 我的当前结论

1. Agent commerce 的最小闭环不是“agent 自动付款”，而是“intent → quote → policy → payment → delivery → acceptance → proof”。
2. x402 很适合做付费 API / agent endpoint 的小额支付入口，但它只解决付款协议，不解决信任、权限和验收的全部问题。
3. EIP-3009 让付款授权更顺滑，但必须被预算、deadline、nonce、收款方和 token 限制包住。
4. ERC-8004 更适合做服务发现和 reputation 层，帮助 agent 在付款前判断对方是谁、有没有历史记录。
5. Wallet policy / guard 是最重要的安全层：它把“自然语言目标”限制成“明确可执行、可撤销、可审计的动作”。
6. 对我的 Week 2 主线来说，最有价值的项目方向可能不是做一个全自动消费 agent，而是做一个“带预算、权限和 proof log 的 agent commerce sandbox”。

## 9. 下一步

下一步可以把这个 flow 收敛成 Week 2 总交付的一部分：

- 主方向：Payment / Commerce / Settlement。
- 典型场景：agent 帮用户购买小额信息服务或模型能力。
- 核心机制：x402 + wallet policy + receipt log。
- 人工确认点：预算、新服务、超额付款、approval / delegation、最终验收。
- 最小验证计划：先不真实付款，做一个模拟 402 → policy check → receipt log 的 CLI 或网页 demo。
