import { useEffect, useState } from 'react'
import { AuthStatus } from './components/AuthStatus'
import { MyOrders } from './components/MyOrders'
import { WalletConnect } from './components/WalletConnect'
import { useAuth } from './hooks/useAuth'
import { useWallet } from './hooks/useWallet'
import { OrderPage } from './pages/OrderPage'
import { ProductPage } from './pages/ProductPage'
import { getConfig } from './services/api'
import type { PublicConfig } from './types'

// 订单号保存在 URL 中（?order=...），刷新页面后可以恢复
const readOrderId = () => new URLSearchParams(window.location.search).get('order')

function App() {
  const wallet = useWallet()
  const auth = useAuth()
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

  let content
  if (auth.checking) {
    content = <p>加载中...</p>
  } else if (!auth.address) {
    content = (
      <section>
        <p>{wallet.account ? '请点击右上角"签名登录"，签名不会发起交易，也不收取费用。' : '请先连接钱包，再签名登录。'}</p>
      </section>
    )
  } else if (orderId) {
    content = <OrderPage key={orderId} orderId={orderId} wallet={wallet} onBack={() => navigate(null)} />
  } else {
    // key 绑定登录地址：切换账户后重新加载订单列表
    content = (
      <>
        <ProductPage onOrderCreated={navigate} />
        <MyOrders key={auth.address} onOpen={navigate} />
      </>
    )
  }

  return (
    <main>
      <header>
        <h1>web3 课程资料</h1>
        <div className="header-right">
          <WalletConnect wallet={wallet} expectedChainId={config?.chain_id ?? null} />
          <AuthStatus auth={auth} wallet={wallet} />
        </div>
      </header>
      {configError && <p className="error">无法连接后端：{configError}</p>}
      {content}
    </main>
  )
}

export default App
