// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Ownable：提供 owner（所有者）和 onlyOwner 修饰符，用于限制只有所有者能调用的函数
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
// ReentrancyGuard：提供 nonReentrant 修饰符，防止函数在执行过程中被再次调用（重入攻击）
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title 课程资料支付合约
/// @notice 用户调用 pay 付款并发出 OrderPaid 事件；金额是否正确由后端核对
contract Payment is Ownable, ReentrancyGuard {
    // 自定义错误：比字符串错误更省 Gas，前端可以解析出具体错误名称
    error ZeroAmount();
    error InvalidRecipient();
    error InsufficientBalance();
    error TransferFailed();

    // 事件：写入交易收据的日志，后端扫描它来确认付款
    // indexed 字段进入 topics，可以按订单号或付款人快速过滤
    event OrderPaid(bytes32 indexed orderId, address indexed payer, uint256 amount);
    event Withdrawn(address indexed to, uint256 amount);

    // 部署时指定合约所有者，只有所有者能提现
    constructor(address initialOwner) Ownable(initialOwner) {}

    /// @notice 为订单付款
    /// @param orderId 后端生成的 32 字节订单编号
    /// @dev payable 表示调用时可以附带 ETH；msg.value 是附带的金额（Wei），msg.sender 是调用者
    function pay(bytes32 orderId) external payable {
        if (msg.value == 0) revert ZeroAmount();
        emit OrderPaid(orderId, msg.sender, msg.value);
    }

    /// @notice 所有者把合约内的 ETH 提取到指定地址
    /// @dev nonReentrant 防止收款方在转账回调中再次调用 withdraw，放在第一位使其最先生效；
    ///      onlyOwner 限制调用者。按"检查 → 记录 → 外部调用"的顺序编写，事件在转账前发出
    function withdraw(address payable to, uint256 amount) external nonReentrant onlyOwner {
        if (to == address(0)) revert InvalidRecipient();
        if (amount > address(this).balance) revert InsufficientBalance();
        emit Withdrawn(to, amount);
        (bool ok, ) = to.call{value: amount}("");
        if (!ok) revert TransferFailed();
    }

    // 没有定义 receive 和 fallback：直接向合约地址转账会被拒绝，避免出现对应不上订单的款项
}
