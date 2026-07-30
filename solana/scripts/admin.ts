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
