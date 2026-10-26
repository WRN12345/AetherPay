// MetaMask 等浏览器钱包注入的 window.ethereum 对象（EIP-1193 接口）
import type { Eip1193Provider } from 'ethers'

interface InjectedProvider extends Eip1193Provider {
  on?(event: string, listener: (...args: unknown[]) => void): void
  removeListener?(event: string, listener: (...args: unknown[]) => void): void
}

declare global {
  interface Window {
    ethereum?: InjectedProvider
  }
}

export {}
