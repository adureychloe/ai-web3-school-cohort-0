# Week 1｜AI Fundamentals Concept Cards

This note is part of my AI × Web3 School proof-of-work.

Related daily notes:
- daily/2026-05-19.md: LLM and Prompt
- daily/2026-05-20.md: Context and Agent

## 1. LLM

One-sentence explanation:
An LLM is a language model that predicts and generates text or code based on the context it receives.

Example:
I can ask an LLM to explain what a wallet is, summarize a course page, or draft a safe Web3 agent prompt.

Boundary / misconception:
An LLM is not a database or a trusted oracle. Its output can be wrong, outdated, or confidently fabricated, so important facts need verification.

## 2. Prompt

One-sentence explanation:
A prompt is the task interface that tells the model what goal to solve, what context to use, what constraints to follow, and what format to return.

Example:
Instead of saying “help me use this contract”, a safer Web3 prompt should ask the model to identify the network, wallet scope, contract address, cost, risk, and confirmation requirement.

Boundary / misconception:
Prompting is not magic wording. A good prompt is structured task design, especially when the task involves money, permissions, or irreversible actions.

## 3. Context

One-sentence explanation:
Context is the working state and information window the model can use right now, including instructions, history, documents, constraints, and tool results.

Example:
For a Web3 assistant, useful context may include the selected network, target contract, wallet address, user goal, maximum cost, and whether execution is allowed.

Boundary / misconception:
More context is not always better. Messy or conflicting context can make the model focus on the wrong thing. Good context should be relevant, organized, and prioritized.

## 4. Workflow

One-sentence explanation:
A workflow is a predefined multi-step process where the model may handle some steps, but the overall path is mostly designed in advance.

Example:
A safe transaction workflow could be: analyze transaction -> summarize risks -> wait for user confirmation -> execute through wallet -> verify on block explorer.

Boundary / misconception:
A workflow is not necessarily an autonomous agent. It can be safer and easier to debug because the steps and confirmation points are explicit.

## 5. Agent

One-sentence explanation:
An agent is an LLM-based system that can plan, use tools, observe results, update state, and continue working toward a goal.

Example:
A learning agent can read course material, create study notes, update a GitHub repo, list blockers, and prepare task proof after user confirmation.

Boundary / misconception:
An agent should not be treated as an unrestricted executor. In Web3, it must not bypass human confirmation for signatures, approvals, transfers, or contract writes.

## 6. Tool Use

One-sentence explanation:
Tool use lets an AI system call external functions or services, such as reading files, searching APIs, running tests, querying chain data, or submitting proof.

Example:
A Web3 agent might use a block explorer API to check a transaction status, but it should still ask the user before initiating any wallet-signing action.

Boundary / misconception:
Tool use expands capability and risk at the same time. Wrong parameters, wrong networks, or excessive permissions can cause real damage, so tools need clear scopes and verification.

## 7. Human-in-the-loop / Confirmation Gate

One-sentence explanation:
A confirmation gate is a required manual approval step before the system takes risky or irreversible action.

Example:
Before any onchain transaction, the agent should show the network, contract address, action, estimated cost, and risk, then wait for explicit confirmation.

Boundary / misconception:
Human-in-the-loop is not just a UX detail. In AI × Web3, it is a safety boundary between analysis and execution.

## My current understanding

The key difference between normal AI chat and an AI agent workflow is execution responsibility. A chat model mainly answers, while an agent can plan and act through tools. This makes context, workflow design, permission scope, and confirmation gates much more important.

In Web3, the safest default is: AI may analyze, explain, draft, and verify; humans must confirm signatures, approvals, transfers, and contract writes.

## AI assistance disclosure

I used Hermes Agent to help organize the structure and draft the first version of these concept cards. I reviewed and adjusted the content to match my own learning focus: AI fundamentals that matter for safe AI × Web3 workflows.
