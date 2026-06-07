# Risk / Assumption Memo — Agent Commerce Hub

> 更新日期：2026-06-07

---

## 项目依赖的前提

| 假设 | 依赖 | 是否成立 |
|------|------|---------|
| CAW 钱包有足够 SETH 余额支付 | 0.01 SETH → 够 3 个服务各跑 1-2 次 | ✅ 成立 |
| 用户有手机并安装了 CAW App | 已配对且批准过 Pact | ✅ 成立 |
| Sepolia 测试网 RPC 可用 | `publicnode.com` 稳定 | ✅ 成立（fallback 已配） |
| ServiceRegistry 合约不改变 | 已部署，owner only | ✅ 成立 |
| 用户愿意在 Demo 时打开 App 批准 | 测试过 | ⚠️ 需提前准备 |

## 最可能的失败点

| 风险 | 概率 | 影响 | 缓解 |
|------|------|------|------|
| Demo 现场 CAW App 批准延迟 | 中 | 高 — 流程卡在 Step 3 | 准备截屏 + 提前批准好 Pact |
| Sepolia RPC 超时/不可用 | 低 | 高 — 合约查询和存证都依赖它 | 备选 RPC: `sepolia.drpc.org` / `tenderly.co` |
| CAW API 限流 | 低 | 中 — 轮询间隔过短 | `poll_interval=5s` 已设 |
| 钱包 SETH 耗尽 | 低 | 中 — 无法执行 Transfer | faucet 备用: `caw faucet deposit` |
| prompt injection 攻击 | 中 | 中 — 用户可能无意中触发 | Guard 层开发中，Demo 前完成 |

## Fallback Plan

| 场景 | Fallback |
|------|---------|
| CAW 批准超时 | 提前录制好批准后的流程视频，现场播放 + CLI 演示并行 |
| RPC 不可用 | 切换 RPC + 准备合约截图作为离线证据 |
| SDK 迁移来不及 | 继续使用 CLI 方案（已验证可运行） |
| Demo 当天网络问题 | 本地 CLI 不依赖外网（除 CAW/RPC），可离线演示已准备好的场景 |

## Week 4 范围控制

| 不做 / 延后 | 原因 |
|-------------|------|
| ServiceRegistry V2 | 当前合约已够 Demo，V2 6/10 后视时间 |
| 多 Agent 经济（A2A） | 需要第二个 CAW 钱包，复杂度高 |
| Autonoumous Trading (caw tx call) | 与核心叙事偏离 |
| 真实的 HTTP 402 标准实现 | 本地模拟足够证明概念 |
