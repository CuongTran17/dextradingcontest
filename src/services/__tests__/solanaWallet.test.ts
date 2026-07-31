import { Connection, PublicKey } from '@solana/web3.js'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  claimCertificateOnchain,
  connectSolanaWallet,
  initializeContestOnchain,
  joinContestOnchain,
  setContestJoinEnabledOnchain,
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

  it('returns the join signature when post-submit confirmation times out', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ data: Buffer.alloc(0) } as never)
    vi.spyOn(Connection.prototype, 'getBalance').mockResolvedValue(1_000_000_000)
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: '11111111111111111111111111111111',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'confirmTransaction').mockRejectedValue(new Error('timeout'))
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
      .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])

    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signAndSendTransaction: async () => ({ signature: '5'.repeat(88) }),
    }

    await expect(
      joinContestOnchain({
        contestId: 'summer-cup',
        walletPublicKey: wallet.toBase58(),
      }),
    ).resolves.toEqual({
      walletAddress: wallet.toBase58(),
      signature: '5'.repeat(88),
    })
  })

  it('syncs an existing on-chain participant without signing a duplicate join transaction', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo')
      .mockResolvedValueOnce({ data: Buffer.alloc(0) } as never)
    vi.spyOn(Connection.prototype, 'getSignaturesForAddress').mockResolvedValue([
      { signature: '4'.repeat(88) },
    ] as never)
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
    ).resolves.toEqual({
      walletAddress: wallet.toBase58(),
      signature: '4'.repeat(88),
    })
    expect(signAndSendTransaction).not.toHaveBeenCalled()
  })

  it('builds and sends the initialize contest instruction', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue(null)
    vi.spyOn(Connection.prototype, 'getBalance').mockResolvedValue(1_000_000_000)
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: '11111111111111111111111111111111',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null },
    })
    vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
      new PublicKey('11111111111111111111111111111111'),
      255,
    ])

    const admin = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    const sentTransactions: unknown[] = []
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: admin }),
      signAndSendTransaction: async (transaction) => {
        sentTransactions.push(transaction)
        return { signature: '5'.repeat(88) }
      },
    }

    await expect(initializeContestOnchain({ contestId: 'summer-cup' })).resolves.toEqual({
      adminWallet: admin.toBase58(),
      contestAddress: '11111111111111111111111111111111',
      signature: '5'.repeat(88),
    })

    const transaction = sentTransactions[0] as {
      instructions: Array<{ data: Buffer; programId: PublicKey }>
    }
    const instruction = transaction.instructions[0]
    const instructionData = Buffer.from(instruction.data)
    expect(instruction.programId.toBase58()).toBe('9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    expect([...instructionData.subarray(0, 8)]).toEqual([8, 124, 233, 229, 42, 156, 92, 3])
    expect(instructionData.includes(Buffer.from('summer-cup'))).toBe(true)
  })

  it('does not initialize a contest that already has an on-chain account', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue({
      data: Buffer.alloc(0),
    } as never)
    vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
      new PublicKey('11111111111111111111111111111111'),
      255,
    ])
    const signAndSendTransaction = vi.fn()
    window.solana = {
      isPhantom: true,
      connect: async () => ({
        publicKey: new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB'),
      }),
      signAndSendTransaction,
    }

    await expect(initializeContestOnchain({ contestId: 'summer-cup' })).rejects.toThrow(
      'Contest summer-cup is already initialized on Solana devnet',
    )
    expect(signAndSendTransaction).not.toHaveBeenCalled()
  })

  it('builds and sends the admin set join enabled instruction', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getAccountInfo').mockResolvedValue({
      data: Buffer.alloc(0),
    } as never)
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: '11111111111111111111111111111111',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null },
    })
    vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
      new PublicKey('11111111111111111111111111111111'),
      255,
    ])

    const admin = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    const sentTransactions: unknown[] = []
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: admin }),
      signAndSendTransaction: async (transaction) => {
        sentTransactions.push(transaction)
        return { signature: '5'.repeat(88) }
      },
    }

    await expect(
      setContestJoinEnabledOnchain({
        contestId: 'summer-cup',
        enabled: false,
        expectedAdminWallet: admin.toBase58(),
      }),
    ).resolves.toEqual({
      adminWallet: admin.toBase58(),
      contestAddress: '11111111111111111111111111111111',
      signature: '5'.repeat(88),
    })

    const transaction = sentTransactions[0] as {
      instructions: Array<{
        data: Buffer
        programId: PublicKey
        keys: Array<{ pubkey: PublicKey; isSigner: boolean; isWritable: boolean }>
      }>
    }
    const instruction = transaction.instructions[0]
    const instructionData = Buffer.from(instruction.data)
    expect(instruction.programId.toBase58()).toBe('9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    expect([...instructionData.subarray(0, 8)]).toEqual([130, 14, 52, 92, 87, 2, 180, 137])
    expect([...instructionData.subarray(8, 9)]).toEqual([0])
    expect(instruction.keys).toEqual([
      { pubkey: new PublicKey('11111111111111111111111111111111'), isSigner: false, isWritable: true },
      { pubkey: admin, isSigner: true, isWritable: false },
    ])
  })

  it('does not sign set join enabled when connected wallet is not the contest admin wallet', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(PublicKey, 'findProgramAddressSync').mockReturnValueOnce([
      new PublicKey('11111111111111111111111111111111'),
      255,
    ])
    const signAndSendTransaction = vi.fn()
    window.solana = {
      isPhantom: true,
      connect: async () => ({
        publicKey: new PublicKey('So11111111111111111111111111111111111111112'),
      }),
      signAndSendTransaction,
    }

    await expect(
      setContestJoinEnabledOnchain({
        contestId: 'summer-cup',
        enabled: false,
        expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      }),
    ).rejects.toThrow('Connected wallet is not the admin wallet that initialized this contest')
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
