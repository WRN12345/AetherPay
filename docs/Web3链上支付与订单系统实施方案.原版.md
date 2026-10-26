# Web3 链上支付与订单系统实施方案

**第十七课 从最小支付到完整订单系统**

技术栈：Python FastAPI PostgreSQL React Solidity Foundry Anvil  
编制日期：2026 年 10 月 24 日

本项目围绕一个具体业务展开：用户购买课程资料，在 React 网页连接钱包，使用测试 ETH 支付；智能合约保存支付记录，Python 后端独立核验链上事实，并将 PostgreSQL 中的订单更新为已支付。

建议先完成阶段 0 至阶段 4，得到可以演示的最小完整项目；再完成阶段 5 和阶段 6，加入后台补偿、重启恢复和一致性处理；阶段 7 用于第十八课的测试网与工程化扩展。每个阶段都给出操作顺序、交付物和验收标准，可以按顺序实施，不必一次性引入全部复杂度。

## 1 项目目标与边界

第一版采用单商户、单链、固定商品价格、原生测试 ETH。示例商品为课程资料，价格为 0.01 ETH，即 10000000000000000 Wei。价格由后端商品配置决定，前端只提交商品编号和付款钱包地址。

完成后应能演示以下结果：

1. 用户连接钱包，检查所在网络，创建订单。
2. 后端生成业务订单并将金额和付款地址注册到链上。
3. 注册确认后，用户调用支付合约并附带准确的 ETH 金额。
4. 后端检查交易、收据、事件、合约状态与确认条件。
5. 订单在数据库中完成一次有效状态更新。
6. 完成后台扫描阶段后，用户关闭网页也不会遗漏有效付款。

基础阶段暂不实现退款、ERC20、多商户、跨链、法币计价、库存扣减和自动发货。阶段 4 的界面闭环依赖前端触发验证；阶段 5 才保证脱离页面继续发现与处理支付。公共部署前加入钱包身份认证和订单访问控制。

### 1.1 技术选型

| 层级 | 技术 | 主要作用 |
| --- | --- | --- |
| 业务后端 | Python 与 FastAPI | 订单接口、输入校验和状态查询 |
| 数据库 | PostgreSQL | 保存订单、交易记录与扫描进度 |
| 数据访问 | SQLAlchemy 与 psycopg | ORM、数据库事务和连接池 |
| 数据迁移 | Alembic | 管理表结构的创建和升级 |
| 链上交互 | web3.py | 广播注册交易、查询收据和事件 |
| 前端 | React 与 Vite | 商品页、钱包连接、支付与结果展示 |
| 钱包交互 | ethers.js v6 | 读取网络、获取签名者、调用支付合约 |
| 智能合约 | Solidity | 订单注册、校验付款和保存支付状态 |
| 开发工具 | Foundry 与 Anvil | 编译、部署、测试和本地链运行 |
| 后台处理 | 独立 Python Worker | 注册补偿、查链与支付确认 |
| 测试 | Forge 与 pytest | 合约测试、接口测试和集成验证 |
| 本地服务 | Docker Compose | 启动 PostgreSQL 和持久化数据卷 |

Python 用于全部业务后端及后台处理。EVM 合约使用 Solidity，浏览器钱包交互使用 JavaScript。第一版选择同步 SQLAlchemy 和同步 web3.py，减少学习负担；同步 FastAPI 接口使用普通 def，持续查链放到独立进程。后续若改为异步，应成套调整数据库驱动和 RPC 调用，避免在 async def 内直接执行阻塞操作。[1][2][3]

### 1.2 方案选择

| 方式 | 每个订单的链上操作 | 优点 | 代价 | 本项目安排 |
| --- | --- | --- | --- | --- |
| 商户预注册订单 | 商户注册一次，用户付款一次 | 金额和付款地址可直接在链上检查 | 商户需要 Gas 和交易发送管理 | 本课采用 |
| 商户签署订单凭证 | 用户付款时携带商户签名 | 可省去逐单注册交易 | 需要签名域、重放保护和签名验证 | 后续扩展 |

## 2 系统架构与可信边界

