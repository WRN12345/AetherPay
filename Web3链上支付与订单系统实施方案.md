# web3 链上支付与订单系统实施方案

**第十七课 从最小支付到完整订单系统**

技术栈：Python FastAPI PostgreSQL React TypeScript Solidity Foundry Anvil  
编制日期：2026 年 10 月 24 日

项目基于一个前后端分离模板改造：保留了 FastAPI 分层结构、pydantic-settings 配置、Vite 代理、nginx 与 Docker 部署文件，删除了模板原有的聊天与智能体代码，前端替换为 React + TypeScript。第 9 节给出改造后的目录与当前完成情况。

本项目围绕一个具体业务展开：用户购买课程资料，在 React 网页连接钱包，使用测试 ETH 支付；智能合约记录付款并发出事件，Python 后端从链上读取事件、独立核验，并将 PostgreSQL 中的订单更新为已支付。

本方案面向有后端或前端开发经验、但没有做过区块链开发的读者。建议先阅读 1.3 节的概念速查，再按阶段顺序实施。阶段 0 至阶段 4 得到可以演示的最小完整项目；阶段 5 和阶段 6 加入常驻处理、故障恢复和一致性测试；阶段 7 和阶段 8 用于第十八课的进阶对比、测试网与工程化扩展。每个阶段都给出操作顺序、交付物和验收标准，不必一次性引入全部复杂度。

## 1 项目目标与边界

第一版采用单商户、单链、固定商品价格、原生测试 ETH。示例商品为课程资料，价格为 0.01 ETH，即 10000000000000000 Wei。价格由后端商品配置决定，前端只提交商品编号。

完成后应能演示以下结果：

1. 用户连接钱包，检查所在网络，创建订单。
2. 用户调用支付合约，附带订单编号和 ETH。
3. 合约发出 OrderPaid 事件，记录订单编号、付款人和金额。
4. 后台扫描器读取已确认区块中的事件，与数据库订单比对金额和到期时间。
5. 订单在数据库中完成一次有效状态更新；用户关闭网页也不会遗漏付款。

基础阶段暂不实现自动退款、ERC20、多商户、跨链、法币计价、库存扣减和自动发货。金额不符、逾期和重复付款记录为异常付款，供人工处理。公共部署前加入钱包身份认证和订单访问控制。

### 1.1 技术选型

| 层级 | 技术 | 主要作用 |
| --- | --- | --- |
| 业务后端 | Python 与 FastAPI | 订单接口、输入校验和状态查询 |
| 数据库 | PostgreSQL | 保存订单、链上付款记录与扫描进度 |
| 数据访问 | SQLAlchemy 与 psycopg | ORM、数据库事务和连接池 |
| 数据迁移 | Alembic | 管理表结构的创建和升级 |
| 链上读取 | web3.py v7 | 查询区块、收据和事件日志 |
| 前端 | React、TypeScript 与 Vite | 商品页、钱包连接、支付与结果展示 |
| 钱包交互 | ethers.js v6 | 读取网络、获取签名者、调用支付合约 |
| 智能合约 | Solidity 与 OpenZeppelin | 收款、发出事件、权限与防重入 |
| 开发工具 | Foundry 与 Anvil | 编译、部署、测试、命令行交互和本地链 |
| 后台处理 | 独立 Python Worker | 扫描事件、核验付款、处理到期 |
| 测试 | Forge 与 pytest | 合约测试、接口测试和集成验证 |
| 本地服务 | 本机 PostgreSQL 或 Docker Compose | 提供开发数据库；Docker Compose 另用于阶段 8 部署 |

Python 用于全部业务后端及后台处理。第一版选择同步 SQLAlchemy 和同步 web3.py，减少学习负担；同步 FastAPI 接口使用普通 def，持续查链放到独立进程。模板原有接口写成 async def，新增的业务接口一律使用普通 def，否则同步的数据库和 RPC 调用会阻塞整个服务。后续若改为异步，应成套调整数据库驱动和 RPC 调用，避免在 async def 内直接执行阻塞操作。[1][2][3]

合约的权限和防重入直接使用 OpenZeppelin 的 Ownable 与 ReentrancyGuard，不自己手写。[8]

前端也可以选用 wagmi 与 viem，它们内置了账户切换、网络切换等状态处理；本方案使用 ethers.js v6，概念更直接，代价是这些状态需要自己监听。

### 1.2 方案选择

链上收款常见三种做法：

| 方式 | 每个订单的链上操作 | 优点 | 代价 | 本项目安排 |
| --- | --- | --- | --- | --- |
| 直接付款加事件核验 | 用户付款一次 | 合约最简单；后端不持有私钥、不发交易 | 金额是否正确由后端判断，异常付款需人工处理 | 基础阶段采用 |
| 商户预注册订单 | 商户注册一次，用户付款一次 | 合约可直接拒绝错误金额和错误付款人 | 后端保管热钱包、管理 nonce 和 Gas；每单多一次等待和费用 | 阶段 7 进阶对比 |
| 商户签署订单凭证 | 用户付款时携带商户签名 | 合约可校验金额，又省去逐单注册 | 需要 EIP-712 签名域、重放保护和签名验证 | 阶段 7 进阶对比 |

选择第一种的原因：后端从"既要读链又要写链"变成"只读链"。后端不需要任何私钥，不存在发交易失败、nonce 冲突、广播结果不明等问题，学习重点集中在"如何从链上得到可信的付款事实"。

### 1.3 新手概念速查

| 概念 | 含义 | 在本项目中的作用 |
| --- | --- | --- |
| 地址 | 20 字节账户标识，形如 0x 开头的 40 个十六进制字符 | 合约地址、付款人地址 |
| 私钥与签名 | 私钥控制账户，交易必须由私钥签名才能发送 | 用户私钥只在钱包中；后端不持有任何私钥 |
| 外部账户与合约账户 | 前者由私钥控制，后者是部署在链上的代码 | 付款人可能是普通钱包，也可能是智能合约钱包 |
| 交易 | 一次签名后的链上操作，有唯一的交易哈希 | 用户调用 pay 产生一笔交易 |
| 收据 | 交易被打包后的执行结果，含 status、区块号和日志 | status 为 1 表示执行成功，0 表示回滚 |
| 事件日志 | 合约执行时发出的结构化记录；indexed 字段进入 topics，可按其过滤 | OrderPaid 是后端核验付款的主要依据 |
| Wei、Gwei、Ether | 1 Ether = 10^9 Gwei = 10^18 Wei | 金额一律以 Wei 整数存储和传输 |
| Gas | 执行交易的计算费用，由发送交易的账户支付 | 用户余额必须足够"商品金额 + Gas" |
| nonce | 每个账户发送交易的递增序号 | 钱包自动管理；Anvil 重启后需要重置钱包缓存 |
| 区块与确认数 | 交易所在区块之后又产生的区块数，越多越不容易被撤销 | 后端只处理达到确认要求的区块 |
| 重组 | 链在分叉后切换到另一条分支，近期区块可能被替换 | 通过只处理已确认区块规避 |
| 最终性 | 区块在协议层面不可再被撤销的状态 | 公共网络可使用 finalized 区块标签 |
| ABI | 合约接口的 JSON 描述，用于编码调用和解码事件 | 前后端都依赖 Foundry 导出的同一份 ABI |
| RPC 节点 | 读取链数据和广播交易的 HTTP 接口 | 本地为 Anvil，测试网使用服务商节点 |

