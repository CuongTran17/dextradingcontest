# Solana Admin Scripts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add checked-in Solana admin scripts for initializing contest PDAs, toggling on-chain joins, and publishing certificate Merkle roots on devnet.

**Architecture:** Keep all privileged on-chain actions in `solana/scripts/admin.ts`, driven by explicit CLI subcommands and Anchor provider configuration. The script derives the same PDAs used by tests/frontend and calls the deployed Anchor program with the configured admin wallet. Tests validate argument parsing, PDA derivation, root/hash normalization, and instruction dispatch through an injected fake program before any devnet command is run.

**Tech Stack:** Anchor 0.32.1, TypeScript, ts-mocha, Chai, Solana web3.js, devnet program `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.

## Global Constraints

- Solana devnet is the target for the current deployment.
- Program ID must remain `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx` unless `anchor keys sync` changes it in a future deploy.
- Admin scripts must not embed private keys or seed phrases.
- Admin scripts must use `ANCHOR_PROVIDER_URL` and `ANCHOR_WALLET` or Anchor CLI provider defaults.
- Contest IDs passed to on-chain instructions must be at most 32 bytes, matching `MAX_CONTEST_ID_LEN`.
- Merkle root and snapshot hash inputs must be exactly 32 bytes encoded as 64 lowercase or uppercase hex characters.
- Tests must be written and observed failing before production code changes.
- Do not commit `solana/target/`, `solana/.anchor/`, `solana/test-ledger/`, or deploy keypairs.

---

### Task 1: Admin Command Parser and Hex Utilities

**Files:**
- Create: `solana/scripts/admin.ts`
- Create: `solana/tests/admin_script.ts`
- Modify: `solana/package.json`

**Interfaces:**
- Produces `parseAdminArgs(argv: string[]): AdminCommand`
- Produces `hex32(value: string, label: string): number[]`
- Produces `contestPda(programId: PublicKey, contestId: string): PublicKey`
- Produces package script `admin`: `ts-node scripts/admin.ts`

- [ ] **Step 1: Add failing parser and utility tests**

Create `solana/tests/admin_script.ts`:

```ts
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd solana
npm run test -- tests/admin_script.ts
```

Expected: FAIL because `solana/scripts/admin.ts` does not exist.

- [ ] **Step 3: Add minimal admin helper exports**

Create `solana/scripts/admin.ts`:

```ts
import { PublicKey } from "@solana/web3.js";

export type AdminCommand =
  | { kind: "initialize-contest"; contestId: string }
  | { kind: "set-join-enabled"; contestId: string; enabled: boolean }
  | {
      kind: "publish-certificate-root";
      contestId: string;
      root: number[];
      snapshotHash: number[];
    };

export function parseAdminArgs(argv: string[]): AdminCommand {
  const [command, contestId, firstValue, secondValue] = argv;
  if (!contestId) throw new Error("contest id is required");
  if (Buffer.byteLength(contestId, "utf8") > 32) {
    throw new Error("contest id must be at most 32 bytes");
  }

  if (command === "initialize-contest") {
    return { kind: "initialize-contest", contestId };
  }
  if (command === "set-join-enabled") {
    if (firstValue !== "true" && firstValue !== "false") {
      throw new Error("enabled must be true or false");
    }
    return { kind: "set-join-enabled", contestId, enabled: firstValue === "true" };
  }
  if (command === "publish-certificate-root") {
    if (!firstValue || !secondValue) {
      throw new Error("root and snapshot hash are required");
    }
    return {
      kind: "publish-certificate-root",
      contestId,
      root: hex32(firstValue, "root"),
      snapshotHash: hex32(secondValue, "snapshot hash"),
    };
  }
  throw new Error("unknown admin command");
}

export function hex32(value: string, label: string): number[] {
  const normalized = value.startsWith("0x") ? value.slice(2) : value;
  if (!/^[0-9a-fA-F]{64}$/.test(normalized)) {
    throw new Error(`${label} must be 32 bytes encoded as 64 hex characters`);
  }
  return Array.from(Buffer.from(normalized, "hex"));
}