```text
React 网页  ── HTTP API ──> FastAPI ── SQLAlchemy ──> PostgreSQL
    │                           │                         ↑
    │ 请求钱包签名               │ 查询和广播 RPC           │ 持久化处理结果
    ↓                           ↓                         │
用户钱包 ── 支付交易 ──> Anvil 上的 Payment 合约 <── Python Worker
```

React 负责交互，钱包负责用户签名，合约负责约束支付，FastAPI 与 Worker 根据链上证据维护业务状态。数据库保存业务订单及其关联记录；链上收据、事件和状态用于证明付款。

必须维持以下规则：

- 用户私钥始终保留在钱包中，网页和后端都不接收用户私钥。
- 后端商品价格是定价依据，前端金额只用于展示。
- 提交交易哈希只创建待验证线索，不能直接把订单改为已支付。
- 只有指定网络、指定合约、指定订单的有效付款才能完成订单。
- 已注册的订单金额、付款地址和到期时间保持不可变；需要修改时创建新订单。
- 同一订单最多完成一次业务入账；失败交易不消耗订单的付款机会。

## 3 从简单到复杂的实施路线

| 阶段 | 本阶段增加的能力 | 阶段结束时可以做什么 |
| --- | --- | --- |
| 0 环境准备 | 本地链、数据库和工具可连接 | 查询链 ID 与区块，连通 PostgreSQL |
| 1 合约闭环 | 注册、付款、事件和权限 | 不经过网页即可完成一笔测试付款 |
| 2 Python 闭环 | Python 连接合约并验证支付 | 用脚本说明一笔付款为什么有效 |
| 3 订单后端 | PostgreSQL、迁移和 FastAPI | 通过接口创建、注册和核验订单 |
| 4 React 网页 | 钱包连接、支付与进度展示 | 在浏览器完成完整演示 |
| 5 后台补偿 | Worker、事件扫描和游标 | 关闭网页仍可确认支付 |
| 6 一致性处理 | 幂等、崩溃恢复和重组处理 | 重启与重复请求不会重复入账 |
| 7 工程扩展 | 公共测试网、身份认证和部署 | 形成可继续迭代的测试环境 |

### 阶段 0 先让环境可连接

**目标**：排除工具、网络和配置问题，暂不编写订单业务。

实施步骤：

1. 准备 Python、Node.js、Foundry，以及 PostgreSQL 或用于启动数据库的 Docker 环境。
2. 检查 python、node、forge、anvil 等命令是否可用。
3. 启动 Anvil，显式设置本地 RPC 和链 ID。
4. 启动 PostgreSQL，创建 web3_payment 数据库和专用本地账号。
5. 编写最小 Python 连通性检查，读取 chain_id、block_number 和测试账户余额。
6. 使用数据库客户端或 Python 执行 SELECT 1。

本地配置约定：

| 服务 | 地址或标识 |
| --- | --- |
| Anvil RPC | http://127.0.0.1:8545 |
| 本地 Chain ID | 31337 |
| PostgreSQL | 127.0.0.1:5432 |
| 数据库名称 | web3_payment |
| FastAPI | http://127.0.0.1:8000 |
| React 开发服务 | http://127.0.0.1:5173 |

启动 Anvil 的命令示例：

```bash
anvil --host 127.0.0.1 --port 8545 --chain-id 31337
```

**交付物**：环境配置示例、数据库启动配置、RPC 和数据库连通性检查。

**验收**：Python 读到 chain_id 为 31337，能够查询区块和测试账户余额，数据库查询成功。

### 阶段 1 只完成合约支付

**目标**：先理解链上支付本身，不加入数据库和 React。

实施步骤：

1. 定义订单结构，包含 payer、amount、expiresAt、exists 和 paid。
2. 商户调用 registerOrder 注册一个随机 bytes32 订单编号。
3. 指定测试付款账户调用 pay，并发送 0.01 ETH。
4. 检查订单 paid 字段、合约余额和 OrderPaid 事件。
5. 编写拒绝错误金额、错误付款人、过期和重复付款的合约测试。
6. 加入商户提现功能，验证提现权限、余额变化与防重入处理。

