import { PublicKey } from "@solana/web3.js";
import { assert } from "chai";
import { contestPda, hex32, parseAdminArgs, runAdminCommand } from "../scripts/admin";

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

  it("parses publish-certificate-root batch arguments", () => {
    assert.deepEqual(
      parseAdminArgs([
        "publish-certificate-root",
        "practice-arena",
        "01".repeat(32),
        "02".repeat(32),
        "5",
        "91",
      ]),
      {
        kind: "publish-certificate-root",
        contestId: "practice-arena",
        root: Array.from(Buffer.alloc(32, 1)),
        snapshotHash: Array.from(Buffer.alloc(32, 2)),
        topN: 5,
        batchId: "91",
      },
    );
  });

  it("rejects invalid publish-certificate-root topN", () => {
    assert.throws(
      () =>
        parseAdminArgs([
          "publish-certificate-root",
          "practice-arena",
          "01".repeat(32),
          "02".repeat(32),
          "0",
          "91",
        ]),
      /topN must be between 1 and 100/,
    );
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

function fakeProgram() {
  const calls: string[] = [];
  const rpc = async (label: string) => {
    calls.push(label);
    return `${label}-signature`;
  };
  return {
    calls,
    programId: new PublicKey("9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx"),
    provider: {
      publicKey: new PublicKey("ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"),
    },
    methods: {
      initializeContest: (contestId: string) => ({
        accounts: () => ({
          rpc: () => rpc(`initialize:${contestId}`),
        }),
      }),
      setJoinEnabled: (enabled: boolean) => ({
        accounts: () => ({
          rpc: () => rpc(`join:${enabled}`),
        }),
      }),
      publishCertificateRoot: (
        root: number[],
        snapshotHash: number[],
        topN: number,
        batchId: string,
      ) => ({
        accounts: () => ({
          rpc: () => rpc(`root:${root.length}:${snapshotHash.length}:${topN}:${batchId}`),
        }),
      }),
    },
  };
}

describe("admin script dispatch", () => {
  it("dispatches initialize-contest to Anchor", async () => {
    const program = fakeProgram();
    const signature = await runAdminCommand(
      { kind: "initialize-contest", contestId: "practice-arena" },
      { program: program as any },
    );
    assert.equal(signature, "initialize:practice-arena-signature");
    assert.deepEqual(program.calls, ["initialize:practice-arena"]);
  });

  it("dispatches publish-certificate-root with 32-byte arrays", async () => {
    const program = fakeProgram();
    const signature = await runAdminCommand(
      {
        kind: "publish-certificate-root",
        contestId: "practice-arena",
        root: Array.from(Buffer.alloc(32, 1)),
        snapshotHash: Array.from(Buffer.alloc(32, 2)),
        topN: 5,
        batchId: "91",
      },
      { program: program as any },
    );
    assert.equal(signature, "root:32:32:5:91-signature");
  });
});
