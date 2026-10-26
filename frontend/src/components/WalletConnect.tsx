import type { Wallet } from '../hooks/useWallet'

const shorten = (address: string) => `${address.slice(0, 6)}...${address.slice(-4)}`

interface Props {
  wallet: Wallet
  expectedChainId: number | null
}

export function WalletConnect({ wallet, expectedChainId }: Props) {
  if (!wallet.hasWallet) {
    return <div className="wallet warn">未检测到钱包，请先安装 MetaMask 浏览器扩展</div>
  }

  const wrongChain = expectedChainId !== null && wallet.chainId !== null && wallet.chainId !== expectedChainId

  return (
    <div className="wallet">
      {wallet.account ? (
        <span>
          钱包 <code>{shorten(wallet.account)}</code>
        </span>
      ) : (
        <button onClick={wallet.connect}>连接钱包</button>
      )}
      {wallet.chainId !== null && (
        <span className={wrongChain ? 'warn' : undefined}>
          网络 {wallet.chainId}
          {wrongChain && (
            <>
              ，需要 {expectedChainId}{' '}
              <button onClick={() => wallet.switchChain(expectedChainId)}>切换网络</button>
            </>
          )}
        </span>
      )}
      {wallet.error && <span className="error">{wallet.error}</span>}
    </div>
  )
}