阶段 1 就保留权限校验、金额匹配和重复付款限制。这些规则直接决定支付是否正确，不应推迟到工程优化阶段。

**交付物**：Payment.sol、Deploy.s.sol、Payment.t.sol 和本地部署记录。

**验收**：正常付款成功；少付、多付、未注册订单、错误付款人和重复付款均失败；非商户不能注册订单或提现。

### 阶段 2 用 Python 完成链上闭环

**目标**：把注册、付款验证和证据输出迁移到 Python。

实施步骤：

1. 从 Foundry 编译产物导出 ABI，创建 web3.py 合约对象。
2. Python 读取网络、商户地址和合约配置。
3. 用商户测试账户注册订单，保存并查询注册交易哈希。
4. 通过 Cast 或单独的本地测试脚本模拟用户付款。
5. 编写 verify_payment，交叉验证交易、收据、事件和合约状态。
6. 输出订单编号、付款人、金额、区块号、区块哈希和验证原因。

Python 模拟用户付款仅用于本地测试。网页接入后，用户付款由钱包签名，不把用户签名逻辑搬到服务器。

**交付物**：链连接检查脚本、订单注册脚本、支付验证函数。

**验收**：正确付款被识别；随机哈希、失败交易、普通转账和其他订单的交易不能被判定为当前订单付款。

### 阶段 3 加入 PostgreSQL 和 FastAPI

**目标**：让链上操作与持久化业务订单关联起来。

实施步骤：

1. 使用 SQLAlchemy 定义订单、链上交易和扫描游标模型，通过 Alembic 建表。
2. 实现商品查询与创建订单 API，价格从服务端商品配置读取。
3. 创建订单时提交数据库事务，保存 REGISTERING 状态。
4. 基础版提供单次注册任务，由命令行处理待注册订单；不在创建订单请求内等待出块。
5. 注册交易成功且链上字段匹配后，将订单更新为 PENDING_PAYMENT。
6. 实现交易哈希提交接口和幂等的单次核验接口。
7. 提供订单查询接口，返回当前状态和确认进度。

单次任务是阶段 5 常驻 Worker 的前身，业务函数保持复用。这个阶段允许人工运行注册任务和核验请求，以便逐步观察状态变化。

**交付物**：数据库迁移、API、单次注册任务、pytest 接口测试。

**验收**：创建订单后数据库有记录；重启 API 后订单仍可查询；注册成功才开放付款；无效交易不会改变付款结果。

### 阶段 4 接入 React 和钱包

**目标**：做出用户可以操作的完整界面。

实施步骤：

1. 创建 React 与 Vite 项目，通过开发代理访问 FastAPI 的 /api 路径。
2. 实现商品页、订单页、钱包连接组件和支付状态组件。
3. 使用 ethers.js v6 获取钱包地址和网络，核对 chain_id。
4. 创建订单并轮询注册状态；只有 PENDING_PAYMENT 才能发起付款。
5. 从 API 读取合约地址、链上订单编号和 amount_wei，钱包调用 pay。
6. 提交交易哈希，定期触发单次核验，并查询订单展示结果。
7. 在 URL 中保留订单编号，刷新后从 API 恢复订单状态。

金额从 JSON 字符串转为 BigInt 后传给合约，不先转 JavaScript Number。用户拒绝签名、余额不足、交易失败、钱包地址变化和网络变化分别展示可理解的提示。[4]

**交付物**：React 页面、钱包 Hook、API 客户端、付款组件。

**验收**：从浏览器完成下单和付款；切错网络不能付款；拒绝签名后可以重试；页面刷新后能重新查询订单。

此阶段用于首次演示。关闭页面后自动发现支付的能力在下一阶段完成。

### 阶段 5 让后台独立确认付款

**目标**：支付处理不再依赖浏览器持续在线。

实施步骤：

1. 将单次注册处理包装成独立 Worker 的周期任务。
2. 处理已提交的付款交易哈希，复用 verify_payment。
3. 按区块范围扫描本合约的 OrderPaid 事件，发现没有上报哈希的付款。
4. 从合约部署区块开始扫描，记录 last_block_number 与 last_block_hash。
5. 在同一数据库事务中保存本批处理结果和扫描进度。
6. RPC 超时采用退避重试；单笔异常不能阻塞全部订单。
7. 对已发现付款继续计算确认数，达到条件后完成订单。

