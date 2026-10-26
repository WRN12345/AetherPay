// 与后端 app/schemas/order.py 对应；Wei 金额一律为字符串，使用时转为 BigInt

export interface PublicConfig {
  chain_id: number
  contract_address: string
  required_confirmations: number
}

export interface Product {
  product_id: string
  name: string
  price_wei: string
}

export type OrderStatus = 'PENDING_PAYMENT' | 'PAID' | 'EXPIRED'

export interface Order {
  order_id: string
  product_id: string
  chain_order_id: string
  amount_wei: string
  chain_id: number
  contract_address: string
  status: OrderStatus
  submitted_tx_hash: string | null
  paid_tx_hash: string | null
  paid_by_address: string | null
  paid_at: string | null
  expires_at: string
}