与传统支付的对照：

| 传统支付 | 链上支付 | 注意点 |
| --- | --- | --- |
| 支付流水号 | 交易哈希 | 拿到哈希只说明交易已发出，不说明执行成功或付给了哪个订单 |
| 支付回调通知 | 合约事件日志 | 没有人推送给你，需要后端主动扫描 |
| 清算完成 | 达到确认数或最终性 | 刚打包的区块仍可能被重组替换 |
| 商户密钥 | 部署者和合约所有者私钥 | 只用于部署和提现，不放进业务后端 |

## 2 系统架构与可信边界

```text
React 网页  ── HTTP API ──> FastAPI ── SQLAlchemy ──> PostgreSQL
    │                                                   ↑
    │ 请求钱包签名                                        │ 付款记录、订单状态、扫描进度
    ↓                                                   │
用户钱包 ── pay 交易 ──> Anvil 上的 Payment 合约 <── 读取事件 ── Python Worker
```

React 负责交互，钱包负责用户签名，合约负责收款并发出事件，Worker 根据链上事件维护业务状态，FastAPI 负责订单创建和查询。后端整体只读链，不发交易。

必须维持以下规则：

- 用户私钥始终保留在钱包中，网页和后端都不接收用户私钥；后端也不持有部署者或合约所有者私钥。
- 后端商品价格是定价依据，前端金额只用于展示。
- 只有 Worker 能把订单改为已支付。前端提交的交易哈希只用于展示进度和排查问题。
- 只有指定网络、指定合约发出的 OrderPaid 事件才算付款证据；合约余额和交易哈希都不能单独作为证据。
- 只处理达到确认要求的区块中的事件。
- 订单金额和到期时间创建后不可变；需要修改时创建新订单。
- 同一订单最多一笔被接受的付款；其余付款记录为异常，不覆盖已接受的付款。

## 3 从简单到复杂的实施路线

| 阶段 | 本阶段增加的能力 | 阶段结束时可以做什么 |
| --- | --- | --- |
| 0 环境与钱包 | 本地链、数据库、MetaMask 和 cast 可用 | 用命令行转账、查收据；钱包能看到测试余额 |
| 1 合约支付 | 收款、事件、提现和权限 | 用 cast 完成一笔付款并查到事件 |
| 2 Python 读链 | web3.py 读取收据和事件并核验 | 用脚本说明一笔付款为什么有效 |
| 3 订单后端 | PostgreSQL、迁移、FastAPI 和单次扫描 | 通过接口创建订单，扫描后变为已支付 |
| 4 React 网页 | 钱包连接、支付与进度展示 | 在浏览器完成完整演示，关闭页面不漏单 |
| 5 Worker 健壮化 | 常驻循环、重试、日志、到期处理 | RPC 中断、Worker 重启后自动恢复 |
| 6 一致性与幂等 | 幂等键、唯一约束、异常付款分类 | 重复请求和重复扫描不会重复入账 |
| 7 进阶对比 | 预注册、签名凭证、重组检测 | 理解基础方案省掉了哪些复杂度 |
| 8 测试网与工程化 | 身份认证、测试网部署、运维 | 形成可继续迭代的测试环境 |

### 阶段 0 环境、钱包与命令行体验

**目标**：排除工具、网络和配置问题，并在写代码前对链上操作建立直观感受。

实施步骤：

1. 准备 Python、Node.js、Foundry 和 PostgreSQL。Windows 上在 Git Bash 中运行 Foundry 官方安装脚本和 foundryup；安装不顺利时改用 WSL。PostgreSQL 可以使用本机安装版本，也可以用 Docker Compose 启动。
2. 检查 python、node、forge、anvil、cast、psql 等命令是否可用。
3. 启动 Anvil。启动日志会打印 10 个测试账户及其私钥，每个账户有 10000 ETH。
4. 准备数据库（见下文），把仓库根目录的 .env.example 复制为 .env，填写 PGSQL_* 连接信息。
5. 配置 MetaMask（见下文），确认能看到测试账户余额。
6. 用 cast 完成下文的命令行练习。
7. 启动后端，访问 http://127.0.0.1:8000/health，确认 database 和 rpc 均为 ok。再编写最小 Python 脚本读取 block_number 和测试账户余额。

**数据库准备**：使用本机 PostgreSQL 时，用超级用户执行：

```bash
psql -U postgres -c "CREATE ROLE web3_app LOGIN PASSWORD 'change_me';"
psql -U postgres -c "CREATE DATABASE web3_payment OWNER web3_app;"
```

使用 Docker 时运行 docker compose up -d postgres，账号和数据库会自动创建。两者都监听 5432 端口，只能选一个；同时需要时把 Docker 的端口映射改为 5433，并同步修改 PGSQL_PORT。

也可以使用已有的 PostgreSQL 服务器，在 .env 中填写其地址即可。建议为本项目单独建一个 UTF8 编码的库和一个普通账号，不要直接使用 postgres 超级用户；库编码为 SQL_ASCII 时，后端已在连接参数中指定 client_encoding=utf8，中文可以正常读写，但数据库本身不会校验编码。

本地配置约定：

| 服务 | 地址或标识 |
| --- | --- |
| Anvil RPC | http://127.0.0.1:8545 |
| 本地 Chain ID | 31337 |
| PostgreSQL | 127.0.0.1:5432 |
| 数据库名称 | web3_payment |
| FastAPI | http://127.0.0.1:8000 |
| React 开发服务 | http://127.0.0.1:5173 |

本地账户约定（Anvil 默认助记词生成的公开测试账户，只能用于本地，切勿在任何真实网络使用）：

| 用途 | Anvil 账户序号 | 地址 |
| --- | --- | --- |
| 部署者与合约所有者 | 0 | 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 |
| 测试用户 | 1 | 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 |