先运行一个 Worker，串行发送商户注册交易。暂不引入 Redis、Celery 或多个并行签名进程。

**交付物**：常驻 Worker、事件扫描器、扫描游标与结构化日志。

**验收**：用户付款后立即关闭页面，数据库最终仍变为 PAID；Worker 重启后接着处理；重复扫描相同区块不会重复入账。

### 阶段 6 处理重复请求与故障恢复

**目标**：处理数据库与区块链不能共用事务带来的问题。

实施步骤：

1. 创建订单接口支持 Idempotency-Key，相同业务请求复用同一订单。
2. 保存签名交易及本地计算出的哈希，再广播；广播结果不明确时优先查该哈希。
3. 同一商户账户串行管理 nonce。重启后同时核对数据库交易记录与节点 pending nonce，不能只依赖其中一个。
4. 订单注册重试前读取链上订单，已经存在且字段一致时直接恢复本地状态。
5. 采用数据库唯一约束和条件状态更新，避免提交哈希接口与事件扫描同时重复完成订单。
6. 保存付款区块哈希并核对规范链，重组后撤回失效记录并重新扫描。
7. 区分失败交易、暂未出收据、RPC 不可用和付款不匹配，避免全部记成失败订单。
8. 加入到期对账，确保到期前成功付款但稍晚才被发现的订单仍然入账。

基础版先保证订单状态和入账记录的幂等。如果后续增加资料发放或通知，使用独立履约状态和数据库 Outbox，让入账与待履约任务在同一事务中保存；外部动作也必须有幂等键。链上重组发生后，已经发出的资料不能靠回滚数据库自动收回，需要按业务规则进入复核。

**交付物**：故障恢复逻辑、幂等约束、重组处理与集成测试。

**验收**：广播后重启、付款后 RPC 中断、接口重复调用、事件重复扫描和模拟链重组均不会造成重复入账或永久遗漏。

### 阶段 7 迁移到公共测试网并扩展

**目标**：在完整本地项目基础上学习真实网络条件和部署。

实施顺序：

1. 增加钱包签名登录，校验域名、一次性 nonce、有效期和签名，建立服务端会话。
2. 创建订单时绑定已认证钱包；查询和修改订单时检查访问权限。
3. 为公共测试网单独部署合约，配置独立 RPC、chain_id、地址和部署区块。
4. 商户测试账户单独管理，修改确认或最终性策略，不沿用本地即时确认假设。
5. 构建 React 静态资源，反向代理统一提供网页与 API，并启用 HTTPS。
6. API 与 Worker 分开运行，增加日志、健康检查、数据库备份和异常告警。
7. 有需要时再加入 ERC20、签名订单、退款或多商户，每次只扩展一项主要能力。

**交付物**：测试网配置、部署说明、登录与访问控制、运行与恢复说明。

**验收**：两个钱包不能互相读取或修改受保护订单；测试网真实出块条件下完成支付；重启服务不丢失订单和扫描进度。

## 4 智能合约详细设计

### 4.1 接口与状态

| 接口 | 权限 | 行为 |
| --- | --- | --- |
| registerOrder(orderId, payer, amount, expiresAt) | 商户 | 注册唯一订单，校验地址、金额与未来到期时间 |
| pay(orderId) payable | 绑定的钱包 | 校验订单并记录付款，拒绝少付和多付 |
| orders(orderId) view | 公开读取 | 返回链上订单结构 |
| withdraw(to, amount) | 商户 | 提取合约收入，使用防重入和失败回滚 |

链上订单结构：

```solidity
struct Order {
    address payer;
    uint256 amount;
    uint256 expiresAt;
    bool exists;
    bool paid;
}
```

事件设计：

```solidity
event OrderRegistered(
    bytes32 indexed orderId,
    address indexed payer,
    uint256 amount,
    uint256 expiresAt
);

event OrderPaid(
    bytes32 indexed orderId,
    address indexed payer,
    uint256 amount
);
```

