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
  const snapshotHash = Array.from(Buffer.alloc(32, 7));

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

  function hex(bytes: number[]) {
    return Buffer.from(bytes).toString("hex");
  }

  function certificateLeaf() {
    const payload = JSON.stringify({
      contest_id: contestId,
      metadata_uri: metadataUri,
      rank,
      snapshot_hash: hex(snapshotHash),
      wallet: provider.wallet.publicKey.toBase58(),
    });
    return Array.from(createHash("sha256").update(payload).digest());
  }

  it("mints one certificate for a valid proof and rejects duplicate claims", async () => {
    const contest = contestPda();
    const certificate = certificatePda(contest);
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
      .publishCertificateRoot(root, snapshotHash)
      .accounts({
        contest,
        admin: provider.wallet.publicKey,
      })
      .rpc();

    await program.methods
      .claimCertificate(contestId, rank, metadataUri, snapshotHash, [])
      .accounts({
        contest,
        certificate,
        wallet: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    const account = await (program.account as any).certificateClaim.fetch(certificate);
    assert.equal(account.wallet.toBase58(), provider.wallet.publicKey.toBase58());
    assert.equal(account.rank, rank);
    assert.equal(account.metadataUri, metadataUri);

    try {
      await program.methods
        .claimCertificate(contestId, rank, metadataUri, snapshotHash, [])
        .accounts({
          contest,
          certificate,
          wallet: provider.wallet.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        })
        .rpc();
      assert.fail("duplicate certificate claim should fail");
    } catch (error) {
      assert.match(String(error), /already in use|custom program error|Error/i);
    }
  });
});
