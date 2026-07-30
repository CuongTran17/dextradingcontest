import { Connection, PublicKey } from '@solana/web3.js'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  claimCertificateOnchain,
  connectSolanaWallet,
  joinContestOnchain,
} from '@/services/solanaWallet'

describe('solanaWallet', () => {
  afterEach(() => {
    delete window.solana
    vi.unstubAllEnvs()
    vi.restoreAllMocks()
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

  it('explains when the contest has not been initialized on-chain', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue(null)
    vi.spyOn(Connection.prototype, 'getBalance').mockResolvedValue(1_000_000_000)
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
      .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])

    const signAndSendTransaction = vi.fn()
    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signAndSendTransaction,
    }

    await expect(
      joinContestOnchain({
        contestId: 'summer-cup',
        walletPublicKey: wallet.toBase58(),
      }),
    ).rejects.toThrow('Contest summer-cup is not initialized on Solana devnet')
    expect(signAndSendTransaction).not.toHaveBeenCalled()
  })

  it('rejects certificate claim when snapshot hash is not 32 bytes', async () => {
    await expect(
      claimCertificateOnchain({
        contestId: 'practice-arena',
        walletPublicKey: 'So11111111111111111111111111111111111111112',
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa',
        proof: [],
      }),
    ).rejects.toThrow('Snapshot hash must be 32 bytes')
  })

  it('builds and sends the claim certificate instruction', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: '11111111111111111111111111111111',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null },
    })
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
      .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])

    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    const sentTransactions: unknown[] = []
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signAndSendTransaction: async (transaction) => {
        sentTransactions.push(transaction)
        return { signature: '5'.repeat(88) }
      },
    }

    await expect(
      claimCertificateOnchain({
        contestId: 'practice-arena',
        walletPublicKey: wallet.toBase58(),
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa'.repeat(32),
        proof: [],
      }),
    ).resolves.toEqual({ signature: '5'.repeat(88) })

    const transaction = sentTransactions[0] as { instructions: Array<{ data: Buffer, programId: PublicKey }> }
    const instruction = transaction.instructions[0]
    const instructionData = Buffer.from(instruction.data)
    expect(instruction.programId.toBase58()).toBe('9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    expect([...instructionData.subarray(0, 8)]).toEqual([45, 124, 106, 139, 156, 89, 153, 233])
    expect(instructionData.includes(Buffer.from('practice-arena'))).toBe(true)
    expect(instructionData.includes(Buffer.from('ipfs://QmMetadata'))).toBe(true)
  })
})
