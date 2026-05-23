# Week 1｜EOA、智能账户、多签权限差异比较

This note is part of my AI × Web3 School proof-of-work.

Task focus: compare EOA, smart account, and multisig from the perspective of control, execution, confirmation, recovery, automation, and risk.

References:
- AI Web3 School Handbook: https://aiweb3.school/zh/handbook/web3/account-abstraction/
- AI Web3 School Handbook: https://aiweb3.school/zh/handbook/bridge/agent-wallet/
- Ethereum accounts: https://ethereum.org/en/developers/docs/accounts/
- Ethereum smart contracts / multisig: https://ethereum.org/en/developers/docs/smart-contracts/

## 1. My short definitions

### EOA: Externally Owned Account

EOA is the normal wallet-account model controlled by a private key. If you control the private key or seed phrase, you control the account.

Typical examples:
- MetaMask account
- Rabby account
- a fresh testnet wallet address

My understanding:
EOA is simple and universal, but the permission model is very coarse. Most of the time it is basically “whoever has the key can sign”. This is easy to use but dangerous if the key leaks, the user signs the wrong message, or an AI tool is given too much authority.

### Smart account

A smart account is an account implemented through smart contract logic. It can define rules for validation, execution, recovery, gas payment, limits, and automation.

Typical capabilities:
- session key
- daily spending limit
- allowed contract / method list
- social recovery
- paymaster / gas sponsorship
- batch operations
- revocation rules

My understanding:
Smart account turns “account control” from one private key into programmable rules. This is more suitable for AI × Web3 because an agent can be given a limited action space instead of the user’s main private key.

### Multisig

A multisig account usually means a smart contract wallet that requires multiple approvals before a transaction can execute.

Typical examples:
- Safe multisig for DAO treasury
- 2-of-3 team wallet
- 3-of-5 protocol admin wallet

My understanding:
Multisig is mainly about shared control and reducing single-key risk. It is slower than EOA, but much safer for high-value funds, admin operations, and team decisions.

## 2. Permission comparison table

| Dimension | EOA | Smart account | Multisig |
|---|---|---|---|
| Who controls it | Whoever controls the private key / seed phrase | Rules inside the smart account plus one or more signers / keys | A group of signers according to threshold rules |
| Who can initiate actions | Usually the EOA owner directly | Owner, session key, module, automation, or allowed agent depending on rules | A proposer can draft; enough signers must approve |
| Can it initiate transactions | Yes. EOAs are the standard transaction initiator model | Yes, often through account abstraction / UserOperation-style flows | Yes, after threshold approval |
| Supports multi-person approval | No, not natively | Possible if coded or configured | Yes, this is the core feature |
| Supports recovery | Weak by default; if seed phrase is lost, recovery is usually impossible | Can support social recovery, guardians, or rule-based recovery | Can recover from one signer loss if threshold still works or owners are rotated |
| Supports spending / method limits | Not natively; depends on external dapp or wallet UI | Yes, can support limits, allowlists, expiry, session keys | Possible, but usually used for approval threshold more than fine-grained automation |
| Automation | Difficult and risky because automation would need signing authority | Better fit: limited automation can be expressed as account rules | Possible but slower; usually not ideal for frequent small automation |
| Gas payment | Usually the account needs native token | Can support paymaster / gas sponsorship depending on design | Usually needs funds / configured execution path |
| Best use case | Simple personal wallet, learning, low-value testnet actions | Agent workflows, safer UX, limited permissions, recurring or batched actions | DAO treasury, team funds, protocol admin, high-value actions |
| Main risk | Single private key is a single point of failure | Smart contract bugs or misconfigured permissions | Signer coordination failure, compromised threshold, slow execution |

## 3. How I think about “who can do what”

### EOA

EOA is clear but unforgiving:

1. The private key signs.
2. The network accepts the signature.
3. The transaction executes if valid.

This means the user must protect the seed phrase and carefully review every signature. For AI-assisted workflows, I should never give an AI agent the EOA private key or seed phrase. The agent can prepare a checklist, explain transaction fields, or verify a tx hash, but the human must confirm in the wallet.

### Smart account

Smart account can express boundaries such as:

- this session key can only call contract A
- this key expires tomorrow
- this workflow can spend at most a small testnet amount
- this action is allowed only on one chain id
- this permission can be revoked
- this operation must be logged and verified

This makes it a better fit for agent workflows. The key idea is not “AI controls my wallet”; the key idea is “the account rules define exactly what the agent can and cannot do.”

### Multisig

Multisig adds human or organizational confirmation. Instead of trusting one signer, the account requires a threshold such as 2-of-3 or 3-of-5.

This is useful when:

- funds belong to a team, DAO, or project
- a transaction changes protocol parameters
- a mistake would be expensive
- no single person should have unilateral power

For an AI assistant, multisig can also be a safety boundary: the AI may prepare a proposal, but multiple people still review and approve before execution.

## 4. Safety boundaries for AI × Web3

My current rule:

AI may assist with reading, drafting, explaining, checking, simulating, and verifying. AI should not bypass wallet confirmation or receive unlimited signing authority.

Practical boundaries:

1. Never paste seed phrase, private key, or API secrets into an agent chat.
2. Separate read tools from write tools.
3. Before any write action, show chain id, contract, method, value, recipient, and risk.
4. Prefer fresh testnet wallets for learning.
5. Prefer smart-account/session-key style limited permissions for automation.
6. Use multisig for team or high-value actions.
7. Verify results with tx hash, block explorer, receipt, events, or logs.
8. Record what the AI suggested and what the human approved.

## 5. My current conclusion

EOA, smart account, and multisig are not simply “old vs new wallet types.” They represent different permission models.

- EOA is simple but centered on one private key.
- Smart account is programmable and can express limited, expiring, revocable permissions.
- Multisig distributes authority across multiple signers.

For AI × Web3, the safest direction is not to make the agent more powerful by default. The safer direction is to make the account boundary more explicit: what can be read, what can be proposed, what can be executed, who confirms, how long permission lasts, and how the result is verified.

## 6. Open question

For Week 2, I want to explore the smallest hands-on version of this idea:

Can I create a testnet-only workflow where an AI agent prepares a transaction, a human confirms it in a wallet, and the agent verifies the receipt afterward — without the agent ever touching the private key?
