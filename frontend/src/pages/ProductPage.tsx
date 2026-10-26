import { formatEther } from 'ethers'
import { useEffect, useState } from 'react'
import { createOrder, getProducts } from '../services/api'
import type { Product } from '../types'

interface Props {
  onOrderCreated: (orderId: string) => void
}

export function ProductPage({ onOrderCreated }: Props) {
  const [products, setProducts] = useState<Product[]>([])
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState<string | null>(null)

  useEffect(() => {
    getProducts().then(setProducts).catch((e: Error) => setError(e.message))
  }, [])

  async function buy(productId: string) {
    setError(null)
    setCreating(productId)
    try {
      const order = await createOrder(productId)
      onOrderCreated(order.order_id)
    } catch (e) {
      setError((e as Error).message)
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
