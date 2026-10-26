// 钱包状态：当前账户、所在网络，并监听用户在钱包中切换账户或网络
import { useCallback, useEffect, useState } from 'react'

export interface Wallet {
  hasWallet: boolean
  account: string | null
  chainId: number | null
  error: string | null
  connect: () => Promise<void>
  switchChain: (chainId: number) => Promise<void>
}

const firstAccount = (accounts: unknown) => (accounts as string[])[0] ?? null
const parseChainId = (hex: unknown) => parseInt(hex as string, 16)

export function useWallet(): Wallet {
  const ethereum = window.ethereum
  const [account, setAccount] = useState<string | null>(null)
  const [chainId, setChainId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!ethereum) return
    // eth_accounts 只读取已授权的账户，不会弹窗；首次连接用 eth_requestAccounts
    ethereum.request({ method: 'eth_accounts' }).then((a) => setAccount(firstAccount(a)))
    ethereum.request({ method: 'eth_chainId' }).then((id) => setChainId(parseChainId(id)))

    const onAccountsChanged = (a: unknown) => setAccount(firstAccount(a))
    const onChainChanged = (id: unknown) => setChainId(parseChainId(id))
    ethereum.on?.('accountsChanged', onAccountsChanged)
    ethereum.on?.('chainChanged', onChainChanged)
    return () => {
      ethereum.removeListener?.('accountsChanged', onAccountsChanged)
      ethereum.removeListener?.('chainChanged', onChainChanged)
    }
  }, [ethereum])

  const connect = useCallback(async () => {
    if (!ethereum) return
    setError(null)
    try {
      const accounts = await ethereum.request({ method: 'eth_requestAccounts' })
      setAccount(firstAccount(accounts))
    } catch (err) {
      const code = (err as { code?: number }).code
      setError(code === 4001 ? '你拒绝了连接请求' : '连接钱包失败')
    }
  }, [ethereum])

  const switchChain = useCallback(
    async (target: number) => {
      if (!ethereum) return
      setError(null)
      try {
        await ethereum.request({
          method: 'wallet_switchEthereumChain',
          params: [{ chainId: '0x' + target.toString(16) }],
        })
      } catch (err) {
        const code = (err as { code?: number }).code
        // 4902：钱包里没有这个网络
        setError(code === 4902 ? `钱包中没有链 ID 为 ${target} 的网络，请先在 MetaMask 中添加` : '切换网络失败')
      }
    },
    [ethereum],
  )

  return { hasWallet: Boolean(ethereum), account, chainId, error, connect, switchChain }
}
