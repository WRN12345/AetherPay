import type { Auth } from '../hooks/useAuth'
import type { Wallet } from '../hooks/useWallet'

const shorten = (address: string) => `${address.slice(0, 6)}...${address.slice(-4)}`

interface Props {
  auth: Auth
  wallet: Wallet
}

export function AuthStatus({ auth, wallet }: Props) {
  if (auth.checking) return null

  if (!auth.address) {
    if (!wallet.account) return null
    return (
      <div className="wallet">
        <button onClick={auth.signIn} disabled={auth.signingIn}>
          {auth.signingIn ? '等待钱包签名...' : '签名登录'}
        </button>
        {auth.error && <span className="error">{auth.error}</span>}
      </div>
    )
  }

  // 登录后用户可能在钱包里切换了账户：订单仍属于登录账户，提示用户注意
  const switched = wallet.account !== null && wallet.account.toLowerCase() !== auth.address

  return (
    <div className="wallet">
      <span>
        已登录 <code>{shorten(auth.address)}</code>
      </span>
      <button onClick={auth.signOut}>退出</button>
      {switched && <span className="warn">钱包当前账户与登录账户不同，如需切换请退出后重新登录</span>}
    </div>
  )
}
