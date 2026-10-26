import type { Order } from '../types'

export type PayStep = 'idle' | 'signing' | 'submitted' | 'mined' | 'failed'

interface Props {
  order: Order
  step: PayStep
  txHash: string | null
}

/** 付款进度：钱包与链上的进度仅作提示，只有后端返回 PAID 才代表业务成功 */
export function PaymentStatus({ order, step, txHash }: Props) {
  let text: string
  if (order.status === 'PAID') text = '支付成功'
  else if (order.status === 'EXPIRED') text = '订单已过期'
  else if (step === 'signing') text = '等待钱包签名'
  else if (step === 'submitted') text = '交易已提交，等待打包'
  else if (step === 'mined') text = '交易已上链，等待后台确认'
  else if (step === 'failed') text = '交易失败，可以重新付款'
  else text = '待付款'

  const hash = order.paid_tx_hash ?? txHash

  return (
    <div className={`status status-${order.status === 'PAID' ? 'paid' : step}`}>
      <strong>{text}</strong>
      {hash && (
        <div>
          交易哈希 <code>{hash}</code>
        </div>
      )}
    </div>
  )
}
