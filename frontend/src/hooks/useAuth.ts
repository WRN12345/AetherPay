// 钱包签名登录：向后端取登录消息 → 钱包签名 → 后端验证后下发会话 Cookie
import { BrowserProvider, isError } from 'ethers'
import { useCallback, useEffect, useState } from 'react'
import { ApiError, createChallenge, getMe, login, logout } from '../services/api'

export interface Auth {
  /** 已登录的钱包地址（小写）；未登录为 null */
  address: string | null
  checking: boolean
  signingIn: boolean
  error: string | null
  signIn: () => Promise<void>
  signOut: () => Promise<void>
}

export function useAuth(): Auth {
  const [address, setAddress] = useState<string | null>(null)
  const [checking, setChecking] = useState(true)
  const [signingIn, setSigningIn] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // 页面加载时查询会话：Cookie 有效则无需重新签名
  useEffect(() => {
    getMe()
      .then((me) => setAddress(me.address))
      .catch(() => setAddress(null))
      .finally(() => setChecking(false))
  }, [])

  const signIn = useCallback(async () => {
    if (!window.ethereum) return
    setError(null)
    setSigningIn(true)
    try {
      const provider = new BrowserProvider(window.ethereum)
      const signer = await provider.getSigner()
      const { chainId } = await provider.getNetwork()
      const challenge = await createChallenge(signer.address, Number(chainId))
      // personal_sign：只签名一段文字，不发交易，不花 Gas
      const signature = await signer.signMessage(challenge.message)
      const me = await login(challenge.nonce, signature)
      setAddress(me.address)
    } catch (err) {
      if (isError(err, 'ACTION_REJECTED')) setError('你取消了签名')
      else if (err instanceof ApiError) setError(err.message)
      else setError('登录失败')
    } finally {
      setSigningIn(false)
    }
  }, [])

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined)
    setAddress(null)
  }, [])

  return { address, checking, signingIn, error, signIn, signOut }
}
