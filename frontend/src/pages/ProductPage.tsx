import { formatEther } from 'ethers'
import { useEffect, useRef, useState } from 'react'
import { createOrder, getProducts } from '../services/api'
import type { Product } from '../types'

interface Props {
  onOrderCreated: (orderId: string) => void
}

export function ProductPage({ onOrderCreated }: Props) {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState<string | null>(null)
  // 尚未成功的购买尝试所用的幂等键；请求失败后重试时复用，成功后丢弃
  const pendingKeys = useRef<Record<string, string>>({})

  useEffect(() => {
    getProducts().then(setProducts).catch((e: Error) => setError(e.message))
  }, [])

  async function buy(productId: string) {
    setError(null)
    setCreating(productId)
    const key = (pendingKeys.current[productId] ??= crypto.randomUUID())
    try {
      const order = await createOrder(productId, key)
      delete pendingKeys.current[productId]
      onOrderCreated(order.order_id)
    } catch (e) {
      // 请求可能已在后端成功、只是响应丢失；保留键，重试时拿回同一个订单
      setError(`${(e as Error).message}，可以重试`)
    } finally {
      setCreating(null)
    }
  }

  return (
    <section>
      <h2>商品</h2>
      {error && <p className="error">{error}</p>}
      {products.map((p) => (
        <div key={p.product_id} className="card">
          <div>
            <div className="title">{p.name}</div>
            {/* 价格仅用于展示，实际金额以创建订单时后端返回的为准 */}
            <div>{formatEther(BigInt(p.price_wei))} ETH</div>
          </div>
          <button onClick={() => buy(p.product_id)} disabled={creating !== null}>
            {creating === p.product_id ? '正在创建订单...' : '购买'}
          </button>
        </div>
      ))}
    </section>
  )
}
