# Week 2｜Wallet / Permission｜Agent 链上动作权限策略

日期：2026-05-26
WCB 任务：Week 2｜Wallet / Permission｜Agent 链上动作权限策略
状态：Proof-of-Work 草稿

## 1. 今天为什么做这个任务

昨天我选择的 Week 2 主线是 Payment / Commerce / Settlement，也就是：Agent 如何帮助用户购买服务、完成交付、验收结果，并留下可审计的付款记录。

今天我把问题推进到更底层的钱包和权限问题。我的当前理解是：

- Payment 不只是“把钱转出去”，还包括授权、限额、证明、退款路径和失败处理。
- AI agent 不应该拿到无限制的钱包控制权。
- 钱包层应该把用户的自然语言目标，转换成有边界、可执行、可撤销的权限。
- 最安全的默认策略是：低风险步骤可以自动化，高风险动作必须由人确认。

下面的设计，是一个最小化 agent wallet 场景：一个 AI 学习 / 研究助手，可以在用户授权范围内，为用户购买小额付费 API 或 AI 服务。

## 2. 场景设定

用户目标：

> “帮我研究一个 AI × Web3 主题。如果需要，可以购买小额付费 API 结果，但总花费必须在固定预算内，并向我展示证明。”

参与方：

| 参与方 | 角色 |
| --- | --- |
| 用户 | 设置目标、预算和最终审批规则 |
| Learning Agent | 搜索、比较服务、调用工具、整理输出 |
| Agent Wallet / Smart Account | 执行被授权的付款，并保留日志 |
| 付费 API / 服务方 | 提供数据、模型输出或验证结果 |
| Policy / Guard 层 | 在执行前检查动作是否被允许 |
| 区块浏览器 / receipt 存储 | 提供可审计的交易和付款证明 |

涉及的资产和风险：

- 资产：稳定币预算、API credits、用户数据、研究结果、钱包权限。
- 主要风险：超预算、付给错误服务、prompt injection、伪造工具返回、确认疲劳、隐私数据泄露、不可逆交易。

## 3. Agent 发起链上动作的执行流程

```text
[1] 用户设置目标和预算
    - 例子：“研究 Cobo Agentic Wallet 和 x402，最高花费 5 USDC。”
    - 必须人工确认。

        ↓

[2] Agent 制定执行计划
    - 搜索资料。
    - 判断是否需要付费 API。
    - 预估成本。
    - 这一步还不涉及钱包动作。
    - 可以自动化。

        ↓

[3] Policy engine 检查拟议的钱包权限
    - 服务是否在 allowlist 内？
    - token 是否被允许？
    - 金额是否低于单次限额？
    - 总花费是否低于每日 / 本次任务预算？
    - 如果规则已经配置好，可以自动化。

        ↓

[4] 用户复核高风险或首次付款
    - 如果是新服务、新合约、高金额、结果不明确或异常请求，则必须人工确认。
    - 用户需要看到：收款方、金额、用途、预期结果、退款 / 争议路径。

        ↓

[5] Agent wallet 执行付款
    - 可以使用 smart account、Safe module、x402 client 或被委托的 EOA 权限。
    - 只有在已批准的 policy 边界内，才可以自动执行。

        ↓

[6] 服务返回结果
    - Agent 检查响应格式和质量。
    - 如果结果无效，标记为 disputed / failed。
    - 低风险格式检查可以自动化；主观验收需要人工复核。

        ↓

[7] 保存日志和 receipt
    - 保存 tx hash / payment receipt / API response metadata / policy decision。
    - 不保存任何敏感信息。
    - 可以自动化。

        ↓

[8] 用户收到最终报告
    - 报告中说明：付了什么、为什么付、得到了什么、还有什么不确定。
    - 用户复核最终输出。
```

## 4. 哪些步骤可以自动化，哪些必须人工确认