pay 的执行顺序为：检查存在、未支付、付款人、金额和到期时间，然后更新 paid，再发出事件。支付过程中不向商户执行外部转账，资金保存在合约内，由独立提现接口处理。

直接向合约地址转账不能完成订单；普通 receive 和 fallback 应拒绝非预期调用。合约余额也不能单独作为订单支付证据。

### 4.2 编号和时间

业务 order_id 使用 UUID；链上 chain_order_id 使用后端生成的随机 32 字节值。两者原样保存在同一条订单记录中，重试时复用，不能重新生成。

到期规则统一为 block.timestamp < expiresAt 才允许支付。教学阶段可以使用最新区块时间加订单有效期生成 expiresAt；本地测试通过推进链上时间验证到期，不依赖修改电脑时间。

订单只注册一次，不开放修改已注册金额的接口。更换钱包或修改商品数量时重新下单。

## 5 PostgreSQL 数据模型

阶段 3 建立三张核心表；阶段 6 增加事件记录表；增加自动履约时再建立 Outbox 表。

### 5.1 orders 订单表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 业务主键 |
| deployment_id | UUID | 本次合约部署的业务命名空间 |
| chain_order_id | VARCHAR(66) | 0x 开头的 bytes32 编号 |
| product_id | VARCHAR(64) | 商品编号 |
| payer_address | VARCHAR(42) | 付款钱包地址 |
| amount_wei | NUMERIC(78,0) | 以 Wei 为单位的整数金额 |
| chain_id | BIGINT | 目标网络 |
| contract_address | VARCHAR(42) | 支付合约地址 |
| status | VARCHAR(32) | 业务订单状态 |
| idempotency_key | VARCHAR(128) | 创建订单的幂等键 |
| expires_at | TIMESTAMPTZ | 与链上 expiresAt 对应的时间 |
| paid_at | TIMESTAMPTZ | 已验证付款所在区块时间 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 最近更新时间 |

NUMERIC 用于精确金额，78 位精度可以容纳 uint256 的十进制表示，但字段仍须限制在 1 到 2^256-1 范围内。输入层拒绝小数 Wei，避免数据库把带小数的输入舍入为整数。Python 按整数处理，API 将 Wei 序列化为字符串。[5]

地址先校验，再统一规范化用于比较与唯一约束；展示时可以使用校验和地址。订单状态字段增加 CHECK 约束，避免拼写错误进入数据库。

### 5.2 chain_transactions 链上交易表

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | UUID | 主键 |
| order_id | UUID | 关联订单 |
| tx_type | VARCHAR(24) | REGISTER 或 PAYMENT |
| chain_id | BIGINT | 网络 |
| deployment_id | UUID | 部署命名空间 |
| tx_hash | VARCHAR(66) | 交易哈希 |
| sender_address | VARCHAR(42) | 发送地址 |
| nonce | BIGINT | 商户发送交易时使用的 nonce |
| signed_raw_tx | TEXT 可空 | 商户注册交易的已签名内容，限制访问 |
| status | VARCHAR(32) | SIGNED、BROADCAST、MINED、CONFIRMED 或 REVERTED |
| block_number | BIGINT 可空 | 所在区块 |
| block_hash | VARCHAR(66) 可空 | 所在区块哈希 |
| error_code | VARCHAR(64) 可空 | 查询、广播或核验原因 |
| created_at | TIMESTAMPTZ | 记录时间 |

一笔失败付款和之后的成功付款分别记录。RPC 暂时不可用只记录最近查询错误，不据此将有效交易标记为 REVERTED。未知或不匹配的哈希不能抢占有效付款关联，也不能把订单锁死。

### 5.3 scan_cursors 扫描游标表

保存 deployment_id、chain_id、contract_address、deployment_block、last_block_number 和 last_block_hash。每个部署一个扫描游标；起始位置位于部署区块之前，以包含部署区块的事件。

阶段 6 的 chain_events 保存区块号、区块哈希、交易哈希、log_index、订单编号与 canonical 标记。物理事件唯一键包含 deployment_id、block_hash、tx_hash 和 log_index；业务层另行约束同一订单只有一笔有效付款。

### 5.4 必要约束和索引

