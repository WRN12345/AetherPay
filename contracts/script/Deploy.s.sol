// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {Payment} from "../src/Payment.sol";

/// @notice 部署 Payment 合约，并把部署者设为合约所有者
/// @dev 运行前需设置环境变量 OWNER_PK（部署者私钥）
contract Deploy is Script {
    function run() external returns (Payment payment) {
        // 从环境变量读取私钥，并推导出对应地址
        uint256 ownerKey = vm.envUint("OWNER_PK");
        address owner = vm.addr(ownerKey);

        // startBroadcast 与 stopBroadcast 之间的调用会被签名并作为真实交易发送到链上
        vm.startBroadcast(ownerKey);
        payment = new Payment(owner);
        vm.stopBroadcast();

        console.log("Payment deployed at:", address(payment));
        console.log("Owner:", owner);
    }
}
