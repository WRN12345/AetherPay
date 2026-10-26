// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

// Test：forge-std 的测试基类，提供断言函数（assertEq 等）和作弊码对象 vm
import {Test} from "forge-std/Test.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {Payment} from "../src/Payment.sol";

/// @dev 一个拒绝接收 ETH 的合约（没有 receive 函数），用来测试提现转账失败的情况
contract RejectingReceiver {}

/// @notice Payment 合约测试
/// @dev 函数名以 test 开头的会被 forge test 自动执行；testFuzz 开头的会用随机参数执行多次
contract PaymentTest is Test {
    Payment internal payment;

    // makeAddr 根据名字生成一个固定的测试地址，并在报错信息里显示这个名字，便于阅读
    address internal owner = makeAddr("owner");
    address internal user = makeAddr("user");

    bytes32 internal constant ORDER_ID = keccak256("order-1");
    uint256 internal constant PRICE = 0.01 ether;

    /// @dev 每个测试函数执行前都会先运行 setUp，各测试之间互不影响
    function setUp() public {
        payment = new Payment(owner);
        // vm.deal：直接设置某个地址的 ETH 余额
        vm.deal(user, 10 ether);
    }

    // ───────────────────────── pay ─────────────────────────

    function test_Pay_EmitsOrderPaid() public {
        // vm.expectEmit：断言下一次调用会发出与下面 emit 相同的事件
        // 四个布尔值分别表示：是否检查 topic1（orderId）、topic2（payer）、topic3（无）、data（amount）
        // 最后一个参数指定事件必须由 payment 合约发出
        vm.expectEmit(true, true, false, true, address(payment));
        emit Payment.OrderPaid(ORDER_ID, user, PRICE);

        // vm.prank：让下一次调用的 msg.sender 变成 user
        vm.prank(user);
        payment.pay{value: PRICE}(ORDER_ID);

        assertEq(address(payment).balance, PRICE, "contract should hold the payment");
        assertEq(user.balance, 10 ether - PRICE, "user balance should decrease");
    }

    function test_Pay_RevertsOnZeroAmount() public {
        // vm.expectRevert：断言下一次调用会以指定的错误回滚
        vm.expectRevert(Payment.ZeroAmount.selector);
        vm.prank(user);
        payment.pay{value: 0}(ORDER_ID);
    }

    /// @dev 合约不在链上去重，同一订单付款两次都会成功；第二笔由后端记为 DUPLICATE 异常付款
    function test_Pay_SameOrderTwice_BothSucceed() public {
        vm.startPrank(user); // startPrank：之后的所有调用都以 user 身份发出，直到 stopPrank
        payment.pay{value: PRICE}(ORDER_ID);
        payment.pay{value: PRICE}(ORDER_ID);
        vm.stopPrank();

        assertEq(address(payment).balance, 2 * PRICE);
    }

    /// @dev 模糊测试：forge 会生成大量随机 amount 执行本函数，验证任意正数金额都能付款
    function testFuzz_Pay_AnyPositiveAmount(uint96 amount) public {
        // vm.assume：不满足条件的随机输入直接跳过
        vm.assume(amount > 0);
        vm.deal(user, amount);

        vm.prank(user);
        payment.pay{value: amount}(ORDER_ID);

        assertEq(address(payment).balance, amount);
    }

    // ─────────────────────── 直接转账 ───────────────────────

    function test_DirectTransfer_Reverts() public {
        // 不调用任何函数、只附带 ETH，相当于普通转账；合约没有 receive，应当失败
        vm.prank(user);
        (bool ok, ) = address(payment).call{value: PRICE}("");

        assertFalse(ok, "direct transfer should be rejected");
        assertEq(address(payment).balance, 0);
    }

    // ─────────────────────── withdraw ───────────────────────

    /// @dev 辅助函数：先让用户付一笔款，使合约里有余额
    function _payOnce() internal {
        vm.prank(user);
        payment.pay{value: PRICE}(ORDER_ID);
    }

    function test_Withdraw_ByOwner() public {
        _payOnce();

        vm.expectEmit(true, false, false, true, address(payment));
        emit Payment.Withdrawn(owner, PRICE);

        vm.prank(owner);
        payment.withdraw(payable(owner), PRICE);

        assertEq(address(payment).balance, 0, "contract should be empty");
        assertEq(owner.balance, PRICE, "owner should receive the funds");
    }

    function test_Withdraw_RevertsForNonOwner() public {
        _payOnce();

        // 带参数的错误：用 abi.encodeWithSelector 拼出"选择器 + 参数"，与合约实际返回的数据比较
        vm.expectRevert(abi.encodeWithSelector(Ownable.OwnableUnauthorizedAccount.selector, user));
        vm.prank(user);
        payment.withdraw(payable(user), PRICE);
    }

    function test_Withdraw_RevertsWhenAmountExceedsBalance() public {
        _payOnce();

        vm.expectRevert(Payment.InsufficientBalance.selector);
        vm.prank(owner);
        payment.withdraw(payable(owner), PRICE + 1);
    }

    function test_Withdraw_RevertsOnZeroAddress() public {
        _payOnce();

        vm.expectRevert(Payment.InvalidRecipient.selector);
        vm.prank(owner);
        payment.withdraw(payable(address(0)), PRICE);
    }

    function test_Withdraw_RevertsWhenRecipientRejects() public {
        _payOnce();
        RejectingReceiver receiver = new RejectingReceiver();

        // 收款方拒收时整笔交易回滚，资金仍留在合约中
        vm.expectRevert(Payment.TransferFailed.selector);
        vm.prank(owner);
        payment.withdraw(payable(address(receiver)), PRICE);

        assertEq(address(payment).balance, PRICE);
    }
}