- orders：UNIQUE(deployment_id, chain_order_id)。
- orders：幂等键按调用主体或本地演示范围唯一；同键不同请求内容返回冲突。
- chain_transactions：UNIQUE(chain_id, tx_hash)，哈希提交重复时返回既有结果。
- scan_cursors：UNIQUE(deployment_id)。
- 对待注册订单、待确认交易和到期时间建立查询索引。
- 订单完成时使用条件更新和事务，防止两个处理入口同时入账。

扫描器发现的交易可以补充到现有记录。若交易已经被关联到另一个订单，必须核验事件和调用参数后拒绝错误关联，不能直接覆盖。

## 6 FastAPI 接口约定

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | /api/config | 公开网络、合约地址、部署标识及确认策略 |
| GET | /api/products | 返回商品与展示价格 |
| POST | /api/orders | 创建业务订单，返回注册中状态 |
| GET | /api/orders/{order_id} | 查询订单、付款记录与确认进度 |
| POST | /api/orders/{order_id}/transactions | 提交付款哈希作为待核验线索 |
| POST | /api/orders/{order_id}/verify | 执行一次有限时长的核验，供基础阶段使用 |
| GET | /health | 检查 API、数据库与 RPC 状态 |

创建订单返回 202 与订单资源地址，后台尚未完成注册时使用 REGISTERING。verify 接口不会无限等待出块；暂无收据时返回待处理结果。阶段 5 后由 Worker 自动核验，前端主要查询 GET 接口，保留限频的手动刷新入口即可。

创建请求示例：

```json
{
  "product_id": "lesson17",
  "payer_address": "0x1111111111111111111111111111111111111111"
}
```

订单响应示例，地址和编号为格式占位值：

```json
{
  "order_id": "123e4567-e89b-42d3-a456-426614174000",
  "chain_order_id": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "amount_wei": "10000000000000000",
  "payer_address": "0x1111111111111111111111111111111111111111",
  "chain_id": 31337,
  "contract_address": "0x2222222222222222222222222222222222222222",
  "status": "PENDING_PAYMENT",
  "payment_tx_hash": null,
  "confirmations": 0,
  "required_confirmations": 1,
  "expires_at": "2026-10-24T12:30:00Z"
}
```

基础阶段接口只用于本地演示；接入公共环境时增加身份认证、订单归属校验、请求限频和明确的错误码。连接钱包得到一个地址不等于已通过服务端身份认证。

## 7 支付验证和状态流转

### 7.1 订单状态

```text
REGISTERING → PENDING_PAYMENT → CONFIRMING → PAID
                   │
                   └→ EXPIRED
```

REGISTERING 的错误使用独立注册处理状态和错误信息表示，可重试，不自动变成支付失败。CONFIRMING 表示已经找到匹配且执行成功的付款，仍在等待确认条件。

EXPIRED 只阻止新的业务支付尝试，不阻止对历史有效付款的对账。实际支付区块时间早于 expiresAt 且交易有效时，即使扫描发生得较晚，也应恢复到 CONFIRMING 或 PAID。

重组使付款失效时，撤回受影响的有效付款记录；未到期订单恢复 PENDING_PAYMENT，到期订单重新对账后进入 EXPIRED。若同一订单已有新的规范链有效付款，直接按新证据更新。

### 7.2 单笔核验顺序

1. 使用后端配置的可信 RPC，核对 chain_id 与目标部署。
2. 查询交易和收据；暂无收据时保持待查询，收据 status 为 0 时记录交易回滚。
3. 核对交易 to 是本项目合约，from 是绑定付款钱包。
4. 解码交易 input，确认调用 pay 且 chain_order_id 相同。
5. 核对 transaction.value、数据库 amount_wei 和注册金额完全一致。
6. 从该收据中筛选本合约发出的 OrderPaid，核对订单、付款人与金额。
7. 查询对应区块的合约状态，核对 paid 及注册字段；节点不支持历史状态读取时明确报错或调整节点能力。
8. 根据 block_number 查询规范链区块，核对 block_hash 并计算确认数。
9. 达到策略后，在数据库事务中幂等地完成订单。

