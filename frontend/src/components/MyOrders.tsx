import { formatEther } from 'ethers'
import { useEffect, useState } from 'react'
import { listOrders } from '../services/api'
import type { Order, OrderStatus } from '../types'

const STATUS_TEXT: Record<OrderStatus, string> = {
  PENDING_PAYMENT: '待付款',
  PAID: '已支付',
  EXPIRED: '已过期',
}

interface Props {
  onOpen: (orderId: string) => void
}

export function MyOrders({ onOpen }: Props) {
  const [orders, setOrders] = useState<Order[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listOrders()
      .then(setOrders)
      .catch((e: Error) => setError(e.message))
  }, [])

  if (error) return <p className="error">{error}</p>
  if (!orders) return null

  return (
    <section>
      <h2>我的订单</h2>
      {orders.length === 0 && <p className="muted">还没有订单</p>}
      {orders.map((o) => (
        <div key={o.order_id} className="card">
          <div>
            <div className="title">{STATUS_TEXT[o.status]}</div>
            <div className="muted">
              {formatEther(BigInt(o.amount_wei))} ETH · {new Date(o.expires_at).toLocaleString()} 到期
            </div>
          </div>
          <button onClick={() => onOpen(o.order_id)}>查看</button>
        </div>
      ))}
    </section>
  )
}
