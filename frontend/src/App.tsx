import { useEffect, useState } from 'react'
import { WalletConnect } from './components/WalletConnect'
import { useWallet } from './hooks/useWallet'
import { OrderPage } from './pages/OrderPage'
import { ProductPage } from './pages/ProductPage'
import { getConfig } from './services/api'
import type { PublicConfig } from './types'

// 订单号保存在 URL 中（?order=...），刷新页面后可以恢复
const readOrderId = () => new URLSearchParams(window.location.search).get('order')

function App() {
  const wallet = useWallet()
  const [config, setConfig] = useState<PublicConfig | null>(null)
  const [configError, setConfigError] = useState<string | null>(null)
  const [orderId, setOrderId] = useState<string | null>(readOrderId)

  useEffect(() => {
    getConfig().then(setConfig).catch((e: Error) => setConfigError(e.message))
  }, [])

  useEffect(() => {
    const onPopState = () => setOrderId(readOrderId())
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  function navigate(id: string | null) {
    window.history.pushState(null, '', id ? `?order=${id}` : window.location.pathname)
    setOrderId(id)
  }

  return (
    <main>
      <header>
        <h1>web3 课程资料</h1>
        <WalletConnect wallet={wallet} expectedChainId={config?.chain_id ?? null} />
      </header>
      {configError && <p className="error">无法连接后端：{configError}</p>}
      {orderId ? (
        <OrderPage key={orderId} orderId={orderId} wallet={wallet} onBack={() => navigate(null)} />
      ) : (
        <ProductPage onOrderCreated={navigate} />
      )}
    </main>
  )
}

export default App