启动 Anvil：

```bash
# 不保留状态，每次启动都是一条全新的链
anvil --host 127.0.0.1 --port 8545 --chain-id 31337

# 需要在重启之间保留链上状态时使用，退出时写入文件、启动时读取
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --state ./anvil-state.json
```

**MetaMask 配置**：

1. 添加自定义网络：网络名称 Anvil，RPC 地址 http://127.0.0.1:8545，链 ID 31337，货币符号 ETH。
2. 导入账户：选择"导入账户"，粘贴 Anvil 日志中账户 1 的私钥。
3. 切换到 Anvil 网络，应看到 10000 ETH。

常见问题：Anvil 重启后链被重置，但 MetaMask 仍缓存着旧的 nonce 和交易记录，发交易时会报 nonce 相关错误或长时间挂起。处理方法是在 MetaMask 的"设置 → 高级"中清除活动数据，重置该账户的本地状态。每次重置 Anvil 后都需要执行。

**cast 命令行练习**：

```bash
export RPC=http://127.0.0.1:8545
export USER_PK=<Anvil 日志中账户 1 的私钥>

cast chain-id --rpc-url $RPC
cast block-number --rpc-url $RPC
cast balance 0x70997970C51812dc3A010C7d01b50e0d17dc79C8 --ether --rpc-url $RPC

# 单位换算
cast to-wei 0.01 ether
cast from-wei 10000000000000000

# 用户给账户 0 转 0.1 ETH，记下输出中的交易哈希
cast send 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266 --value 0.1ether --private-key $USER_PK --rpc-url $RPC

# 查看交易本身和执行结果，对比两者字段的差别
cast tx <交易哈希> --rpc-url $RPC
cast receipt <交易哈希> --rpc-url $RPC
```

练习时注意观察：交易记录了"想做什么"（from、to、value、input），收据记录了"实际结果"（status、blockNumber、gasUsed、logs）；用户余额减少的数额比 0.1 ETH 略多，差额就是 Gas 费用。这些命令也是后续排查问题的主要工具。

**交付物**：根目录 .env、数据库账号与库、RPC 和数据库连通性检查。

**验收**：/health 返回 status 为 ok；Python 读到区块号和测试账户余额；MetaMask 显示测试余额；能用 cast 转账并解释收据中的 status、blockNumber 和 gasUsed；数据库查询成功。

### 阶段 1 合约支付

**目标**：理解链上收款本身，不加入数据库和 React。

实施步骤：

1. 在仓库根目录运行 forge init contracts --no-git（仓库已由外层 git 管理，避免生成嵌套仓库），进入 contracts 目录运行 forge install OpenZeppelin/openzeppelin-contracts，删除示例文件 Counter.sol、Counter.t.sol、Counter.s.sol。forge 会自动识别 @openzeppelin/contracts/ 导入路径，无需手写 remappings。本阶段的命令都在 contracts 目录中执行。
2. 按 4.1 节编写 Payment.sol：pay 收款并发出事件，withdraw 由所有者提现。
3. 编写 Deploy.s.sol，用账户 0 部署到 Anvil，记录合约地址和部署区块号。
4. 编写 Payment.t.sol，覆盖下表中的测试场景。
5. 用 cast 调用 pay，再用 cast logs 查到 OrderPaid 事件。
6. 用 cast 以所有者身份提现，再尝试以用户身份提现并观察失败。

合约测试需要用到的 Foundry 作弊码：

| 作弊码 | 作用 | 用于测试 |
| --- | --- | --- |
| vm.deal(addr, amount) | 给地址设置 ETH 余额 | 准备付款账户 |
| vm.prank(addr) | 下一次调用以指定地址发出 | 模拟用户付款、非所有者提现 |
| vm.expectRevert(selector) | 断言下一次调用以指定错误回滚 | 零金额、非所有者、余额不足 |
| vm.expectEmit() | 断言下一次调用发出指定事件 | OrderPaid 字段正确 |

部署与命令行验证：

```bash
export OWNER_PK=<Anvil 日志中账户 0 的私钥>

cd contracts
forge script script/Deploy.s.sol --rpc-url $RPC --broadcast
# 部署脚本从环境变量 OWNER_PK 读取私钥，并把该账户设为合约所有者
# 新启动的 Anvil 上，账户 0 部署的第一个合约地址固定为 0x5FbDB2315678afecb367f032d93F642f64180aa3
# 合约地址和部署区块号可在 contracts/broadcast/Deploy.s.sol/31337/run-latest.json 中找到
export CONTRACT=<部署输出的合约地址>

ORDER_ID=$(cast keccak "demo-order-1")
cast send $CONTRACT "pay(bytes32)" $ORDER_ID --value 0.01ether --private-key $USER_PK --rpc-url $RPC
# 事件签名要写明 indexed，cast 才能把 topics 解码成字段
cast logs --address $CONTRACT --from-block 0 "OrderPaid(bytes32 indexed orderId, address indexed payer, uint256 amount)" --rpc-url $RPC
cast balance $CONTRACT --ether --rpc-url $RPC
```

**交付物**：Payment.sol、Deploy.s.sol、Payment.t.sol 和本地部署记录。

**验收**：forge test 全部通过；能用 cast 完成付款并查到事件；能说明 topics 中各项分别对应什么；直接向合约转账失败；非所有者提现失败。

### 阶段 2 用 Python 读链并核验付款

**目标**：用 Python 读取收据和事件，判断一笔付款是否有效。

实施步骤：

1. 编写 scripts/export_abi.py，从 contracts/out/Payment.sol/Payment.json 导出 ABI 到 backend/abi/ 和 frontend/src/abi/，在 app/services/chain.py 中创建 web3.py 合约对象。
2. 从根目录 .env 读取 RPC、chain_id、合约地址和部署区块，启动时检查 chain_id 一致且合约地址上有代码。
3. 编写 verify_payment_tx(tx_hash)：根据收据核验单笔交易，输出结论和原因。
4. 编写 fetch_paid_events(from_block, to_block)：按区块范围读取 OrderPaid 事件。
5. 编写 classify_payment(event, order)：比对事件与订单，给出 7.2 节的分类结果。阶段 3 起该函数由扫描器复用。
6. 用 cast 制造各种交易，观察脚本输出。

核验单笔交易的要点：

- 暂无收据表示交易未打包，结论为"待处理"，不是失败。
- 收据 status 为 0 表示交易回滚，回滚交易不会产生任何事件日志。
- 只认收据日志中 address 等于本项目合约地址的 OrderPaid。web3.py 按 ABI 解码收据日志时不会替你检查日志来源地址，必须显式过滤，否则其他合约伪造的同名事件也会被接受。
- 付款人和金额以事件字段为准，不使用交易外层的 from、to 和 value。智能合约钱包付款时，外层交易的 from 是代发者、to 是钱包合约，事件中的 payer 才是实际调用 pay 的账户。

