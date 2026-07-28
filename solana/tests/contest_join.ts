import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
import { assert } from "chai";

describe("contest_nft join", () => {
  anchor.setProvider(anchor.AnchorProvider.env());

  const program = anchor.workspace.ContestNft as Program;
  const provider = anchor.getProvider() as anchor.AnchorProvider;
  const contestId = `summer-cup-${Date.now()}`;

  function contestPda() {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [Buffer.from("contest"), Buffer.from(contestId)],
      program.programId,
    )[0];
  }

  function participantPda(contest: anchor.web3.PublicKey) {
    return anchor.web3.PublicKey.findProgramAddressSync(
      [
        Buffer.from("participant"),
        contest.toBuffer(),
        provider.wallet.publicKey.toBuffer(),
      ],
      program.programId,
    )[0];
  }

  it("lets a wallet join a contest once", async () => {
    const contest = contestPda();
    const participant = participantPda(contest);

    await program.methods
      .initializeContest(contestId)
      .accounts({
        contest,
        admin: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    await program.methods
      .joinContest()
      .accounts({
        contest,
        participant,
        wallet: provider.wallet.publicKey,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();

    const account = await program.account.participant.fetch(participant);
    assert.equal(account.wallet.toBase58(), provider.wallet.publicKey.toBase58());

    try {
      await program.methods
        .joinContest()
        .accounts({
          contest,
          participant,
          wallet: provider.wallet.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        })
        .rpc();
      assert.fail("duplicate join should fail");
    } catch (error) {
      assert.match(String(error), /already in use|custom program error|Error/i);
    }
  });
});