web3.py 的收据和日志接口可提供上述证据。收据 status 为 1 仅证明交易执行成功，不能单独证明它支付了当前订单。[6]

### 7.3 确认策略

本地约定确认数等于 latest_block_number 减 receipt_block_number 再加 1，本地 required_confirmations 为 1。需要演示多次确认时，使用按时间出块的 Anvil 或主动挖块，否则自动挖矿模式下没有新交易时确认数可能不再增长。

公共网络的策略按网络和业务价值单独制定，多次确认不等于协议最终性。Worker 在提交入账前再次检查区块哈希；持续回看近期区块，发现断链时定位共同祖先并重新处理。

## 8 React 页面和交互

| 页面或组件 | 展示内容 | 关键行为 |
| --- | --- | --- |
| 商品页 ProductPage | 商品、价格、网络、钱包地址 | 连接钱包并创建订单 |
| 订单页 OrderPage | 编号、金额、状态、到期时间 | 查询注册进度和发起支付 |
| WalletConnect | 当前地址和网络 | 处理连接、账户切换与网络变化 |
| PaymentStatus | 哈希、确认数与结果 | 轮询后端状态并提供重试入口 |

钱包未安装、网络不匹配、当前钱包不是付款人、订单注册中、已支付和已过期时，支付按钮分别给出对应状态。钱包签名弹窗被取消不记成链上失败，也不把订单关闭。

等待阶段禁用重复点击只用于改善交互，不能代替合约防重复和数据库幂等。API 返回的 PAID 才用于展示业务成功；钱包提示发送成功或前端获得交易哈希时，显示已提交或确认中。

开发时 Vite 将 /api 代理到 FastAPI，减少跨域配置。部署时使用统一域名反向代理，前端不保存商户私钥，也不暴露包含秘密凭证的 RPC 配置。

## 9 工程目录和运行约定

```text
web3-payment/
├── contracts/
│   └── Payment.sol
├── script/
│   └── Deploy.s.sol
├── test/
│   └── Payment.t.sol
├── foundry.toml
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── api/
│   │   │   ├── config.py
│   │   │   ├── products.py
│   │   │   └── orders.py
│   │   ├── services/
│   │   │   ├── orders.py
│   │   │   ├── blockchain.py
│   │   │   └── verification.py
│   │   ├── jobs/
│   │   │   └── register_orders.py
│   │   └── worker.py
│   ├── alembic/
│   ├── abi/Payment.json
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── hooks/useWallet.js
│   │   ├── services/api.js
│   │   ├── services/payment.js
│   │   ├── abi/Payment.json
│   │   └── App.jsx
│   ├── package.json
│   └── vite.config.js
├── scripts/
│   └── export_abi.py
├── compose.yaml
├── .gitignore
└── README.md
```

foundry.toml 设置 src 为 contracts。ABI 从 Foundry 的编译产物统一导出给前后端，不手工维护两份不同版本。依赖在实际初始化时选择兼容版本并锁定，Node 使用锁文件，Python 同样保存可复现的依赖锁定结果。

环境配置示例：

```dotenv
DATABASE_URL=postgresql+psycopg://web3_app:change_me@127.0.0.1:5432/web3_payment
RPC_URL=http://127.0.0.1:8545
CHAIN_ID=31337
CONTRACT_ADDRESS=<部署后填写>
DEPLOYMENT_ID=<本次部署的UUID>
DEPLOYMENT_BLOCK=<部署区块高度>
MERCHANT_PRIVATE_KEY=<仅用于本地开发的商户测试私钥>
REQUIRED_CONFIRMATIONS=1
ORDER_TTL_SECONDS=1800
SCAN_BATCH_SIZE=100
WORKER_POLL_SECONDS=3
```

推荐运行顺序：数据库与 Anvil、合约部署、ABI 导出与配置、Alembic 迁移、FastAPI、单次注册任务或 Worker、React。服务启动时检查目标地址有代码，并校验数据库记录的部署信息与当前链一致。

以下为项目实现后应提供的入口约定，当前方案文件不包含这些应用源码：

```bash
# 仓库根目录
docker compose up -d postgres
forge test

# backend 目录
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
python -m app.jobs.register_orders --once
python -m app.worker
pytest

# frontend 目录
npm ci
npm run dev
npm run build
```

