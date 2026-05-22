# Week 1｜AI × Web3 Learning Summary

This note is part of my AI × Web3 School proof-of-work.

Related daily notes:
- `daily/2026-05-19.md`: LLM and prompt basics
- `daily/2026-05-20.md`: context and agent basics
- `daily/2026-05-21.md`: Web3 wallet, network, transaction, gas, smart contract
- `daily/2026-05-22.md`: AI × Web3 bridge, agent wallet, account abstraction

Related task artifacts:
- `tasks/ai-fundamentals-concept-cards.md`
- `tasks/web3-fundamentals-concept-cards.md`

## 1. One AI concept I understand better: Agent

My current understanding:

An AI agent is not just a chatbot that writes longer answers. It is a system that can observe context, plan steps, call tools, read results, update state, and continue working toward a goal.

In normal learning tasks, this is useful because the agent can:

- read course pages
- summarize concepts
- create notes
- update a GitHub repo
- prepare proof text
- verify that links are public

But once the task touches Web3, “agent” becomes much more sensitive. Tool use means the model may move from text generation into execution. If the tools include wallet actions, contract writes, approvals, or payments, the system needs stricter boundaries than an ordinary writing assistant.

Key lesson:

A good agent workflow is not “let the model decide everything.” It should have explicit steps, state, permissions, logs, confirmation gates, and verification.

## 2. One Web3 concept I understand better: Wallet as a permission boundary

Before this week, it is easy to think of a wallet as a login tool or an address manager. Now I understand it more as the user’s permission boundary.

A wallet is where the user sees and confirms actions such as:

- connecting an address
- signing a message
- sending a transaction
- approving token spending
- switching networks
- interacting with a contract

A wallet action can have real consequences. A signature may prove identity, authorize a session, approve a typed-data message, or enable a transaction flow. A token approval can allow another contract to move assets within a limit. A transaction can change balances, contract state, or permissions.

Key lesson:

A wallet is not only a UI. It is a control point for identity, assets, permissions, and risk.

## 3. One AI × Web3 intersection: chain-aware agent workflows

The bridge between AI and Web3 is not only “AI explains blockchain.” A more important bridge is:

How can an agent safely read, reason about, prepare, execute, and verify Web3 actions?

For that, the agent needs chain-aware context:

- network / chain id
- user address
- contract address
- ABI and method
- balance and allowance
- block number and timestamp
- transaction hash and explorer link
- source of the data

Without this context, the model might mix up chains, use outdated data, explain the wrong contract, or generate a risky transaction.

A safer workflow should separate:

1. Read public/onchain facts.
2. Explain what the facts mean.
3. Draft a plan or transaction.
4. Simulate or estimate where possible.
5. Show risk and expected effect.
6. Ask for explicit confirmation.
7. Execute only through a constrained wallet/tool path.
8. Verify with transaction hash, receipt, events, or explorer link.
9. Record the trace.

Key lesson:

AI should not replace verification. In Web3, AI should help produce better verification paths.

## 4. Proof-of-work I completed this week

This week I created and submitted public learning artifacts:

- AI fundamentals concept cards: `tasks/ai-fundamentals-concept-cards.md`
- Web3 fundamentals concept cards: `tasks/web3-fundamentals-concept-cards.md`
- Daily study notes from 2026-05-18 to 2026-05-22

These artifacts helped me connect the AI side and Web3 side:

- LLM output needs verification.
- Agent tool use needs permission scope.
- Wallet signatures and transactions need human confirmation.
- Onchain facts need explorer/RPC/indexer evidence.
- Public proof-of-work should not include secrets.

## 5. My current safety checklist for an AI × Web3 agent

Before allowing an agent to help with a Web3 action, I would check:

### Context

- Which chain id / network is being used?
- Which wallet address is involved?
- Which contract address and method are involved?
- Is the ABI verified or at least source-linked?
- What block number or timestamp is the data based on?

### Permission

- Is this read-only or state-changing?
- Does it require a signature?
- Does it require token approval?
- Does it transfer native token or ERC-20 / NFT assets?
- Is there a spending limit, method limit, or time limit?

### Safety

- Is the user’s seed phrase or private key involved? If yes, stop.
- Is the request asking the agent to bypass wallet confirmation? If yes, stop.
- Is the transaction simulated or estimated?
- Are contract address, network, value, method, and recipient visible before confirmation?
- Can the permission be revoked?

### Verification

- Is there a transaction hash?
- Is there an explorer link?
- Did the transaction succeed or fail?
- Which events/logs prove the result?
- Did the agent record its inputs, outputs, and errors?

## 6. One unresolved question for Week 2

My next question is:

What is the smallest safe hands-on workflow where an AI agent can help me complete a testnet transaction without ever touching my seed phrase/private key or bypassing my wallet confirmation?

A possible path:

1. Use a fresh testnet-only wallet.
2. Get faucet funds.
3. Let the agent prepare a transaction checklist.
4. Manually confirm in wallet.
5. Save tx hash and explorer link.
6. Ask the agent to verify the receipt and summarize what happened.

This would turn the current conceptual understanding into real chain evidence.

## 7. AI assistance disclosure

I used Hermes Agent to help fetch course/task context, organize the learning structure, draft this summary, update the public repo, and prepare WCB proof text. I reviewed the content and kept the safety boundary explicit: the agent can assist with reading, writing, verification, and submission, but it must not handle seed phrases, private keys, or unconfirmed wallet execution.
