# Week 2｜Wallet / Permission｜Agent 链上动作权限策略

Date: 2026-05-26
WCB task: Week 2｜Wallet / Permission｜Agent 链上动作权限策略
Status: Draft for proof-of-work

## 1. Why I chose this task today

Yesterday I chose Week 2 mainline as Payment / Commerce / Settlement: how an agent can help a user purchase a service, finish delivery, verify the result, and leave auditable payment records.

Today I focused on the wallet / permission layer behind that mainline. My current understanding is:

- Payment is not only “send money”. It is also authorization, limits, evidence, refund path, and failure handling.
- An AI agent should not receive unlimited wallet control.
- The wallet layer should turn a vague human goal into bounded executable permissions.
- The safest default is: low-risk steps can be automated; high-risk actions require human confirmation.

The scenario below is a minimum agent wallet design for an AI learning / research assistant that can buy small paid APIs or AI services on behalf of the user.

## 2. Scenario

User goal:

> “Help me research an AI × Web3 topic. You may buy small paid API results if needed, but keep total cost under a fixed budget and show me proof.”

Actors:

| Actor | Role |
| --- | --- |
| User | Sets goal, budget, and final approval rules |
| Learning Agent | Searches, compares services, calls tools, prepares outputs |
| Agent Wallet / Smart Account | Executes approved payments and keeps logs |
| Paywalled API / Service | Provides data, model output, or verification result |
| Policy / Guard Layer | Checks whether an action is allowed before execution |
| Block explorer / receipt store | Provides auditable transaction and payment evidence |

Assets and risks:

- Assets: stablecoin budget, API credits, user data, research output, wallet permissions.
- Main risks: overspending, paying the wrong service, malicious prompt injection, fake tool output, approval fatigue, private data leakage, and irreversible transactions.

## 3. Agent chain-action flow

```text
[1] User sets goal and budget
    - Example: “Research Cobo Agentic Wallet and x402. Max spend: 5 USDC.”
    - Human confirmation required.

        ↓

[2] Agent creates an execution plan
    - Search sources.
    - Identify whether paid API access is needed.
    - Estimate cost.
    - No wallet action yet.
    - Can be automated.

        ↓

[3] Policy engine checks proposed wallet permissions
    - Is the service allowlisted?
    - Is the token allowed?
    - Is the amount below per-action limit?
    - Is total spend below daily / session budget?
    - Can be automated if rules are already configured.

        ↓

[4] Human reviews high-risk or first-time payment
    - Required if new service, new contract, high amount, unclear output, or unusual request.
    - User sees: recipient, amount, purpose, expected result, refund / dispute path.

        ↓

[5] Agent wallet executes payment
    - Could use smart account, Safe module, x402 client, or delegated EOA permissions.
    - Can be automated only inside the approved policy boundary.

        ↓

[6] Service returns result
    - Agent verifies response format and quality.
    - If result is invalid, agent marks it as disputed / failed.
    - Can be automated for low-risk checks; human review for subjective acceptance.

        ↓

[7] Logs and receipts are saved
    - Save tx hash / payment receipt / API response metadata / policy decision.
    - Never save secrets.
    - Can be automated.

        ↓

[8] User receives final report
    - Shows what was paid, why, what was received, and what remains uncertain.
    - Human reviews final output.
```

## 4. Automation vs human confirmation

| Step | Can be automated? | Human confirmation required? | Reason |
| --- | --- | --- | --- |
| Parse user goal | Yes | Only if ambiguous | Low-risk planning step |
| Search public sources | Yes | No | No wallet action |
| Compare services | Yes | No | Agent can rank options, but not blindly pay |
| Set budget | No | Yes | Budget is a user decision |
| First payment to a new service | No | Yes | New counterparty risk |
| Payment under existing allowlist and limit | Yes | No, if policy allows | Pre-authorized small action |
| Contract approval / allowance | Usually no | Yes | Approvals can create future loss risk |
| Transfer above threshold | No | Yes | Direct asset movement |
| Revoke permission | Yes | Optional confirmation | Usually safety-positive, but still should be logged |
| Save receipt and logs | Yes | No | Auditability improvement |
| Submit official course evidence | No | Yes | This affects external course record |

## 5. Permission strategy

### 5.1 Budget

- Session budget: max 5 USDC for one research task.
- Per-payment limit: max 1 USDC without human confirmation.
- Daily limit: max 10 USDC across all agent actions.
- Hard stop: if cumulative spending reaches the limit, the agent cannot continue payments.

### 5.2 Allowed tokens

- Prefer testnet tokens for experiments.
- For real payments, only allow a specific stablecoin such as USDC.
- Do not allow volatile token swaps in the minimum version.

### 5.3 Callable contracts / services

Allowlist only:

- Known x402-compatible paywalled endpoints.
- Known payment settlement contract or smart account module.
- Known revoke / permission management contract.

Deny by default:

- Unknown spender addresses.
- Unlimited approvals.
- Arbitrary contract calls.
- Bridges, swaps, lending, staking, and NFT minting unless separately approved.

