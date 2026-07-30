import * as anchor from "@coral-xyz/anchor";
import { Program } from "@coral-xyz/anchor";
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
