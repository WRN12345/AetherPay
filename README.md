# web3

一个链上支付与订单系统：用户用钱包签名登录、下单，通过智能合约付 ETH，后端扫描链上事件确认付款，并更新订单状态。

```
React + MetaMask ──pay(orderId)──▶ Payment 合约 ──OrderPaid 事件──▶ Worker 扫描 ──▶ PostgreSQL
        │                                                                      ▲
        └──────────── 签名登录 / 下单 / 查询订单 ──▶ FastAPI ──────────────────┘
```

设计原则：合约只负责收款和发出事件，金额核对、订单状态、到期处理都在链下完成；只有扫描器能把订单写成 `PAID`。

## 技术栈

| 部分 | 技术 |
| --- | --- |
| 合约 | Solidity 0.8.24、OpenZeppelin（Ownable、ReentrancyGuard）、Foundry |
| 后端 | Python、FastAPI、SQLAlchemy、Alembic、web3.py、PostgreSQL |
| 前端 | React、TypeScript、Vite、ethers v6 |
| 登录 | EIP-4361 钱包签名登录 |

## 目录

```
contracts/   Payment 合约、测试、部署脚本
backend/     API（app/main.py）、扫描 Worker（app/worker.py）、CLI 工具（app/cli.py）
frontend/    商品页、订单页、我的订单
scripts/     export_abi.py：把合约 ABI 导出给前后端
```

## 本地运行

需要：Python 3、Node.js、Foundry、PostgreSQL（或 Docker）、MetaMask。以下命令在 Git Bash 中执行。

```bash
cp .env.example .env                  # 按需修改数据库连接
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt
docker compose up -d postgres         # 已有本机 PostgreSQL 可跳过

anvil                                  # 另开终端，本地链

# 部署合约，把输出的合约地址和部署区块写入 .env
cd contracts && forge script script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
cd .. && python scripts/export_abi.py

cd backend
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload   # API
python -m app.worker                                          # 另开终端，扫描付款

cd frontend && npm ci && npm run dev   # 打开 http://127.0.0.1:5173
```

部署时需要先 `export OWNER_PK=<部署者私钥>`。私钥只在终端里临时提供，不要写进任何文件。

## Sepolia 测试网

已部署的合约：[`0xDDdDe6F4b4Ea438cF15182BbDC0B1896dA70E793`](https://sepolia.etherscan.io/address/0xDDdDe6F4b4Ea438cF15182BbDC0B1896dA70E793)

1. 以 `.env.sepolia.example` 为模板创建 `.env.sepolia`，填入 RPC 地址和独立的数据库。
2. 后端和 Worker 启动前设置 `APP_ENV_FILE=.env.sepolia`。
3. 默认 `SCAN_BLOCK_TAG=finalized`，付款大约 15 分钟后才会确认；想更快可以改成 `safe`。

部署到测试网时，本地估算的 Gas 可能偏低，请先用 `cast estimate` 查一下，再调大 `--gas-estimate-multiplier`。

## 测试与工具

```bash
cd contracts && forge test            # 合约测试
cd backend && pytest                  # 后端测试（需要 PostgreSQL 测试库）

python -m app.cli check               # 检查数据库、节点、合约部署
python -m app.cli verify <交易哈希>    # 核验一笔交易
python -m app.cli events              # 列出 OrderPaid 事件
python -m app.cli exceptions          # 列出需人工处理的异常付款
```

完整的设计、实施阶段和测试矩阵见 [实施方案](Web3链上支付与订单系统实施方案.md)。
