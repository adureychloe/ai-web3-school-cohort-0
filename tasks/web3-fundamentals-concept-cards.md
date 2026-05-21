# Web3 Fundamentals Concept Cards

Date: 2026-05-21

Handbook references:
- Wallet: https://aiweb3.school/zh/handbook/web3/wallet/
- Network: https://aiweb3.school/zh/handbook/web3/network/
- Smart Contract: https://aiweb3.school/zh/handbook/web3/smart-contract/

AI assistance disclosure: Hermes Agent helped draft and organize these cards. I reviewed the structure and kept the safety boundaries explicit, especially around seed phrases, private keys, signatures, approvals, and transactions.

## 1. Account

One-sentence explanation:
An account is an identity and control unit on a blockchain that can hold assets, sign messages, and interact with smart contracts.

Example:
An Ethereum EOA account can hold ETH, sign a login message, and send a transaction to a contract.

Safety reminder / common misconception:
An account is not the same as an email login. If the private key or recovery method is lost, there may be no customer support path to recover it.

## 2. Address

One-sentence explanation:
An address is the public identifier used to receive assets and interact with other accounts or contracts.

Example:
When someone sends testnet ETH to my wallet, they send it to my public address, not to my seed phrase or private key.

Safety reminder / common misconception:
An address is usually safe to share, but address sharing still affects privacy because others may inspect related onchain activity in a block explorer.

## 3. Wallet

One-sentence explanation:
A wallet is the user-side tool for managing accounts, connecting to dApps, signing messages, sending transactions, switching networks, and reviewing risks.

Example:
A browser wallet may ask me to connect to a dApp, sign a message for login, or confirm a transaction that calls a smart contract.

Safety reminder / common misconception:
Connecting a wallet is not the same as approving every future action. Each signature, token approval, or transaction should still be reviewed separately.

## 4. Seed Phrase

One-sentence explanation:
A seed phrase is a high-risk recovery secret that can regenerate wallet keys and therefore control the assets tied to those keys.

Example:
If I lose my phone but still have my seed phrase, I may be able to recover the wallet in a wallet app.

Safety reminder / common misconception:
No website, AI agent, form, support person, or dApp should ask me to type my seed phrase. If someone asks for it, I should assume it is dangerous.

## 5. Private Key

One-sentence explanation:
A private key is the secret cryptographic material that proves control over an account and enables signatures or transactions.

Example:
A wallet uses the private key locally to sign a transaction, but the private key itself should not be sent to the dApp.

Safety reminder / common misconception:
A private key is not an API key that can be casually pasted into tools. Exposing it can allow an attacker to drain assets or impersonate the account.

## 6. Signature

One-sentence explanation:
A signature is cryptographic proof that the account owner approved a message or transaction with their key.

Example:
A dApp may ask me to sign a human-readable message to prove that I control an address for login.

Safety reminder / common misconception:
Not all signatures are harmless. I should understand what I am signing, especially if the message is unreadable, requests permissions, creates an order, or authorizes later actions.

## 7. Transaction

One-sentence explanation:
A transaction is a formal request to change blockchain state, such as transferring assets, approving tokens, or calling a smart contract.

Example:
Calling a contract’s `increment()` function may create a transaction that changes a public `count` value onchain.

Safety reminder / common misconception:
Clicking a website button is only the start. The transaction still needs wallet confirmation, signing, broadcasting, block inclusion, execution, and confirmation; it may fail or stay pending.

## 8. Gas

One-sentence explanation:
Gas is the cost paid for blockchain execution and storage resources.

Example:
Sending ETH or calling a contract on an EVM network requires paying gas in the network’s fee token, such as ETH on Ethereum or a testnet version on a testnet.

Safety reminder / common misconception:
A failed transaction may still consume gas because network resources were used. I should check fee estimates and make sure I am on the correct network.

## 9. Smart Contract

One-sentence explanation:
A smart contract is a public program deployed onchain that stores state and defines rules for interacting with that state.

Example:
A counter contract can store a `count` variable and expose an `increment()` function that users call through transactions.

Safety reminder / common misconception:
A smart contract is not automatically safe just because it is onchain. Bugs, bad permissions, upgrade risks, and unsafe external calls can affect real assets.

## 10. Testnet

One-sentence explanation:
A testnet is a blockchain network used to test wallets, contracts, scripts, and transaction flows without using mainnet assets.

Example:
Before deploying a contract to mainnet, I can deploy it to a testnet and verify the contract address and transaction hash in a testnet explorer.

Safety reminder / common misconception:
Testnet assets usually have no real economic value, but testnet success does not prove mainnet safety. Mainnet has different liquidity, MEV, attack incentives, and user behavior.

## 11. Block Explorer

One-sentence explanation:
A block explorer is a tool for inspecting onchain facts such as addresses, transactions, contract code, events, token transfers, and execution status.

Example:
After sending a testnet transaction, I can paste the tx hash into a block explorer to check whether it succeeded or failed.

Safety reminder / common misconception:
An explorer helps verify chain data, but it is not the chain itself. I should use the correct explorer for the correct network and avoid trusting random links blindly.

## AI × Web3 safety takeaway

For an AI-assisted Web3 workflow, the agent can help prepare and explain, but high-risk actions must stay under user control.

A safe flow should be:

1. Read public context: docs, ABI, explorer data, local notes.
2. Explain the intended action in plain language.
3. Show network, account address, contract address, method, assets, gas estimate, and possible side effects.
4. Ask the user to review in their wallet.
5. Wait for explicit confirmation before any write action.
6. Record public proof such as tx hash or explorer link after the user completes the action.

The agent must not ask for seed phrases or private keys, and it must not secretly sign messages, approve tokens, transfer assets, deploy contracts, or call write methods.
