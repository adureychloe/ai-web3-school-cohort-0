# Week 2｜AI × Web3 问题地图与主方向选择

Date: 2026-05-25
WCB task: Week 2｜方向研究｜AI × Web3 问题地图与主方向选择
Handbook pages:
- https://aiweb3.school/zh/handbook/bridge/chain-aware-context/
- https://aiweb3.school/zh/handbook/bridge/web3-tool-use/
- https://aiweb3.school/zh/handbook/bridge/agent-workflow/
- https://aiweb3.school/zh/handbook/bridge/agent-wallet/
- https://aiweb3.school/zh/handbook/bridge/machine-payment/

## 1. 今天的学习目标

Week 1 我已经补了 AI / Web3 的基础词汇。今天开始进入 Week 2：不再只问“AI 是什么、钱包是什么”，而是把 AI × Web3 拆成几个真实问题方向，判断哪些问题必须同时需要 AI 和 Web3，最后选出一个本周主线。

我的时间预算仍然按每天 1 小时来做，所以今天的产出重点是：

1. 画一张问题地图，至少覆盖 5 个方向。
2. 每个方向说明 AI 的作用和 Web3 的机制。
3. 选择 2 个方向解释：为什么它不是纯 AI，也不是纯 Web3。
4. 最后选 1 个方向作为 Week 2 主线。

## 2. AI × Web3 问题地图

```mermaid
mindmap
  root((AI × Web3 问题地图))
    Payment / Commerce / Settlement
      AI: 理解任务、比价、选择服务、生成支付意图
      Web3: 稳定币、x402、预算授权、收据、结算/托管
    Identity / Reputation / Capability
      AI: 描述 agent 能力、匹配任务、总结履历
      Web3: DID/地址、签名、ERC-8004、可验证历史记录
    Wallet / Permission / Safe Execution
      AI: 生成交易计划、解释风险、自动执行低风险步骤
      Web3: ERC-4337、Safe、session key、policy、撤销权限
    Privacy / Security / Sovereignty
      AI: 检测威胁、分类敏感数据、提示确认
      Web3: 加密、ZK、权限隔离、链上/链下审计记录
    Dev Tooling / Agent Workflow
      AI: 读文档、生成合约交互脚本、维护任务状态
      Web3: RPC、ABI、区块浏览器、交易模拟、trace
    Governance / Coordination / Public Goods
      AI: 总结提案、会议转 action、贡献记录归纳
      Web3: DAO 投票、公开资金流、贡献凭证、治理流程
```

## 3. 方向拆解

### A. Payment / Commerce / Settlement

问题：如果一个 agent 要帮用户完成任务，并调用另一个付费 API / agent / 人工服务，谁报价、谁授权、谁付款、谁验收？

AI 的作用：
- 把用户目标拆成任务。
- 对不同服务报价做比较。
- 判断服务结果是否满足交付标准。
- 在预算内选择下一步调用。

Web3 的机制：
- 用 stablecoin 或链上支付完成结算。
- 用 x402 / HTTP 402 一类协议表达“先付款再访问服务”。
- 用 escrow / receipt / transaction hash 证明付款与交付。
- 用 wallet policy 限制单次金额、总预算、服务方范围和时间窗口。

### B. Identity / Reputation / Capability

问题：如果网络里有很多 agent，用户如何知道某个 agent 真的会做某类任务？另一个 agent 又如何安全地调用它？

AI 的作用：
- 生成和更新 agent profile：能做什么、输入输出是什么、限制是什么。
- 根据用户目标匹配合适 agent。
- 总结历史任务记录和失败原因。

Web3 的机制：
- 用地址、签名或 DID 作为 agent 身份锚点。
- 用 ERC-8004 这类 agent identity registry 记录身份、能力或服务端点。
- 用可验证的任务记录、付款记录、评价记录形成 reputation。

### C. Wallet / Permission / Safe Execution

问题：Agent 能不能代表用户发起链上动作？如果可以，边界在哪里？

AI 的作用：
- 理解用户意图，生成交易计划。
- 解释每一步资产变化、授权变化和风险。
- 自动执行只读查询、草稿生成、低风险白名单动作。

Web3 的机制：
- ERC-4337 / Smart Account 表达更细的账户规则。
- Safe / 多签用于高价值资产和团队 treasury。
- Session key / policy 用于小额、短时、可撤销授权。
- 区块浏览器、交易哈希、事件日志用于验证执行结果。

### D. Privacy / Security / Sovereignty

问题：Agent 需要上下文才能工作，但上下文可能包含钱包、交易习惯、财务数据、身份信息和私有策略。怎样避免 agent 因为 prompt injection、工具误用或数据泄露伤害用户？

AI 的作用：
- 识别敏感数据和异常指令。
- 为高风险动作触发人工确认。
- 对工具返回做一致性检查。

