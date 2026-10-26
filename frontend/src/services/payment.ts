// 调用支付合约，以及把钱包和合约的错误转换成用户能看懂的提示
import { BrowserProvider, Contract, Interface, isError, type ContractTransactionResponse } from 'ethers'
import abi from '../abi/Payment.json'

const paymentInterface = new Interface(abi)

/** 请求钱包签名并发送 pay 交易；返回时交易已发出，但尚未被打包 */
export async function sendPayment(
  contractAddress: string,
  chainOrderId: string,
  amountWei: string,
): Promise<ContractTransactionResponse> {
  if (!window.ethereum) throw new Error('未检测到钱包')
  // 每次付款重新创建 provider：用户切换网络后，旧的 provider 会失效
  const provider = new BrowserProvider(window.ethereum)
  const signer = await provider.getSigner()
  const contract = new Contract(contractAddress, paymentInterface, signer)
  // 金额从字符串直接转 BigInt，不经过 Number，避免精度丢失
  return contract.pay(chainOrderId, { value: BigInt(amountWei) })
}

export function explainError(err: unknown): string {
  if (isError(err, 'ACTION_REJECTED')) return '你在钱包中取消了签名，可以重新付款'
  if (isError(err, 'INSUFFICIENT_FUNDS')) return '钱包余额不足以支付商品金额和 Gas 费'
  if (isError(err, 'CALL_EXCEPTION')) {
    // 合约自定义错误：返回数据的前 4 字节是错误选择器，用 ABI 解析出名称
    if (err.data) {
      const parsed = paymentInterface.parseError(err.data)
      if (parsed) return `合约拒绝了交易：${parsed.name}`
    }
    return '交易执行失败，已回滚，可以重新付款'
  }
  return err instanceof Error ? err.message : String(err)
}