```python
# 按区块范围读取本合约事件；get_logs 会自动按合约地址过滤
events = contract.events.OrderPaid.get_logs(from_block=start, to_block=end)
for e in events:
    e.args.orderId, e.args.payer, e.args.amount
    e.transactionHash, e.logIndex, e.blockNumber, e.blockHash
```

**交付物**：链连接检查脚本、verify_payment_tx、fetch_paid_events、classify_payment。

**验收**：正确付款被识别；随机哈希返回待处理或不存在；回滚交易、普通转账和其他合约的交易不会被判定为付款。

### 阶段 3 加入 PostgreSQL 和 FastAPI

**目标**：把链上付款与持久化的业务订单关联起来。

实施步骤：

1. 在 app/models/ 中用 SQLAlchemy 定义 orders、payments、scan_cursors 三张表，继承 app/database.py 的 Base，并在 app/models/__init__.py 中导入；然后用 alembic revision --autogenerate 生成迁移，检查后执行 alembic upgrade head。
2. 实现商品查询与创建订单 API，价格从服务端商品配置读取，chain_order_id 由后端随机生成。
3. 创建订单时直接保存为 PENDING_PAYMENT，并返回合约地址、chain_order_id 和 amount_wei。
4. 实现 scan_once：从扫描游标读取到确认区块，调用 classify_payment，在同一事务中保存付款记录、更新订单和推进游标（见 7.3 节）。
5. 提供命令行入口 python -m app.jobs.scan_payments --once，用于手动单次扫描。
6. 实现订单查询接口，以及只做记录的交易哈希提交接口。

本阶段手动运行单次扫描，逐步观察状态变化：创建订单后用 cast 付款，订单仍为 PENDING_PAYMENT；运行一次扫描后变为 PAID。

**交付物**：数据库迁移、API、单次扫描命令、pytest 接口测试。

**验收**：创建订单后数据库有记录；重启 API 后订单仍可查询；cast 付款后单次扫描使订单变为 PAID；金额错误的付款被记为异常，订单不变；重复运行扫描不会产生重复记录。

### 阶段 4 接入 React 和钱包

**目标**：做出用户可以操作的完整界面。

实施步骤：

1. 前端项目已就绪（React + TypeScript + Vite，已安装 ethers v6），Vite 将 /api 代理到 FastAPI。替换 src/App.tsx 中的占位页面开始开发。
2. 实现商品页、订单页、钱包连接组件和支付状态组件。
3. 使用 ethers.js v6 获取钱包地址和网络，核对 chain_id；网络不符时请求钱包切换到目标网络。
4. 创建订单，从响应中读取合约地址、chain_order_id 和 amount_wei，钱包调用 pay。
5. 拿到交易哈希后提交给后端记录，并调用 tx.wait() 等待交易打包。
6. 轮询订单查询接口，直到状态变为 PAID 或 EXPIRED。
7. 在 URL 中保留订单编号，刷新后从 API 恢复订单状态。
8. 运行最简 Worker：python -m app.worker，循环调用 scan_once 后休眠 WORKER_POLL_SECONDS 秒。阶段 5 再为它加入重试、日志和到期处理。

页面状态的来源：

| 页面显示 | 判断依据 |
| --- | --- |
| 等待签名 | 已唤起钱包，用户尚未确认 |
| 已提交 | 钱包返回交易哈希 |
| 已上链，等待后台确认 | tx.wait() 返回的收据 status 为 1 |
| 交易失败 | tx.wait() 返回的收据 status 为 0，可以重新付款 |
| 支付成功 | 后端返回 PAID，这是唯一的业务成功依据 |

金额从 JSON 字符串转为 BigInt 后传给合约，不先转 JavaScript Number；在 TypeScript 类型中把 amount_wei 声明为 string，可以避免误用。错误处理：ethers v6 中用户拒绝签名的错误码为 ACTION_REJECTED，余额不足为 INSUFFICIENT_FUNDS；合约自定义错误可用合约对象的 interface.parseError 解析为具体名称。监听钱包的 accountsChanged 和 chainChanged 事件，账户或网络变化后刷新页面状态。[4][9]

**交付物**：React 页面、钱包 Hook、API 客户端、付款组件、最简 Worker。

**验收**：从浏览器完成下单和付款；切错网络不能付款；拒绝签名后可以重试；付款后立即关闭页面，订单最终仍变为 PAID；页面刷新后能重新查询订单。

此阶段即可用于首次演示。

### 阶段 5 Worker 健壮化

**目标**：Worker 能长期运行，并能从各类中断中自动恢复。

实施步骤：

1. RPC 超时或不可用时采用退避重试，不推进游标，不改变任何订单状态。
2. 每批扫描的区块数由 SCAN_BATCH_SIZE 限制，避免单次 get_logs 范围过大被节点拒绝。
3. 单个事件处理异常时记录错误并告警，不能让整个 Worker 退出；同一批次仍在一个事务内，失败则整批回滚、下轮重试。
4. 加入到期处理：扫描进度对应的区块时间已经越过订单 expires_at，且订单仍为 PENDING_PAYMENT 时，才将订单标记为 EXPIRED（原因见 7.1 节）。
5. 输出结构化日志：每批扫描的区块范围、事件数、各分类数量和耗时。
6. /health 返回数据库、RPC 状态和扫描进度落后的区块数。

Worker 只运行一个实例。暂不引入 Redis、Celery 或多实例调度。

**交付物**：常驻 Worker、到期处理、结构化日志、健康检查。

**验收**：扫描中途停止 Anvil 或断开数据库后再恢复，Worker 自动继续；Worker 重启后从游标续扫；到期前付款、到期后才扫描到的订单仍能变为 PAID。

### 阶段 6 一致性与幂等

**目标**：重复请求、重复扫描和并发处理都不会造成重复入账或订单错乱。

实施步骤：

1. 创建订单接口支持 Idempotency-Key，相同业务请求复用同一订单，不同内容返回冲突。
2. payments 表以 (tx_hash, log_index) 唯一，重复扫描相同区块时直接跳过已存在的事件。
3. 用部分唯一索引保证每个订单最多一条 ACCEPTED 付款记录。
4. 订单状态更新使用条件更新：只有状态为 PENDING_PAYMENT 或 EXPIRED 时才能改为 PAID。
5. 完整实现 7.2 节的异常付款分类，提供查询异常付款的脚本，供人工退款处理。
6. 编写集成测试，覆盖第 10 节中阶段 5 和阶段 6 的场景。