### 5.4 Executable actions

Allowed in the minimum version:

- Read wallet balance.
- Read policy state.
- Request quote.
- Pay a small invoice under the configured limit.
- Store receipt / tx hash.
- Revoke a session permission.

Not allowed by default:

- Export private keys or seed phrases.
- Sign arbitrary messages without clear purpose.
- Grant unlimited token allowance.
- Change wallet owner.
- Upgrade wallet implementation.
- Interact with unknown contracts.

### 5.5 Human confirmation thresholds

Human confirmation is required when:

1. Recipient / contract is not allowlisted.
2. Amount is above per-payment limit.
3. Total session budget would be exceeded.
4. The action is an approval, delegation, module install, or policy change.
5. Tool output conflicts with wallet simulation.
6. Prompt or webpage asks the agent to ignore previous instructions.
7. The transaction has irreversible or unclear consequences.

### 5.6 Revocation

The user must be able to revoke:

- A single service permission.
- A session budget.
- A delegated key or session key.
- A Safe module / guard.
- All agent permissions at once.

Revocation should be visible in the UI and logged as a safety event.

### 5.7 Logs

Each payment attempt should create a structured log:

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

Logs should not include API keys, private user data, private meeting links, private keys, seed phrases, or `.env` content.

### 5.8 Failure handling

| Failure | Handling |
| --- | --- |
| Payment fails | Stop, show reason, do not retry infinitely |
| API returns bad output | Mark as failed, keep receipt, ask whether to dispute / retry |
| Agent detects prompt injection | Refuse wallet action, save incident log |
| Policy engine unavailable | Fail closed: no payment |
| User cancels | Revoke session permission and stop |
| Budget exceeded | Stop payment path and ask user for new budget |

## 6. Why ERC-4337, Safe, and guard / policy matter

### ERC-4337

ERC-4337 matters because it makes account abstraction practical without requiring every user to manage only a basic EOA flow. For agent wallets, the important idea is that the account can support richer validation logic than “whoever has the private key can do everything”.

Risks it helps with:

- Session permissions instead of full wallet control.
- Spending limits.
- Bundled user operations.
- Gas sponsorship / smoother UX.
- More programmable validation before execution.

My takeaway: ERC-4337 is useful when the wallet needs rules, not just signatures.

### Safe

Safe matters because it is a battle-tested smart account / multisig pattern for protecting valuable assets. For agent workflows, I would not want an AI agent to control a normal EOA with all funds. A Safe-style setup can separate ownership, modules, guards, and thresholds.

Risks it helps with:

- Single-key loss.
- Unauthorized treasury movement.
- Need for multi-person or multi-device confirmation.
- Adding controlled modules instead of giving away full custody.

My takeaway: Safe is useful when the wallet must protect real assets and support controlled delegation.

### Guard / policy mechanism

A guard or policy layer matters because it is the place where human intent becomes enforceable rules. The agent can propose actions, but the policy decides whether the action is allowed.

Risks it helps with:

- Prompt injection causing unauthorized payments.
- Agent hallucinating a recipient address.
- Tool output being forged or misleading.
- Overspending.
- Unlimited approvals.
- Calling contracts outside the task scope.

My takeaway: the policy layer is the “seatbelt” between natural-language autonomy and irreversible blockchain execution.

## 7. Minimum viable policy table

| Policy | Rule | Default |
| --- | --- | --- |
| Budget | Max 5 USDC per session | Required |
| Per-payment amount | Max 1 USDC without confirmation | Required |
| Token | USDC only | Required |
| Recipient | Allowlisted service only | Required |
| Contract calls | Payment / receipt / revoke only | Required |
| Approval | No unlimited approval | Required |
| New service | Human confirmation | Required |
| Logs | Save receipt and reason | Required |
| Revocation | One-click session revoke | Required |
| Failure mode | Fail closed | Required |

## 8. Connection back to Payment / Commerce mainline

This task helped me refine the Week 2 mainline. My previous focus was “how agent payment works”; today I realized the harder question is “how payment remains bounded and reviewable”.

A minimal agent commerce flow should have three layers:

1. Commerce layer: quote, order, delivery, acceptance, refund / dispute.
2. Wallet layer: budget, payment, receipt, revocation.
3. Policy layer: allowlist, limits, simulation, human confirmation, logs.

Without the wallet and policy layers, “agent payment” is just unsafe automation.

## 9. Open questions

1. What is the best UX for showing policy decisions to a non-technical user?
2. Should small x402 payments be confirmed one by one, or batched under a session budget?
3. How can the user verify that a paid API result is real and not fabricated by the agent?
4. When should refund / dispute logic be onchain, and when is an offchain receipt enough?
5. How should agent wallet logs balance transparency with privacy?

## 10. Next steps

- Connect this permission strategy with the Week 2 Payment / Commerce flow.
- Draft a minimum x402 + agent wallet architecture.
- Compare x402, MPP, ERC-8004, and Safe / ERC-4337 in the context of a small paid research agent.
- Use this note as proof-of-work for the Wallet / Permission task after review.