export function contestPda(programId: PublicKey, contestId: string): PublicKey {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("contest"), Buffer.from(contestId)],
    programId,
  )[0];
}
```

Modify `solana/package.json` scripts:

```json
{
  "scripts": {
    "test": "ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts",
    "admin": "ts-node scripts/admin.ts"
  }
}
```

Add dev dependency in `solana/package.json`:

```json
"ts-node": "^10.9.2"
```

- [ ] **Step 4: Install/update script dependencies**

Run:

```bash
cd solana
npm install
```

Expected: `solana/package-lock.json` updates with `ts-node`.

- [ ] **Step 5: Run tests to verify helpers pass**

Run:

```bash
cd solana
npm run test -- tests/admin_script.ts
```

Expected: PASS for parser, hex, and PDA helper tests.

- [ ] **Step 6: Commit Task 1**

```bash
git add solana/package.json solana/package-lock.json solana/scripts/admin.ts solana/tests/admin_script.ts
git commit -m "feat: add solana admin command helpers"
```

### Task 2: Admin Instruction Dispatch

**Files:**
- Modify: `solana/scripts/admin.ts`
- Modify: `solana/tests/admin_script.ts`

**Interfaces:**
- Consumes `AdminCommand`, `contestPda`, and `hex32` from Task 1.
- Produces `runAdminCommand(command: AdminCommand, deps: AdminDeps): Promise<string>`
- Produces CLI entrypoint `main(argv?: string[]): Promise<void>`

- [ ] **Step 1: Add failing dispatch tests**

Append to `solana/tests/admin_script.ts`:

```ts
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
      publishCertificateRoot: (root: number[], snapshotHash: number[]) => ({
        accounts: () => ({
          rpc: () => rpc(`root:${root.length}:${snapshotHash.length}`),
        }),
      }),
    },
  };
}

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
    },
    { program: program as any },
  );
  assert.equal(signature, "root:32:32-signature");
});
```

Update import line:

```ts
import { contestPda, hex32, parseAdminArgs, runAdminCommand } from "../scripts/admin";
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd solana
npm run test -- tests/admin_script.ts
```

Expected: FAIL because `runAdminCommand` is not exported.

- [ ] **Step 3: Implement dispatch function**

Add to `solana/scripts/admin.ts`:

```ts
import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";

export interface AdminDeps {
  program: Program;
}

export async function runAdminCommand(command: AdminCommand, deps: AdminDeps): Promise<string> {
  const contest = contestPda(deps.program.programId, command.contestId);
  const admin = deps.program.provider.publicKey;
  if (!admin) throw new Error("admin wallet public key is unavailable");

  if (command.kind === "initialize-contest") {
    return deps.program.methods
      .initializeContest(command.contestId)
      .accounts({
        contest,
        admin,
        systemProgram: anchor.web3.SystemProgram.programId,
      })
      .rpc();
  }

  if (command.kind === "set-join-enabled") {
    return deps.program.methods
      .setJoinEnabled(command.enabled)
      .accounts({ contest, admin })
      .rpc();
  }

  return deps.program.methods
    .publishCertificateRoot(command.root, command.snapshotHash)
    .accounts({ contest, admin })
    .rpc();
}
```

- [ ] **Step 4: Implement CLI entrypoint**

Add to `solana/scripts/admin.ts`:

```ts
export async function main(argv = process.argv.slice(2)): Promise<void> {
  const command = parseAdminArgs(argv);
  const provider = anchor.AnchorProvider.env();
  anchor.setProvider(provider);
  const program = anchor.workspace.ContestNft as Program;
  const signature = await runAdminCommand(command, { program });
  console.log(`signature=${signature}`);
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error instanceof Error ? error.message : error);
    process.exitCode = 1;
  });
}
```

- [ ] **Step 5: Run admin script tests**

Run:

```bash
cd solana
npm run test -- tests/admin_script.ts
```

Expected: PASS.

- [ ] **Step 6: Run full Anchor TypeScript tests**

Run:

```bash
cd solana
anchor test
```

Expected: PASS with join, certificate claim, and admin helper tests.

- [ ] **Step 7: Commit Task 2**

```bash
git add solana/scripts/admin.ts solana/tests/admin_script.ts
git commit -m "feat: dispatch solana admin instructions"
```

### Task 3: Devnet Admin Workflow Documentation

**Files:**
- Modify: `docs/solana-devnet-deployment.md`
- Modify: `backend_v2/.env.example`

**Interfaces:**
- Consumes admin script from Task 2.
- Produces documented commands for:
  - Initialize contest on devnet
  - Enable or disable joins
  - Publish certificate root and snapshot hash

- [ ] **Step 1: Add deployment doc commands**

In `docs/solana-devnet-deployment.md`, replace the section that says the admin script will be added later with:

```markdown
## 9. Initialize Contest On-chain