如果后续增加资料发放或通知，使用独立履约状态和数据库 Outbox，让入账与待履约任务在同一事务中保存；外部动作也必须有幂等键。

**交付物**：幂等约束、异常付款查询脚本、集成测试。

**验收**：接口重复调用、事件重复扫描、同一订单多次付款都不会产生多次入账；异常付款能被完整列出。

### 阶段 7 进阶对比：基础方案省掉了什么

**目标**：在已完成的项目上，选做以下扩展之一，理解不同设计的代价。每次只做一项，建议在新分支上进行。

**7A 商户预注册订单**

合约增加 registerOrder(orderId, payer, amount, expiresAt)，只有商户能调用；pay 校验订单存在、未支付、付款人、金额和到期时间后才收款。需要额外解决：

- 后端持有商户私钥，订单状态增加 REGISTERING，用户需等待注册交易确认后才能付款。
- 同一商户账户串行管理 nonce；重启后同时核对数据库记录与节点 pending nonce。
- 先保存已签名交易及其哈希再广播；广播结果不明确时先查该哈希。
- 注册重试前读取链上订单，已存在且字段一致时直接恢复本地状态。
- 创建订单接口每被调用一次，商户就要付一次 Gas，必须加身份认证和限频，否则可被刷光余额。
- 链上按订单去重时，攻击者可以抢先用错误金额付款占用订单编号，需要额外设计。

**7B 商户签署订单凭证**

后端用 EIP-712 对订单编号、金额、到期时间和合约地址签名，用户付款时携带签名，合约验证签名后收款。需要理解签名域、链 ID 绑定、重放保护和签名私钥管理。

**7C 重组检测**

扫描器改为读到最新区块，保存每个已处理区块的哈希；每轮回看近期区块，发现哈希变化时定位共同祖先，撤回失效付款记录并重新扫描。可用 Anvil 的快照与回滚接口模拟重组。对比基础方案只读已确认区块的做法，理解实时性与复杂度的取舍。

**交付物**：所选扩展的实现、测试，以及与基础方案对比的简短说明。

### 阶段 8 迁移到公共测试网并工程化

**目标**：在真实网络条件下运行，并加入公开部署所需的安全措施。

实施顺序：

1. 增加钱包签名登录，校验域名、一次性 nonce、有效期和签名，建立服务端会话。
2. 创建订单时绑定已认证钱包；查询订单时检查访问权限。创建订单接口加限频。
3. 准备测试网环境：在 RPC 服务商处申请 Sepolia 节点地址，通过水龙头领取测试 ETH，部署者账户使用新生成的私钥，不使用任何 Anvil 默认私钥。
4. 为测试网单独部署合约，配置独立的 RPC、chain_id、合约地址和部署区块，并在区块浏览器上验证合约源码。
5. 修改确认策略：教学演示可以使用较小的确认数，正式业务按金额使用 finalized 区块标签。免费节点通常限制 get_logs 的区块范围，按节点限制调整 SCAN_BATCH_SIZE。
6. 构建 React 静态资源，反向代理统一提供网页与 API，并启用 HTTPS。
7. API 与 Worker 分开运行，增加日志、健康检查、数据库备份和异常告警。

**交付物**：测试网配置、部署说明、登录与访问控制、运行与恢复说明。

**验收**：两个钱包不能互相读取对方订单；测试网真实出块条件下完成支付，并能在区块浏览器上查到交易和事件；重启服务不丢失订单和扫描进度。

## 4 智能合约详细设计

### 4.1 接口与参考实现

| 接口 | 权限 | 行为 |
| --- | --- | --- |
| pay(orderId) payable | 任何人 | 拒绝零金额，发出 OrderPaid |
| withdraw(to, amount) | 所有者 | 提取合约余额，使用防重入和失败回滚 |
| owner() view | 公开读取 | 返回合约所有者 |

