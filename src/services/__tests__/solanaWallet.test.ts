import { Connection, PublicKey, Transaction } from '@solana/web3.js'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  claimCertificateOnchain,
  connectSolanaWallet,
  initializeContestOnchain,
  joinContestOnchain,
  publishCertificateRootOnchain,
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
    const connect = vi.fn(async () => ({ publicKey }))
    window.solana = {
      isPhantom: true,
      connect,
    }

    await expect(connectSolanaWallet()).resolves.toEqual({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
    expect(connect).toHaveBeenCalledWith({ onlyIfTrusted: false })
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

  it('rejects certificate root publish when root is not 32 bytes', async () => {
    await expect(
      publishCertificateRootOnchain({
        contestId: 'summer-cup',
        rootHex: 'bb',
        snapshotHashHex: 'aa'.repeat(32),
        topN: 5,
        batchId: '91',
        expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      }),
    ).rejects.toThrow('Certificate root must be 32 bytes')
  })

  it('builds and sends the publish certificate root instruction', async () => {
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
      publishCertificateRootOnchain({
        contestId: 'summer-cup',
        rootHex: 'bb'.repeat(32),
        snapshotHashHex: 'aa'.repeat(32),
        topN: 5,
        batchId: '91',
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
    expect([...instructionData.subarray(0, 8)]).toEqual([142, 166, 41, 131, 130, 127, 48, 25])
    expect([...instructionData.subarray(8, 40)]).toEqual(Array.from(Buffer.from('bb'.repeat(32), 'hex')))
    expect([...instructionData.subarray(40, 72)]).toEqual(Array.from(Buffer.from('aa'.repeat(32), 'hex')))
    expect(instructionData.readUInt16LE(72)).toBe(5)
    expect(instructionData.includes(Buffer.from('91'))).toBe(true)
    expect(instruction.keys).toEqual([
      { pubkey: new PublicKey('11111111111111111111111111111111'), isSigner: false, isWritable: true },
      { pubkey: admin, isSigner: true, isWritable: false },
    ])
  })

  it('rejects certificate claim when snapshot hash is not 32 bytes', async () => {
    await expect(
      claimCertificateOnchain({
        contestId: 'practice-arena',
        batchId: '91',
        topN: 5,
        walletPublicKey: 'So11111111111111111111111111111111111111112',
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa',
        proof: [],
      }),
    ).rejects.toThrow('Snapshot hash must be 32 bytes')
  })

  it('surfaces certificate claim simulation logs before asking the wallet to send', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: 'EETubP5AKHgjPAhzPAFcb8BAY1hMH639CWCFTqi3hq1k',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'simulateTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: {
        err: { InstructionError: [0, { Custom: 6010 }] },
        logs: [
          'Program 9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx invoke [1]',
          'Program log: AnchorError occurred. Error Code: InvalidMerkleProof. Error Number: 6010. Error Message: Certificate Merkle proof is invalid.',
        ],
      },
    } as never)
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([new PublicKey('11111111111111111111111111111111'), 255])
      .mockReturnValueOnce([new PublicKey('SysvarRent111111111111111111111111111111111'), 254])
      .mockReturnValueOnce([new PublicKey('So11111111111111111111111111111111111111112'), 253])
      .mockReturnValueOnce([new PublicKey('Vote111111111111111111111111111111111111111'), 252])
    vi.spyOn(Transaction.prototype, 'partialSign').mockImplementation(() => undefined)

    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    const signAndSendTransaction = vi.fn(async () => {
      throw new Error('wallet send should not be called after failed preflight')
    })
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signAndSendTransaction,
    }

    await expect(
      claimCertificateOnchain({
        contestId: 'practice-arena',
        batchId: '91',
        topN: 5,
        walletPublicKey: wallet.toBase58(),
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa'.repeat(32),
        proof: [],
      }),
    ).rejects.toThrow('Certificate Merkle proof is invalid')
    expect(signAndSendTransaction).not.toHaveBeenCalled()
  })

  it('surfaces RPC send logs after the wallet signs a certificate claim', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    const contest = new PublicKey('11111111111111111111111111111111')
    const certificate = new PublicKey('SysvarRent111111111111111111111111111111111')
    const tokenAccount = new PublicKey('So11111111111111111111111111111111111111112')
    const metadata = new PublicKey('Vote111111111111111111111111111111111111111')
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: 'EETubP5AKHgjPAhzPAFcb8BAY1hMH639CWCFTqi3hq1k',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'simulateTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null, logs: [] },
    } as never)
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([contest, 255])
      .mockReturnValueOnce([certificate, 254])
      .mockReturnValueOnce([tokenAccount, 253])
      .mockReturnValueOnce([metadata, 252])
    vi.spyOn(Transaction.prototype, 'partialSign').mockImplementation(() => undefined)
    vi.spyOn(Transaction.prototype, 'serialize').mockReturnValue(Buffer.from([1, 2, 3]))
    vi.spyOn(Connection.prototype, 'sendRawTransaction').mockRejectedValue(
      Object.assign(new Error('Unexpected error'), {
        data: {
          logs: [
            'Program log: AnchorError occurred. Error Code: CertificateBatchMismatch. Error Number: 6006. Error Message: Certificate batch id does not match.',
          ],
        },
      }),
    )

    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signTransaction: async (transaction) => transaction,
    }

    await expect(
      claimCertificateOnchain({
        contestId: 'practice-arena',
        batchId: '91',
        topN: 5,
        walletPublicKey: wallet.toBase58(),
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa'.repeat(32),
        proof: [],
      }),
    ).rejects.toThrow('Certificate batch id does not match')
  })

  it('builds and sends the claim certificate instruction', async () => {
    vi.stubEnv('VITE_SOLANA_CONTEST_PROGRAM_ID', '9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx')
    const contest = new PublicKey('11111111111111111111111111111111')
    const certificate = new PublicKey('SysvarRent111111111111111111111111111111111')
    const tokenAccount = new PublicKey('So11111111111111111111111111111111111111112')
    const metadata = new PublicKey('Vote111111111111111111111111111111111111111')
    vi.spyOn(Connection.prototype, 'getLatestBlockhash').mockResolvedValue({
      blockhash: 'EETubP5AKHgjPAhzPAFcb8BAY1hMH639CWCFTqi3hq1k',
      lastValidBlockHeight: 1,
    })
    vi.spyOn(Connection.prototype, 'confirmTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null },
    })
    vi.spyOn(Connection.prototype, 'simulateTransaction').mockResolvedValue({
      context: { slot: 1 },
      value: { err: null, logs: [] },
    } as never)
    vi.spyOn(Connection.prototype, 'sendRawTransaction').mockResolvedValue('5'.repeat(88))
    const partialSign = vi
      .spyOn(Transaction.prototype, 'partialSign')
      .mockImplementation(() => undefined)
    vi.spyOn(Transaction.prototype, 'serialize').mockReturnValue(Buffer.from([1, 2, 3]))
    vi.spyOn(PublicKey, 'findProgramAddressSync')
      .mockReturnValueOnce([contest, 255])
      .mockReturnValueOnce([certificate, 254])
      .mockReturnValueOnce([tokenAccount, 253])
      .mockReturnValueOnce([metadata, 252])

    const wallet = new PublicKey('ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB')
    const sentTransactions: unknown[] = []
    const signAndSendTransaction = vi.fn(async () => ({ signature: 'should-not-be-used' }))
    window.solana = {
      isPhantom: true,
      connect: async () => ({ publicKey: wallet }),
      signTransaction: async (transaction) => {
        sentTransactions.push(transaction)
        return transaction
      },
      signAndSendTransaction,
    }

    const result = await claimCertificateOnchain({
      contestId: 'practice-arena',
      batchId: '91',
      topN: 5,
      walletPublicKey: wallet.toBase58(),
      rank: 1,
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
    })
    expect(result.signature).toBe('5'.repeat(88))
    expect(result.mintAddress).toMatch(/^[1-9A-HJ-NP-Za-km-z]{32,44}$/)
    expect(partialSign).toHaveBeenCalledOnce()
    expect(signAndSendTransaction).not.toHaveBeenCalled()
    expect(Connection.prototype.sendRawTransaction).toHaveBeenCalledWith(Buffer.from([1, 2, 3]))

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
    expect(instruction.keys[2].pubkey.toBase58()).toBe(result.mintAddress)
    expect([...instructionData.subarray(0, 8)]).toEqual([45, 124, 106, 139, 156, 89, 153, 233])
    expect(instructionData.includes(Buffer.from('practice-arena'))).toBe(true)
    expect(instructionData.includes(Buffer.from('91'))).toBe(true)
    expect(instructionData.includes(Buffer.from([5, 0]))).toBe(true)
    expect(instructionData.includes(Buffer.from('ipfs://QmMetadata'))).toBe(true)
    expect(instruction.keys[0]).toEqual({ pubkey: contest, isSigner: false, isWritable: false })
    expect(instruction.keys[1]).toEqual({ pubkey: certificate, isSigner: false, isWritable: true })
    expect(instruction.keys[2].pubkey.toBase58()).toMatch(/^[1-9A-HJ-NP-Za-km-z]{32,44}$/)
    expect(instruction.keys[2].isSigner).toBe(true)
    expect(instruction.keys[2].isWritable).toBe(true)
    expect(instruction.keys).toEqual([
      { pubkey: contest, isSigner: false, isWritable: false },
      { pubkey: certificate, isSigner: false, isWritable: true },
      instruction.keys[2],
      { pubkey: tokenAccount, isSigner: false, isWritable: true },
      { pubkey: metadata, isSigner: false, isWritable: true },
      { pubkey: wallet, isSigner: true, isWritable: true },
      {
        pubkey: new PublicKey('TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA'),
        isSigner: false,
        isWritable: false,
      },
      {
        pubkey: new PublicKey('ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL'),
        isSigner: false,
        isWritable: false,
      },
      {
        pubkey: new PublicKey('metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s'),
        isSigner: false,
        isWritable: false,
      },
      { pubkey: new PublicKey('11111111111111111111111111111111'), isSigner: false, isWritable: false },
      {
        pubkey: new PublicKey('SysvarRent111111111111111111111111111111111'),
        isSigner: false,
        isWritable: false,
      },
    ])
  })
})
