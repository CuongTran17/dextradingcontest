import { PublicKey } from "@solana/web3.js";
import { assert } from "chai";
import { contestPda, hex32, parseAdminArgs } from "../scripts/admin";

describe("admin script helpers", () => {
  const programId = new PublicKey("9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx");

  it("parses initialize-contest arguments", () => {
    assert.deepEqual(parseAdminArgs(["initialize-contest", "practice-arena"]), {
      kind: "initialize-contest",
      contestId: "practice-arena",
    });
  });

  it("parses set-join-enabled arguments", () => {
    assert.deepEqual(parseAdminArgs(["set-join-enabled", "practice-arena", "false"]), {
      kind: "set-join-enabled",
      contestId: "practice-arena",
      enabled: false,
    });
  });

  it("normalizes 32-byte hex inputs", () => {
    assert.deepEqual(hex32("0x" + "ab".repeat(32), "root"), Array.from(Buffer.alloc(32, 0xab)));
  });

  it("rejects non-32-byte hex inputs", () => {
    assert.throws(() => hex32("ab", "root"), /root must be 32 bytes/);
  });

  it("derives the contest PDA with the program seed convention", () => {
    const pda = contestPda(programId, "practice-arena");
    const expected = PublicKey.findProgramAddressSync(
      [Buffer.from("contest"), Buffer.from("practice-arena")],
      programId,
    )[0];
    assert.equal(pda.toBase58(), expected.toBase58());
  });
});