参考实现：

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract Payment is Ownable, ReentrancyGuard {
    error ZeroAmount();
    error InvalidRecipient();
    error InsufficientBalance();
    error TransferFailed();

    event OrderPaid(bytes32 indexed orderId, address indexed payer, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function pay(bytes32 orderId) external payable {
        if (msg.value == 0) revert ZeroAmount();
        emit OrderPaid(orderId, msg.sender, msg.value);
    }

    function withdraw(address payable to, uint256 amount) external nonReentrant onlyOwner {
        if (to == address(0)) revert InvalidRecipient();
        if (amount > address(this).balance) revert InsufficientBalance();
        emit Withdrawn(to, amount);
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }
}
```

部署脚本 script/Deploy.s.sol：

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {Payment} from "../src/Payment.sol";

contract Deploy is Script {
    function run() external returns (Payment payment) {
        uint256 ownerKey = vm.envUint("OWNER_PK");
        address owner = vm.addr(ownerKey);

        vm.startBroadcast(ownerKey);
        payment = new Payment(owner);
        vm.stopBroadcast();

        console.log("Payment deployed at:", address(payment));
        console.log("Owner:", owner);
    }
}
```

设计说明：

- 合约不定义 receive 和 fallback，直接向合约转账会被拒绝，避免出现无法对应订单的款项。
- 合约不在链上记录订单是否已付款。金额、到期和重复付款都由后端判断，异常付款进入人工处理。这样合约极简，也避免了"他人抢先用错误金额付款、占用订单编号"的问题。
- withdraw 按"检查 → 记录 → 外部调用"的顺序编写：先校验参数、发出事件，最后才转账；nonReentrant 放在第一个修饰符位置。这是 forge 代码检查推荐的写法。
- 使用自定义错误而不是字符串，节省 Gas，前端也能解析出具体错误名称。
- 合约余额不能作为订单支付证据；付款证据只有本合约发出的 OrderPaid 事件。

### 4.2 编号和时间

业务 order_id 使用 UUID；链上 chain_order_id 使用后端生成的随机 32 字节值，以 0x 开头的十六进制字符串保存。两者保存在同一条订单记录中，创建后不再改变。

到期时间由后端在创建订单时计算：expires_at = 当前时间 + ORDER_TTL_SECONDS。付款是否逾期以付款所在区块的时间戳判断：区块时间早于 expires_at 才接受。区块时间与服务器时间可能有少量偏差，有效期应留有余量。本地测试到期场景时，可用 cast rpc evm_increaseTime 推进链上时间，不修改电脑时间。

订单创建后不开放修改金额的接口。更换商品数量时重新下单。

## 5 PostgreSQL 数据模型

阶段 3 建立三张核心表；增加自动履约时再建立 Outbox 表。链 ID 和合约地址来自配置，不在每行重复保存；本地重新部署合约时同时重建数据库。

### 5.1 orders 订单表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 业务主键 |
| chain_order_id | VARCHAR(66) | 0x 开头的 bytes32 编号，唯一 |
| product_id | VARCHAR(64) | 商品编号 |
| amount_wei | NUMERIC(78,0) | 以 Wei 为单位的整数金额 |
| status | VARCHAR(32) | PENDING_PAYMENT、PAID 或 EXPIRED |
| idempotency_key | VARCHAR(128) 可空 | 创建订单的幂等键 |
| submitted_tx_hash | VARCHAR(66) 可空 | 前端最近提交的交易哈希，仅用于展示和排查 |
| paid_tx_hash | VARCHAR(66) 可空 | 被接受的付款交易哈希 |
| paid_by_address | VARCHAR(42) 可空 | 被接受付款的付款人 |
| paid_at | TIMESTAMPTZ 可空 | 被接受付款所在区块的时间 |
| expires_at | TIMESTAMPTZ | 付款截止时间 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 最近更新时间 |

NUMERIC 用于精确金额，78 位精度可以容纳 uint256 的十进制表示，字段仍须限制在 1 到 2^256-1 范围内。Python 按整数处理，API 将 Wei 序列化为字符串。[5]

地址先校验，再统一转为小写用于比较与存储；展示时可以转为校验和格式。状态字段增加 CHECK 约束，避免拼写错误进入数据库。

### 5.2 payments 链上付款记录表

扫描器发现的每一个 OrderPaid 事件都记录一行，无论是否被接受。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| order_id | UUID 可空 | 关联订单；未知订单编号时为空 |
| chain_order_id | VARCHAR(66) | 事件中的订单编号 |
| tx_hash | VARCHAR(66) | 交易哈希 |
| log_index | INTEGER | 事件在区块中的序号 |
| block_number | BIGINT | 所在区块 |
| block_hash | VARCHAR(66) | 所在区块哈希，用于审计 |
| block_time | TIMESTAMPTZ | 所在区块时间 |
| payer_address | VARCHAR(42) | 事件中的付款人 |
| amount_wei | NUMERIC(78,0) | 事件中的金额 |
| result | VARCHAR(32) | ACCEPTED、AMOUNT_MISMATCH、LATE、DUPLICATE 或 UNKNOWN_ORDER |
| created_at | TIMESTAMPTZ | 记录时间 |

一笔交易可能包含多个事件，因此用 tx_hash 加 log_index 唯一标识一个事件。

### 5.3 scan_cursors 扫描游标表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | SERIAL | 主键 |
| chain_id | BIGINT | 网络 |
| contract_address | VARCHAR(42) | 合约地址 |
| last_scanned_block | BIGINT | 已处理完的最后一个区块；初始值为部署区块减 1 |
| last_scanned_block_time | TIMESTAMPTZ 可空 | 该区块的时间，用于到期判断 |
| updated_at | TIMESTAMPTZ | 最近更新时间 |

### 5.4 必要约束和索引

- orders：UNIQUE(chain_order_id)。
- orders：UNIQUE(idempotency_key)，幂等键按调用主体或本地演示范围唯一。
- payments：UNIQUE(tx_hash, log_index)，重复扫描时插入冲突即跳过。
- payments：部分唯一索引 UNIQUE(order_id) WHERE result = 'ACCEPTED'，每个订单最多一笔被接受的付款。
- scan_cursors：UNIQUE(chain_id, contract_address)。
- orders 的 status 与 expires_at 建立组合索引，供到期处理查询。

## 6 FastAPI 接口约定

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /api/v1/config | 公开链 ID、合约地址和确认要求（已实现） |
| GET | /api/v1/products | 返回商品与展示价格 |
| POST | /api/v1/orders | 创建订单，直接返回待付款状态 |
| GET | /api/v1/orders/{order_id} | 查询订单状态和付款信息 |
| POST | /api/v1/orders/{order_id}/tx-hash | 记录前端提交的交易哈希，不做核验、不改变状态 |
| GET | /health | 检查数据库和 RPC（已实现）；阶段 5 加入扫描进度 |

业务接口沿用模板的 /api/v1 前缀，路由文件放在 app/api/v1/ 下，在 app/main.py 中注册。/health 不在 /api 下，部署后 nginx 不对外转发，只供容器和运维检查使用。

创建订单返回 201 与订单资源。前端主要轮询 GET 接口；订单状态只由 Worker 改变。

创建请求示例：

```json
{
  "product_id": "lesson17"
}
```

订单响应示例，地址和编号为格式占位值：

```json
{
  "order_id": "123e4567-e89b-42d3-a456-426614174000",
  "chain_order_id": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "amount_wei": "10000000000000000",
  "chain_id": 31337,
  "contract_address": "0x2222222222222222222222222222222222222222",
  "status": "PENDING_PAYMENT",
  "submitted_tx_hash": null,
  "paid_tx_hash": null,
  "paid_by_address": null,
  "expires_at": "2026-10-24T12:30:00Z"
}
```

基础阶段接口只用于本地演示。因为后端不发交易，创建订单不会消耗任何链上费用，但接入公共环境前仍须增加身份认证、订单归属校验、请求限频和明确的错误码。连接钱包得到一个地址不等于已通过服务端身份认证。

## 7 支付核验和状态流转

### 7.1 订单状态

```text
PENDING_PAYMENT → PAID
       │           ↑
       └→ EXPIRED ─┘（到期前的有效付款晚于到期处理才被扫描到）
```

PAID 只由扫描器在接受一笔付款时写入。EXPIRED 由到期处理写入，条件是扫描进度对应的区块时间已经越过 expires_at：此时所有到期前打包的区块都已扫描完，不会再出现有效付款。如果仅凭服务器时间判断，可能在扫描器尚未处理完早于到期的区块时就过早标记到期；即便如此，状态图中 EXPIRED 到 PAID 的转换仍会兜底纠正。

### 7.2 付款分类规则

扫描器读取的事件来自本合约地址，且回滚交易不产生事件，因此每个事件都对应一笔执行成功的付款。对每个事件按顺序判断：

| 顺序 | 条件 | 分类 | 订单变化 |
| --- | --- | --- | --- |
| 1 | 找不到 chain_order_id 对应的订单 | UNKNOWN_ORDER | 无 |
| 2 | 事件金额不等于订单 amount_wei | AMOUNT_MISMATCH | 无 |
| 3 | 区块时间不早于订单 expires_at | LATE | 无 |
| 4 | 订单已有被接受的付款 | DUPLICATE | 无 |
| 5 | 以上都不满足 | ACCEPTED | 更新为 PAID，写入付款信息 |

除 ACCEPTED 外的分类都是需要人工处理的异常付款，资金已进入合约，可由所有者提现后退还。

### 7.3 扫描流程

```text
确认区块 = 最新区块号 - (REQUIRED_CONFIRMATIONS - 1)
起点 = 游标 last_scanned_block + 1
当 起点 <= 确认区块：
    终点 = min(起点 + SCAN_BATCH_SIZE - 1, 确认区块)
    读取 [起点, 终点] 内本合约的 OrderPaid 事件
    在一个数据库事务内：
        逐个事件分类并插入 payments（冲突即跳过）
        ACCEPTED 时条件更新订单为 PAID
        游标推进到终点，并记录终点区块的时间
    起点 = 终点 + 1
```

付款记录和游标在同一事务中提交：要么整批成功，要么整批回滚后重扫，不会出现"游标推进了但付款没记录"的情况。

### 7.4 确认策略

确认数等于最新区块号减付款区块号再加 1。本地 REQUIRED_CONFIRMATIONS 为 1，即扫描到最新区块。需要演示多次确认时，用 anvil --block-time 2 按时间出块；默认的自动出块模式下，没有新交易就不会产生新区块，确认数不会增长。

只处理已确认区块是本方案规避重组的方式：被处理的区块越旧，被替换的可能越小。公共网络上可以直接读取 finalized 区块号作为扫描上限，正常情况下 finalized 区块不会再被替换，代价是确认时间更长。付款记录仍保存 block_hash 以便审计。需要更快确认时，参见阶段 7C 的重组检测。

## 8 React 页面和交互

| 页面或组件 | 展示内容 | 关键行为 |
| --- | --- | --- |
| 商品页 ProductPage | 商品、价格、网络、钱包地址 | 连接钱包并创建订单 |
| 订单页 OrderPage | 编号、金额、状态、到期时间 | 发起支付 |
| WalletConnect | 当前地址和网络 | 处理连接、账户切换与网络变化 |
| PaymentStatus | 交易哈希、阶段 4 表中的进度 | 轮询后端状态并提供重试入口 |

钱包未安装、网络不匹配、订单已支付和已过期时，支付按钮分别给出对应状态。钱包签名弹窗被取消不记成链上失败，也不关闭订单。

等待阶段禁用重复点击只用于改善交互，不能代替后端的重复付款判断和数据库唯一约束。

开发时 Vite 将 /api 代理到 FastAPI，减少跨域配置。部署时使用统一域名反向代理，前端不暴露包含秘密凭证的 RPC 配置。

## 9 工程目录和运行约定

### 9.1 目录结构

标注"已有"的文件来自模板改造，已可运行；其余在对应阶段新建。

```text
web3/
├── contracts/                      阶段 1 用 forge init contracts 创建
│   ├── src/Payment.sol
│   ├── script/Deploy.s.sol
│   ├── test/Payment.t.sol
│   ├── lib/openzeppelin-contracts/
│   ├── foundry.toml
├── backend/
│   ├── app/
│   │   ├── main.py                 已有：应用入口、/health
│   │   ├── database.py             已有：engine、Session、Base、get_db
│   │   ├── core/config.py          已有：从根目录 .env 读取全部配置，由 PGSQL_* 拼出连接串
│   │   ├── api/v1/
│   │   │   ├── config.py           已有：GET /api/v1/config
│   │   │   ├── products.py         已有：GET /api/v1/products
│   │   │   └── orders.py           已有：创建、查询订单，记录交易哈希
│   │   ├── models/                 已有：orders、payments、scan_cursors
│   │   ├── schemas/                已有：order.py 请求与响应模型
│   │   ├── services/
│   │   │   ├── chain.py            已有：web3 连接、合约对象、部署检查
│   │   │   ├── orders.py           已有：订单业务
│   │   │   ├── products.py         已有：商品与服务端定价
│   │   │   └── payments.py         已有：verify_payment_tx、fetch_paid_events、classify_payment
│   │   ├── jobs/
│   │   │   ├── scan_payments.py    已有：scan_once 与 --once 命令
│   │   │   └── expire_orders.py    阶段 5
│   │   ├── worker.py               已有：常驻循环扫描
│   │   └── cli.py                  已有：链上调试命令 check、verify、events
│   ├── alembic/                    已有：初始迁移建立三张表
│   ├── abi/Payment.json            已有：由 scripts/export_abi.py 导出
│   ├── tests/                      已有：配置、付款分类、订单接口与扫描测试
│   ├── alembic.ini                 已有
│   └── Dockerfile.backend          已有
├── frontend/                       已有：React + TypeScript + Vite，已安装 ethers v6
│   ├── src/
│   │   ├── App.tsx                 已有：页面切换，订单号保存在 URL
│   │   ├── pages/                  已有：ProductPage、OrderPage
│   │   ├── components/             已有：WalletConnect、PaymentStatus
│   │   ├── hooks/useWallet.ts      已有：钱包账户与网络状态
│   │   ├── services/api.ts         已有：后端 API 客户端
│   │   ├── services/payment.ts     已有：调用 pay 与错误提示
│   │   └── abi/Payment.json        已有：由 scripts/export_abi.py 导出
│   ├── vite.config.ts              已有：/api 代理到 127.0.0.1:8000
│   ├── nginx.conf                  已有：部署时转发 /api/ 到后端
│   ├── Dockerfile.frontend         已有
│   └── package.json
├── scripts/export_abi.py           已有：把 ABI 导出到前后端
├── docker-compose.yml              已有：postgres；backend、frontend 在 app 配置组中
├── .env.example                    已有：配置模板，复制为 .env 后填写
├── requirements.txt                已有：唯一的 Python 依赖清单，本机安装与 Docker 构建共用
├── .venv/                          Python 虚拟环境，位于仓库根目录
└── README.md
```

OpenZeppelin 以 git 子模块形式安装在 contracts/lib/ 下，克隆仓库后需执行 git submodule update --init --recursive；forge 自动识别其导入路径。ABI 从 Foundry 编译产物统一导出给前后端，不手工维护两份不同版本。Node 使用 package-lock.json 锁定依赖；Python 依赖统一写在根目录 requirements.txt 中，目前是版本范围，确定可用版本后可用 pip freeze 生成锁定文件。web3.py 固定在 7.x，与本文的代码示例一致。

### 9.2 配置

后端从仓库根目录的 .env 读取配置（从 .env.example 复制），无论在哪个目录启动都读这一份。后端不需要任何私钥：

```dotenv
PGSQL_HOST=127.0.0.1
PGSQL_PORT=5432
PGSQL_USER=web3_app
PGSQL_PASSWORD=change_me
PGSQL_DATABASE=web3_payment
RPC_URL=http://127.0.0.1:8545
CHAIN_ID=31337
CONTRACT_ADDRESS=<部署后填写>
DEPLOYMENT_BLOCK=<部署区块高度>
REQUIRED_CONFIRMATIONS=1
ORDER_TTL_SECONDS=1800
SCAN_BATCH_SIZE=500
WORKER_POLL_SECONDS=3
```

密码中含 @、% 等特殊字符时无需手动转义，config.py 会自动处理。部署者私钥只在执行 forge script 和 cast 提现时通过终端环境变量提供，不写入任何配置文件，也不提交到仓库。

### 9.3 运行

开发阶段（0 至 7）各服务直接在本机运行，便于观察日志和调试；Docker Compose 中的 backend 和 frontend 归在 app 配置组，阶段 8 部署时用 docker compose --profile app up 启动。在容器中运行时 RPC 地址为 http://host.docker.internal:8545，Anvil 仍运行在宿主机上，因为浏览器里的 MetaMask 需要连接 127.0.0.1:8545。

推荐运行顺序：数据库与 Anvil、合约部署、ABI 导出与配置、Alembic 迁移、FastAPI、Worker、React。服务启动时检查 chain_id 一致且合约地址上有代码。

以下命令在 Git Bash 中执行；未标注"阶段"的入口现在即可运行：

```bash
# 激活仓库根目录的虚拟环境，并安装后端依赖
source .venv/Scripts/activate
pip install -r requirements.txt

# 数据库：本机 PostgreSQL 按阶段 0 建库；或使用 Docker
docker compose up -d postgres

# contracts 目录（阶段 1）
forge test
forge script script/Deploy.s.sol --rpc-url $RPC --broadcast   # 需先 export OWNER_PK

# 仓库根目录（阶段 2）
python scripts/export_abi.py

# backend 目录
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
python -m app.jobs.scan_payments --once     # 阶段 3
python -m app.worker                        # 阶段 4
pytest

# frontend 目录
npm ci
npm run dev
npm run build
```

本地链重置：不带 --state 启动的 Anvil 每次重启都是一条新链。由于部署者账户 nonce 从 0 开始，重新部署后合约地址可能与上次相同，但旧数据已不存在。重置链时的固定流程：重新部署合约、更新配置、清空数据库并重新迁移、在 MetaMask 中清除活动数据。需要保留数据时使用 --state 持久化 Anvil 状态。

## 10 测试矩阵和最终验收

| 场景 | 预期结果 | 阶段 |
| --- | --- | --- |
| 正常付款 | 合约收款并发出字段正确的事件 | 1 |
| 零金额付款或直接向合约转账 | 合约拒绝 | 1 |
| 非所有者提现、超额提现 | 合约拒绝 | 1 |
| 回滚交易、普通转账、其他合约的同名事件 | 不被判定为付款 | 2 |
| 前端修改价格 | 后端忽略，使用服务端定价 | 3 |
| API 重启 | 订单数据仍可读取 | 3 |
| 金额不符的付款 | 记为 AMOUNT_MISMATCH，订单不变 | 3 |
| 切错网络或钱包拒签 | 页面可恢复，订单不误记付款 | 4 |
| 用户付款后关闭网页 | Worker 最终确认付款 | 4 |
| RPC 暂时不可用 | 游标不推进，恢复后继续 | 5 |
| Worker 中断后重启 | 从游标续扫，不漏不重 | 5 |
| 到期前付款、到期后才扫描到 | 订单仍变为 PAID | 5 |
| 到期后付款 | 记为 LATE，订单不变 | 5 |
| 相同幂等键提交多次 | 复用同一订单；不同内容返回冲突 | 6 |
| 相同区块重复扫描 | 不产生重复记录 | 6 |
| 同一订单付款两次 | 第一次 ACCEPTED，第二次 DUPLICATE | 6 |
| 另一钱包访问受保护订单 | 服务端拒绝越权访问 | 8 |

数据库集成测试使用独立 PostgreSQL 测试数据库，链上集成测试使用可重置的 Anvil。不要用 SQLite 代替数据库约束与并发测试；核心核验逻辑要有真实交易和事件的集成用例，不能只模拟返回结果。

第十七课基础验收以阶段 4 为界：网页能完成下单和支付，关闭页面不漏单，后端能说明付款有效的依据。完整项目验收以阶段 6 为界：重启可以恢复，重复处理不会重复入账，到期与异常付款处理正确。阶段 7 和阶段 8 作为第十八课的扩展练习。

## 11 实施检查清单

- [ ] Anvil、PostgreSQL 连通，MetaMask 显示测试余额。
- [ ] 能用 cast 转账、查看交易和收据，并解释其区别。
- [ ] 合约付款、提现及失败路径测试通过；能用 cast 查到事件。
- [ ] Python 能核验单笔交易并输出原因，能按区块范围读取事件。
- [ ] Alembic 可在空 PostgreSQL 数据库建立表结构。
- [ ] FastAPI 创建订单和查询状态可用；单次扫描能使订单变为 PAID。
- [ ] React 能连接钱包并完成付款演示；关闭网页后订单仍变为 PAID。
- [ ] Worker 能从 RPC 中断和重启中恢复；到期处理正确。
- [ ] 重复请求、重复扫描、重复付款测试通过；异常付款可查询。
- [ ] README 记录启动顺序、测试命令和本地链重置流程。

## 12 官方参考资料

以下资料用于核对接口能力和基础行为；项目架构、阶段安排与验收标准为本方案的设计。

1. [FastAPI 并发与同步接口](https://fastapi.tiangolo.com/async/)
2. [SQLAlchemy PostgreSQL 与 psycopg 方言](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
3. [web3.py 交易与链上查询](https://web3py.readthedocs.io/en/stable/web3.eth.html)
4. [ethers.js v6 入门与钱包交互](https://docs.ethers.org/v6/getting-started/)
5. [PostgreSQL 精确数值类型](https://www.postgresql.org/docs/current/datatype-numeric.html)
6. [web3.py 合约对象与事件](https://web3py.readthedocs.io/en/stable/web3.contract.html)
7. [Foundry 文档（forge、cast、anvil 与作弊码）](https://getfoundry.sh/)
8. [OpenZeppelin Contracts 5.x](https://docs.openzeppelin.com/contracts/5.x/)
9. [ethers.js v6 错误码](https://docs.ethers.org/v6/api/utils/errors/)
