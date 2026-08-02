import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { assert } from "chai";
import { createHash } from "crypto";

describe("contest_nft certificate claim", () => {
  anchor.setProvider(anchor.AnchorProvider.env());

  const program = anchor.workspace.ContestNft as Program;
  const provider = anchor.getProvider() as anchor.AnchorProvider;
  const contestId = `claim-cup-${Date.now()}`;
  const metadataUri = "ipfs://QmCertificateMetadata";
  const rank = 1;
  const batchId = "91";
  const topN = 5;
  const snapshotHash = Array.from(Buffer.alloc(32, 7));
  const tokenProgramId = new anchor.web3.PublicKey(
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
  );
  const associatedTokenProgramId = new anchor.web3.PublicKey(
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
  );
  const tokenMetadataProgramId = new anchor.web3.PublicKey(
    "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s",
  );

  function contestPda() {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from("contest"), Buffer.from(contestId)],
      program.programId,
    )[0];
  }

  function certificatePda(contest: anchor.web3.PublicKey) {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [
        Buffer.from("certificate"),
        contest.toBuffer(),
        provider.wallet.publicKey.toBuffer(),
      ],
      program.programId,
    )[0];
  }

  function associatedTokenAddress(mint: anchor.web3.PublicKey) {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [
        provider.wallet.publicKey.toBuffer(),
        tokenProgramId.toBuffer(),
        mint.toBuffer(),
      ],
      associatedTokenProgramId,
    )[0];
  }

  function metadataPda(mint: anchor.web3.PublicKey) {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [
        Buffer.from("metadata"),
        tokenMetadataProgramId.toBuffer(),
        mint.toBuffer(),
      ],
      tokenMetadataProgramId,
    )[0];
  }

  function hex(bytes: number[]) {
    return Buffer.from(bytes).toString("hex");
  }

  function certificateLeaf() {
    const payload = JSON.stringify({
      batch_id: batchId,
      contest_id: contestId,
      metadata_uri: metadataUri,
      rank,
      snapshot_hash: hex(snapshotHash),
      top_n: topN,
      wallet: provider.wallet.publicKey.toBase58(),
    });
    return Array.from(createHash("sha256").update(payload).digest());
  }

  it("mints one certificate for a valid proof and rejects duplicate claims", async () => {
    const contest = contestPda();
    const certificate = certificatePda(contest);
    const mint = anchor.web3.Keypair.generate();
    const tokenAccount = associatedTokenAddress(mint.publicKey);
    const metadata = metadataPda(mint.publicKey);
    const root = certificateLeaf();

    await program.methods
      .initializeContest(contestId)
      .accounts({
        contest,
        admin: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    await program.methods
      .publishCertificateRoot(root, snapshotHash, topN, batchId)
      .accounts({
        contest,
        admin: provider.wallet.publicKey,
      })
      .rpc();

    const contestAccount = await (program.account as any).contestState.fetch(contest);
    assert.equal(contestAccount.certificateTopN, topN);
    assert.equal(contestAccount.certificateBatchId, batchId);

    try {
      await program.methods
        .claimCertificate(contestId, "92", topN, rank, metadataUri, snapshotHash, [])
        .accounts({
          contest,
          certificate,
          wallet: provider.wallet.publicKey,
          mint: mint.publicKey,
          tokenAccount,
          metadata,
          tokenProgram: tokenProgramId,
          associatedTokenProgram: associatedTokenProgramId,
          tokenMetadataProgram: tokenMetadataProgramId,
          systemProgram: anchor.web3.SystemProgram.programId,
          rent: anchor.web3.SYSVAR_RENT_PUBKEY,
        })
        .signers([mint])
        .rpc();
      assert.fail("claim with wrong batch id should fail");
    } catch (error) {
      assert.match(String(error), /Certificate batch id does not match|custom program error|Error/i);
    }

    try {
      await program.methods
        .claimCertificate(contestId, batchId, topN + 1, rank, metadataUri, snapshotHash, [])
        .accounts({
          contest,
          certificate,
          wallet: provider.wallet.publicKey,
          mint: mint.publicKey,
          tokenAccount,
          metadata,
          tokenProgram: tokenProgramId,
          associatedTokenProgram: associatedTokenProgramId,
          tokenMetadataProgram: tokenMetadataProgramId,
          systemProgram: anchor.web3.SystemProgram.programId,
          rent: anchor.web3.SYSVAR_RENT_PUBKEY,
        })
        .signers([mint])
        .rpc();
      assert.fail("claim with wrong topN should fail");
    } catch (error) {
      assert.match(String(error), /Certificate topN does not match|custom program error|Error/i);
    }

    await program.methods
      .claimCertificate(contestId, batchId, topN, rank, metadataUri, snapshotHash, [])
      .accounts({
        contest,
        certificate,
        wallet: provider.wallet.publicKey,
        mint: mint.publicKey,
        tokenAccount,
        metadata,
        tokenProgram: tokenProgramId,
        associatedTokenProgram: associatedTokenProgramId,
        tokenMetadataProgram: tokenMetadataProgramId,
        systemProgram: anchor.web3.SystemProgram.programId,
        rent: anchor.web3.SYSVAR_RENT_PUBKEY,
      })
      .signers([mint])
      .rpc();

    const account = await (program.account as any).certificateClaim.fetch(certificate);
    assert.equal(account.wallet.toBase58(), provider.wallet.publicKey.toBase58());
    assert.equal(account.mint.toBase58(), mint.publicKey.toBase58());
    assert.equal(account.rank, rank);
    assert.equal(account.batchId, batchId);
    assert.equal(account.topN, topN);
    assert.equal(account.metadataUri, metadataUri);
    const mintAccount = await provider.connection.getParsedAccountInfo(mint.publicKey);
    assert.isNotNull(mintAccount.value);
    const tokenBalance = await provider.connection.getTokenAccountBalance(tokenAccount);
    assert.equal(tokenBalance.value.amount, "1");
    assert.equal(tokenBalance.value.decimals, 0);
    const metadataAccount = await provider.connection.getAccountInfo(metadata);
    assert.isNotNull(metadataAccount);

    try {
      const duplicateMint = anchor.web3.Keypair.generate();
      const duplicateTokenAccount = associatedTokenAddress(duplicateMint.publicKey);
      const duplicateMetadata = metadataPda(duplicateMint.publicKey);
      await program.methods
        .claimCertificate(contestId, batchId, topN, rank, metadataUri, snapshotHash, [])
        .accounts({
          contest,
          certificate,
          wallet: provider.wallet.publicKey,
          mint: duplicateMint.publicKey,
          tokenAccount: duplicateTokenAccount,
          metadata: duplicateMetadata,
          tokenProgram: tokenProgramId,
          associatedTokenProgram: associatedTokenProgramId,
          tokenMetadataProgram: tokenMetadataProgramId,
          systemProgram: anchor.web3.SystemProgram.programId,
          rent: anchor.web3.SYSVAR_RENT_PUBKEY,
        })
        .signers([duplicateMint])
        .rpc();
      assert.fail("duplicate certificate claim should fail");
    } catch (error) {
      assert.match(String(error), /already in use|custom program error|Error/i);
    }
  });
});