| 步骤 | 可以自动化吗？ | 是否需要人工确认？ | 原因 |
| --- | --- | --- | --- |
| 解析用户目标 | 可以 | 目标模糊时需要 | 这是低风险规划步骤 |
| 搜索公开资料 | 可以 | 不需要 | 不涉及钱包动作 |
| 比较服务 | 可以 | 不需要 | Agent 可以排序，但不能盲目付款 |
| 设置预算 | 不可以 | 需要 | 预算是用户决策 |
| 首次向新服务付款 | 不可以 | 需要 | 有新 counterparty 风险 |
| 已 allowlist 且低于限额的小额付款 | 可以 | 如果 policy 已允许，则不需要 | 属于预授权小额动作 |
| 合约 approval / allowance | 通常不可以 | 需要 | 授权可能造成未来资产损失 |
| 超过阈值的 transfer | 不可以 | 需要 | 直接移动资产 |
| 撤销权限 | 可以 | 可选确认 | 通常是安全正向动作，但仍要记录 |
| 保存 receipt 和日志 | 可以 | 不需要 | 增强可审计性 |
| 提交官方课程证明 | 不可以 | 需要 | 会影响外部课程记录 |

## 5. 权限策略设计

### 5.1 预算

- 单次 session 预算：一个研究任务最多 5 USDC。
- 单笔付款限额：不经人工确认时，最多 1 USDC。
- 每日限额：所有 agent 动作合计最多 10 USDC。
- 硬停止规则：累计支出达到限额后，agent 不能继续付款。

### 5.2 允许使用的 token

- 实验优先使用 testnet token。
- 如果是真实付款，只允许指定稳定币，例如 USDC。
- 最小版本不允许 volatile token swap。

### 5.3 可调用合约 / 服务

只允许 allowlist 中的对象：

- 已知的 x402-compatible paywalled endpoints。
- 已知 payment settlement contract 或 smart account module。
- 已知 revoke / permission management contract。

默认拒绝：

- 未知 spender address。
- 无限授权。
- 任意合约调用。
- bridge、swap、lending、staking、NFT minting，除非单独确认。

### 5.4 可执行动作

最小版本允许：

- 读取钱包余额。
- 读取 policy 状态。
- 请求报价。
- 在配置限额内支付小额 invoice。
- 保存 receipt / tx hash。
- 撤销 session permission。

默认不允许：

- 导出私钥或助记词。
- 在没有清晰目的时签署任意消息。
- 授予无限 token allowance。
- 修改钱包 owner。
- 升级钱包实现。
- 和未知合约交互。

### 5.5 人工确认阈值

以下情况必须人工确认：

1. 收款方 / 合约不在 allowlist 内。
2. 金额超过单笔付款限额。
3. 执行后会超过本次 session 总预算。
4. 动作属于 approval、delegation、module install 或 policy change。
5. 工具返回结果和 wallet simulation 结果冲突。
6. prompt 或网页要求 agent 忽略之前的规则。
7. 交易后果不可逆，或后果不清晰。

### 5.6 撤销方式

用户必须可以撤销：

- 单个服务权限。
- 本次 session 预算。
- delegated key 或 session key。
- Safe module / guard。
- 所有 agent 权限。

撤销动作应该在 UI 中清晰可见，并作为安全事件记录到日志中。

### 5.7 日志记录

每次付款尝试都应该生成结构化日志：

```json
{
  "timestamp": "2026-05-26T00:00:00Z",
  "user_goal": "research AI x Web3 topic",
  "agent_action": "pay paid API invoice",
  "service": "example allowlisted x402 endpoint",
  "token": "USDC",
  "amount": "0.50",
  "policy_result": "allowed",
  "human_confirmation": false,
  "tx_hash_or_receipt": "placeholder",
  "result_summary": "API returned source list",
  "failure_reason": null
}
```

日志不应该包含 API key、用户隐私数据、私人会议链接、私钥、助记词或 `.env` 内容。

### 5.8 失败处理

| 失败情况 | 处理方式 |
| --- | --- |
| 付款失败 | 停止，展示原因，不无限重试 |
| API 返回结果质量差 | 标记为 failed，保留 receipt，询问是否 dispute / retry |
| Agent 检测到 prompt injection | 拒绝钱包动作，并保存 incident log |
| Policy engine 不可用 | Fail closed：不付款 |
| 用户取消 | 撤销 session permission 并停止 |
| 预算超限 | 停止付款路径，并询问用户是否设置新预算 |

