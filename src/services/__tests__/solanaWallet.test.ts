import { PublicKey } from '@solana/web3.js'
import { afterEach, describe, expect, it } from 'vitest'

import { connectSolanaWallet } from '@/services/solanaWallet'

describe('solanaWallet', () => {
  afterEach(() => {
    delete window.solana
  })

  it('connects Phantom and returns the connected wallet address', async () => {
    const publicKey = new PublicKey('So11111111111111111111111111111111111111112')
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey }),
    }

    await expect(connectSolanaWallet()).resolves.toEqual({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
  })

  it('asks the user to install a Solana wallet when no provider exists', async () => {
    await expect(connectSolanaWallet()).rejects.toThrow('Install Phantom or Solflare')
  })
})