Anvil 重置后，即使 chain_id 和合约地址再次相同，也可能是新的一条开发链。基础阶段重置链时使用新的数据库或清理对应部署的测试数据；需要保留数据时持久化 Anvil 状态。deployment_id 用于隔离部署，但仅靠一个本地 UUID 不能证明链未重置，还应核对部署交易、区块哈希与合约代码。

## 10 测试矩阵和最终验收

| 场景 | 预期结果 | 阶段 |
| --- | --- | --- |
| 正确钱包支付准确金额 | 合约支付成功并发出匹配事件 | 1 |
| 少付、多付、未注册、过期或重复付款 | 合约拒绝 | 1 |
| 非商户注册或提现 | 合约拒绝 | 1 |
| 普通转账或其他订单哈希 | 不完成当前订单 | 2 |
| 前端修改价格或传入小数 Wei | 后端拒绝或使用服务端定价 | 3 |
| API 重启 | 订单数据仍可读取 | 3 |
| 切错网络或钱包拒签 | 页面可恢复，订单不误记付款 | 4 |
| 用户付款后关闭网页且未上报哈希 | 扫描器最终找到并确认付款 | 5 |
| Worker 中断后重启 | 从持久化记录恢复处理 | 5 |
| 相同幂等键提交多次 | 复用同一订单；不同内容返回冲突 | 6 |
| 相同事件与哈希多次处理 | 同一订单只有一次有效入账 | 6 |
| 注册广播后尚未记录结果即崩溃 | 查询既有交易和链上订单后恢复 | 6 |
| RPC 暂时超时 | 保持待处理并重试，不误记失败 | 6 |
| 支付区块被重组移除 | 失效付款被撤回并重新对账 | 6 |
| 到期前支付而到期后才扫描 | 有效付款仍可入账 | 6 |
| 另一钱包访问受保护订单 | 服务端拒绝越权访问 | 7 |

数据库集成测试使用独立 PostgreSQL 测试数据库，合约集成测试使用可重置 Anvil。不要用 SQLite 代替数据库约束与并发测试；核心支付验证也要有真实收据和事件的集成用例，不能只模拟返回 paid=true。

第十七课基础验收以阶段 4 为界：网页能完成下单和支付，后端能说明付款有效的依据。完整项目验收以阶段 6 为界：关闭页面不漏单、重启可以恢复、重复处理不会重复入账，并能处理到期和重组。阶段 7 作为第十八课的扩展练习。

## 11 实施检查清单

- [ ] 工具、RPC 和 PostgreSQL 连通。
- [ ] 合约注册、支付、提现及失败路径测试通过。
- [ ] Python 能独立完成付款验证并输出原因。
- [ ] Alembic 可在空 PostgreSQL 数据库建立表结构。
- [ ] FastAPI 创建订单、提交哈希和查询状态可用。
- [ ] React 能连接钱包并完成付款演示。
- [ ] 关闭网页后 Worker 仍能发现付款。
- [ ] 重启、重复请求、广播不确定和 RPC 超时可恢复。
- [ ] 重组和到期对账测试完成。
- [ ] README 记录启动顺序、测试命令和本地链重置方法。

## 12 官方参考资料

以下资料用于核对接口能力和基础行为；项目架构、阶段安排与验收标准为本方案的设计。

1. [FastAPI 并发与同步接口](https://fastapi.tiangolo.com/async/)
2. [SQLAlchemy PostgreSQL 与 psycopg 方言](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
3. [web3.py 交易与链上查询](https://web3py.readthedocs.io/en/stable/web3.eth.html)
4. [ethers.js v6 入门与钱包交互](https://docs.ethers.org/v6/getting-started/)
5. [PostgreSQL 精确数值类型](https://www.postgresql.org/docs/current/datatype-numeric.html)
6. [web3.py 交易收据接口](https://web3py.readthedocs.io/en/stable/web3.eth.html#web3.eth.Eth.get_transaction_receipt)
7. [Anvil 配置与默认参数源码文档](https://foundry-rs.github.io/foundry/anvil/config/index.html)
