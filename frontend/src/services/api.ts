// 后端 API 客户端；开发时 Vite 把 /api 代理到 FastAPI
import type { Order, Product, PublicConfig } from '../types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // 响应不是 JSON 时保留状态文本
    }
    throw new Error(`请求失败（${res.status}）：${detail}`)
  }
  return res.json() as Promise<T>
}

export const getConfig = () => request<PublicConfig>('/config')

export const getProducts = () => request<Product[]>('/products')

// 幂等键：同一次购买的重试必须带同一个键，后端会返回第一次创建的订单
export const createOrder = (productId: string, idempotencyKey: string) =>
  request<Order>('/orders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ product_id: productId }),
  })

export const getOrder = (orderId: string) => request<Order>(`/orders/${orderId}`)

// 只是把交易哈希交给后端记录，订单状态仍由后台扫描器确认
export const submitTxHash = (orderId: string, txHash: string) =>
  request<Order>(`/orders/${orderId}/tx-hash`, { method: 'POST', body: JSON.stringify({ tx_hash: txHash }) })
