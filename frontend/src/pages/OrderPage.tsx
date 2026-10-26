import { formatEther } from 'ethers'
import { useEffect, useState } from 'react'
import { PaymentStatus, type PayStep } from '../components/PaymentStatus'
import type { Wallet } from '../hooks/useWallet'
import { ApiError, getOrder, submitTxHash } from '../services/api'
import { explainError, sendPayment } from '../services/payment'
import type { Order } from '../types'

const POLL_MS = 2000

interface Props {
  orderId: string
  wallet: Wallet
  onBack: () => void
}

export function OrderPage({ orderId, wallet, onBack }: Props) {
  const [order, setOrder] = useState<Order | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [step, setStep] = useState<PayStep>('idle')
  const [txHash, setTxHash] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  // 当前时间每秒更新一次，用于判断到期和显示剩余时间
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  // 轮询订单状态，直到后端确认支付或订单过期；刷新页面后也能从这里恢复
  useEffect(() => {
    let cancelled = false
    let timer: ReturnType<typeof setTimeout>

    async function load() {
      try {
        const o = await getOrder(orderId)
        if (cancelled) return
        setOrder(o)
        setLoadError(null)
        if (o.status === 'PENDING_PAYMENT') timer = setTimeout(load, POLL_MS)
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 404) {
          // 订单不存在，或属于其他账户（后端对两者返回相同结果），不再重试
          setLoadError('订单不存在，或不属于当前登录账户')
          return
        }
        if (e instanceof ApiError && e.status === 401) {
          setLoadError('登录已过期，请重新签名登录')
          return
        }
        // 网络或服务暂时不可用：稍后重试
        setLoadError((e as Error).message)
        timer = setTimeout(load, POLL_MS * 3)
      }
    }

    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [orderId])

  if (!order) {
    return <section>{loadError ? <p className="error">{loadError}</p> : <p>加载订单...</p>}</section>
  }

  const remainingSeconds = Math.max(0, Math.floor((new Date(order.expires_at).getTime() - now) / 1000))
  const expired = order.status === 'EXPIRED' || remainingSeconds === 0
  const busy = step === 'signing' || step === 'submitted' || step === 'mined'

  // 支付按钮不可用时给出原因
  let blocker: string | null = null
  if (order.status === 'PAID') blocker = '订单已支付'
  else if (expired) blocker = '订单已过期，请重新下单'
  else if (!wallet.hasWallet) blocker = '请先安装 MetaMask'
  else if (!wallet.account) blocker = '请先连接钱包'
  else if (wallet.chainId !== order.chain_id) blocker = `请把钱包切换到链 ID ${order.chain_id} 的网络`
  else if (busy) blocker = '付款处理中'

  async function pay() {
    if (!order) return
    setMessage(null)
    setStep('signing')
    let sent = false
    try {
      const tx = await sendPayment(order.contract_address, order.chain_order_id, order.amount_wei)
      sent = true
      setTxHash(tx.hash)
      setStep('submitted')
      // 只是记录线索，失败也不影响付款本身
      submitTxHash(order.order_id, tx.hash).catch(() => undefined)

      const receipt = await tx.wait()
      if (receipt?.status === 1) {
        setStep('mined')
      } else {
        setStep('failed')
        setMessage('交易执行失败，已回滚，可以重新付款')
      }
    } catch (err) {
      // 签名阶段被取消不算链上失败，回到待付款状态
      setStep(sent ? 'failed' : 'idle')
      setMessage(explainError(err))
    }
  }

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← 返回商品
      </button>
      <h2>订单</h2>
      <dl className="details">
        <dt>订单号</dt>
        <dd>
          <code>{order.order_id}</code>
        </dd>
        <dt>链上订单编号</dt>
        <dd>
          <code>{order.chain_order_id}</code>
        </dd>
        <dt>金额</dt>
        <dd>{formatEther(BigInt(order.amount_wei))} ETH</dd>
        <dt>到期时间</dt>
        <dd>
          {new Date(order.expires_at).toLocaleString()}
          {order.status === 'PENDING_PAYMENT' && !expired && (
            <span className="muted">
              {' '}
              （剩余 {Math.floor(remainingSeconds / 60)} 分 {remainingSeconds % 60} 秒）
            </span>
          )}
        </dd>
      </dl>

      <PaymentStatus order={order} step={step} txHash={txHash} />
      {message && <p className="error">{message}</p>}
      {loadError && <p className="error">{loadError}</p>}

      {order.status === 'PENDING_PAYMENT' && (
        <button className="primary" onClick={pay} disabled={blocker !== null}>
          {blocker ?? `支付 ${formatEther(BigInt(order.amount_wei))} ETH`}
        </button>
      )}
    </section>
  )
}