## 6. ERC-4337、Safe、guard / policy 为什么重要

### 6.1 ERC-4337

ERC-4337 的价值在于，它让 account abstraction 更容易落地。对于 agent wallet 来说，重要的不是“钱包更酷”，而是账户可以支持比普通 EOA 更丰富的验证逻辑，不再只是“谁有私钥谁就能做所有事”。

它帮助解决的风险：

- 用 session permission 替代完整钱包控制权。
- 设置 spending limit。
- 支持 bundled user operations。
- 支持 gas sponsorship / 更顺滑的 UX。
- 在执行前加入更可编程的验证逻辑。

我的理解：当钱包需要规则，而不只是签名时，ERC-4337 就变得重要。

### 6.2 Safe

Safe 的价值在于，它是相对成熟、经过大量使用的 smart account / multisig 模式，适合保护高价值资产。对于 agent workflow，我不希望 AI agent 直接控制一个装有所有资金的普通 EOA。Safe-style setup 可以把 owner、module、guard、threshold 分开。

它帮助解决的风险：

- 单一私钥丢失。
- treasury 被未授权移动。
- 需要多人或多设备确认。
- 通过受控 module 委托部分能力，而不是交出完整 custody。

我的理解：当钱包保护真实资产，并且需要受控 delegation 时，Safe 很重要。

### 6.3 Guard / policy 机制

Guard 或 policy 层的价值在于，它是把人的意图变成可执行规则的地方。Agent 可以提出动作，但 policy 决定这个动作是否被允许。

它帮助解决的风险：

- prompt injection 导致未授权付款。
- agent 幻觉出错误收款地址。
- 工具返回被伪造或误导。
- 超预算。
- 无限授权。
- 调用任务范围外的合约。

我的理解：policy 层是自然语言自治和不可逆链上执行之间的“安全带”。

## 7. 最小可行 policy 表

| Policy | 规则 | 默认要求 |
| --- | --- | --- |
| Budget | 每个 session 最多 5 USDC | 必须配置 |
| 单笔付款 | 不确认时最多 1 USDC | 必须配置 |
| Token | 只允许 USDC | 必须配置 |
| 收款方 | 只允许 allowlisted service | 必须配置 |
| 合约调用 | 只允许 payment / receipt / revoke | 必须配置 |
| Approval | 禁止无限授权 | 必须配置 |
| 新服务 | 必须人工确认 | 必须配置 |
| 日志 | 保存 receipt 和原因 | 必须配置 |
| 撤销 | 一键撤销 session 权限 | 必须配置 |
| 失败模式 | Fail closed | 必须配置 |

## 8. 和 Payment / Commerce 主线的关系

这个任务让我重新理解 Week 2 的主线。之前我关注的是“agent payment 怎么发生”；今天我意识到更难的问题是“agent payment 如何保持有边界、可复核、可撤销”。

一个最小 agent commerce flow 至少需要三层：

1. Commerce layer：quote、order、delivery、acceptance、refund / dispute。
2. Wallet layer：budget、payment、receipt、revocation。
3. Policy layer：allowlist、limits、simulation、human confirmation、logs。

如果没有 wallet 和 policy 层，“agent 自动付款”只是危险的自动化；只有边界清晰，它才可能成为可验证、可审计的 Web3 workflow。

## 9. 仍然没解决的问题

1. 怎样用最简单的 UX 向非技术用户展示 policy decision？
2. 小额 x402 payment 应该每次确认，还是在 session budget 下批量授权？
3. 用户如何验证 paid API result 真实存在，而不是 agent 编造的？
4. 哪些 refund / dispute logic 值得上链，哪些 offchain receipt 就足够？
5. Agent wallet logs 如何在透明度和隐私之间平衡？

## 10. 下一步

- 把这份 permission strategy 和 Week 2 Payment / Commerce flow 连接起来。
- 草拟一个最小 x402 + agent wallet 架构。
- 比较 x402、MPP、ERC-8004 和 Safe / ERC-4337 在小额 paid research agent 场景中的分工。
- 复核后，把这篇笔记作为 Wallet / Permission 任务的 proof-of-work。