Run from WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- initialize-contest practice-arena
```

Enable joins:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled practice-arena true
```

Disable joins:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled practice-arena false
```

Publish certificate root after backend export:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- publish-certificate-root practice-arena <MERKLE_ROOT_HEX> <SNAPSHOT_HASH_HEX>
```

The script prints `signature=<TX_SIGNATURE>` when the transaction succeeds.
```

- [ ] **Step 2: Add backend env example program ID**

In `backend_v2/.env.example`, set:

```env
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
```

- [ ] **Step 3: Run docs sanity checks**

Run:

```powershell
git diff --check -- docs/solana-devnet-deployment.md backend_v2/.env.example
```

Expected: no whitespace errors.

- [ ] **Step 4: Run Solana admin tests again**

Run:

```bash
cd solana
npm run test -- tests/admin_script.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add docs/solana-devnet-deployment.md backend_v2/.env.example
git commit -m "docs: add solana admin script workflow"
```

### Task 4: Manual Devnet Smoke Test

**Files:**
- Modify: `docs/solana-devnet-deployment.md`

**Interfaces:**
- Consumes admin CLI from Task 2.
- Produces recorded smoke-test command/output checklist in docs.

- [ ] **Step 1: Run devnet initialize smoke test in WSL**

Use a unique contest id so the PDA is not already initialized:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
CONTEST_ID=smoke-$(date +%s)
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- initialize-contest "$CONTEST_ID"
```

Expected: prints `signature=<TX_SIGNATURE>`.

- [ ] **Step 2: Run devnet join toggle smoke test in WSL**

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled "$CONTEST_ID" false

ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled "$CONTEST_ID" true
```

Expected: each command prints `signature=<TX_SIGNATURE>`.

- [ ] **Step 3: Run devnet root publish smoke test in WSL**

```bash
ROOT_HEX=$(printf '01%.0s' {1..32})
SNAPSHOT_HEX=$(printf '02%.0s' {1..32})
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- publish-certificate-root "$CONTEST_ID" "$ROOT_HEX" "$SNAPSHOT_HEX"
```

Expected: prints `signature=<TX_SIGNATURE>`.

- [ ] **Step 4: Record smoke-test format in docs**

Append to `docs/solana-devnet-deployment.md`:

```markdown
## Admin Script Smoke-Test Record

When smoke testing, record:

```text
CONTEST_ID=<contest id used>
INITIALIZE_SIGNATURE=<signature>
DISABLE_JOIN_SIGNATURE=<signature>
ENABLE_JOIN_SIGNATURE=<signature>
PUBLISH_ROOT_SIGNATURE=<signature>
```
```

- [ ] **Step 5: Run final verification**

Run:

```powershell
npm.cmd run type-check
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/services/__tests__/solanaWallet.test.ts
```

Run in WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
npm run test -- tests/admin_script.ts
anchor test
```

Expected: all commands pass.

- [ ] **Step 6: Commit Task 4**

```bash
git add docs/solana-devnet-deployment.md
git commit -m "docs: record solana admin smoke test workflow"
```

## Self-Review

- Spec coverage: plan covers initialize contest, join toggle, certificate root publishing, docs, env example, and devnet smoke testing.
- Placeholder scan: no `TBD`, `TODO`, or implementation-free "handle edge cases" steps remain.
- Type consistency: `AdminCommand`, `parseAdminArgs`, `hex32`, `contestPda`, `runAdminCommand`, and `main` signatures are defined before use and reused consistently.
- Scope check: Metaplex NFT mint, faucet, and certificate claim UI are intentionally excluded; they belong to later plans after admin operations are reliable.