Web3 的机制：
- 用最小权限账户隔离风险。
- 用链上/链下日志保存可审计记录。
- 用 ZK / 加密 / 本地执行减少不必要的数据暴露。

### E. Dev Tooling / Agent Workflow

问题：开发者怎样让 agent 安全地读链、读合约、生成交易草稿、跑测试、解释区块浏览器结果？

AI 的作用：
- 阅读 ABI、文档、合约源码和错误日志。
- 生成调用脚本、测试用例和解释文档。
- 把“目标 → 上下文读取 → 计划 → 工具调用 → 风险检查 → 执行 → 复盘”组织成 workflow。

Web3 的机制：
- RPC / indexer / explorer 提供链上事实。
- ABI / event / tx receipt 提供结构化接口和结果。
- Simulation / fork test 降低真实执行前的风险。
- Trace 记录每次工具调用的来源、参数和结果。

### F. Governance / Coordination / Public Goods

问题：DAO 和开源社区有大量讨论、提案、会议和贡献记录，AI 可以提高效率，但不能替代治理确认。

AI 的作用：
- 总结提案和会议。
- 把讨论变成 action items。
- 帮助整理贡献记录和预算说明。

Web3 的机制：
- 投票、multisig、公开资金流和链上记录提供最终确认。
- 贡献凭证和公开 repo 让贡献可追溯。
- 治理流程限制 AI 自动执行预算或改规则。

## 4. 两个方向的“非纯 AI / 非纯 Web3”判断

### 方向 1：Wallet / Permission / Safe Execution

为什么它不是纯 AI 问题：
- 纯 AI 可以生成交易说明，但不能真正保证资产安全。
- 风险边界必须落实到账户、钱包、policy、session key、multisig 或智能账户规则里。
- 如果只靠 prompt 说“不要转太多钱”，模型可能被上下文诱导或工具返回误导。

为什么它不是纯 Web3 问题：
- 传统钱包可以签名和转账，但不会理解用户的自然语言目标。
- 用户需要 AI 把复杂操作解释成人能看懂的计划和风险摘要。
- Agent workflow 还需要模型处理文档、错误、上下文和任务拆解。

结论：这个方向的核心是“AI 负责理解和规划，Web3 负责约束和验证”。

### 方向 2：Payment / Commerce / Settlement

为什么它不是纯 AI 问题：
- AI 可以比价和选择服务，但付款、结算、收据、退款和争议需要可验证机制。
- 商业闭环不能停在“我建议你付钱”，必须能证明谁付给谁、为什么付、交付了什么。

为什么它不是纯 Web3 问题：
- 链上支付本身只解决 value transfer，不解决任务理解、服务选择和结果验收。
- Agent commerce 需要 AI 判断“这个服务是否适合当前任务”“交付是否达标”“是否继续调用”。

结论：这个方向的核心是“AI 负责服务发现和任务验收，Web3 负责授权、结算和凭证”。

## 5. Week 2 主线选择

我选择的 Week 2 主线：Wallet / Permission / Safe Execution，也就是“受限 Agent Wallet / 受限 Web3 助手”。

选择原因：
1. 它和我 Week 1 已经学过的 EOA、smart account、multisig 能自然衔接。
2. 它足够贴近真实风险：AI × Web3 最大的问题不是让 agent 会说，而是让 agent 在可控边界内行动。
3. 它可以形成一个小而清晰的 Hackathon 方向：做一个 agent workflow，帮助用户生成链上操作计划、风险摘要、确认清单和验证步骤，但不直接接触私钥。
4. 它能继续连接 Week 2 后续任务：Agent Profile、Wallet Permission、Threat Model、Proposal。

## 6. 初步 MVP 想法

暂定项目名：Safe Web3 Action Copilot

一句话：一个受限 Web3 助手，帮助用户把“我想做某个链上动作”转成可检查的执行计划、风险清单和人工确认步骤。

最小功能：
- 用户输入目标：例如“我想在测试网上调用一个合约函数”或“我想授权一个小额 token 给某个服务”。
- Agent 输出：
  - 目标链、合约地址、方法、参数、value、可能资产变化。
  - 哪些是只读步骤，可以自动查询。
  - 哪些是写入步骤，必须用户自己在钱包确认。
  - 风险提示：approve、转账、合约写入、签名消息、未知合约。
  - 验证方式：tx hash、block explorer、event、余额变化。
- 系统边界：
  - 不接触私钥、助记词、API key。
  - 不自动签名、不自动转账、不自动 approve。
  - 所有高风险动作只生成草稿和确认清单。

## 7. 今天的下一步

下一步我会围绕主线继续做两个产出：

1. Agent profile 草图：这个 Safe Web3 Action Copilot 是谁、能做什么、怎么被调用、失败怎么处理。
2. Wallet permission 策略：预算、白名单合约、可执行动作、人工确认阈值、撤销方式和日志记录。
