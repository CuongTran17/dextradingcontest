use anchor_lang::prelude::*;
use solana_sha256_hasher::hashv;

declare_id!("9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx");

const MAX_CONTEST_ID_LEN: usize = 32;
const MAX_BATCH_ID_LEN: usize = 32;
const MAX_METADATA_URI_LEN: usize = 200;
const MAX_MERKLE_PROOF_LEN: usize = 16;
const MAX_CERTIFICATE_TOP_N: u16 = 100;

#[program]
pub mod contest_nft {
    use super::*;

    pub fn initialize_contest(
        ctx: Context<InitializeContest>,
        contest_id: String,
    ) -> Result<()> {
        require!(
            contest_id.as_bytes().len() <= MAX_CONTEST_ID_LEN,
            ContestNftError::ContestIdTooLong
        );

        let contest = &mut ctx.accounts.contest;
        contest.admin = ctx.accounts.admin.key();
        contest.contest_id = contest_id;
        contest.join_enabled = true;
        contest.certificate_root = [0; 32];
        contest.snapshot_hash = [0; 32];
        contest.certificate_top_n = 0;
        contest.certificate_batch_id = String::new();
        contest.bump = ctx.bumps.contest;
        Ok(())
    }

    pub fn set_join_enabled(ctx: Context<SetJoinEnabled>, enabled: bool) -> Result<()> {
        ctx.accounts.contest.join_enabled = enabled;
        Ok(())
    }

    pub fn join_contest(ctx: Context<JoinContest>) -> Result<()> {
        require!(
            ctx.accounts.contest.join_enabled,
            ContestNftError::JoinDisabled
        );

        let participant = &mut ctx.accounts.participant;
        participant.contest = ctx.accounts.contest.key();
        participant.wallet = ctx.accounts.wallet.key();
        participant.joined_at = Clock::get()?.unix_timestamp;
        participant.bump = ctx.bumps.participant;
        msg!("join_contest contest_slug={}", ctx.accounts.contest.contest_id);
        Ok(())
    }

    pub fn publish_certificate_root(
        ctx: Context<PublishCertificateRoot>,
        root: [u8; 32],
        snapshot_hash: [u8; 32],
        top_n: u16,
        batch_id: String,
    ) -> Result<()> {
        require!(
            (1..=MAX_CERTIFICATE_TOP_N).contains(&top_n),
            ContestNftError::CertificateTopNInvalid
        );
        require!(
            batch_id.as_bytes().len() <= MAX_BATCH_ID_LEN,
            ContestNftError::BatchIdTooLong
        );

        ctx.accounts.contest.certificate_root = root;
        ctx.accounts.contest.snapshot_hash = snapshot_hash;
        ctx.accounts.contest.certificate_top_n = top_n;
        ctx.accounts.contest.certificate_batch_id = batch_id;
        Ok(())
    }

    pub fn claim_certificate(
        ctx: Context<ClaimCertificate>,
        contest_id: String,
        batch_id: String,
        top_n: u16,
        rank: u8,
        metadata_uri: String,
        snapshot_hash: [u8; 32],
        proof: Vec<[u8; 32]>,
    ) -> Result<()> {
        require!(
            contest_id == ctx.accounts.contest.contest_id,
            ContestNftError::ContestMismatch
        );
        require!(
            batch_id == ctx.accounts.contest.certificate_batch_id,
            ContestNftError::CertificateBatchMismatch
        );
        require!(
            top_n == ctx.accounts.contest.certificate_top_n,
            ContestNftError::CertificateTopNMismatch
        );
        require!(
            metadata_uri.as_bytes().len() <= MAX_METADATA_URI_LEN,
            ContestNftError::MetadataUriTooLong
        );
        require!(
            proof.len() <= MAX_MERKLE_PROOF_LEN,
            ContestNftError::ProofTooLong
        );
        require!(
            snapshot_hash == ctx.accounts.contest.snapshot_hash,
            ContestNftError::SnapshotHashMismatch
        );

        let leaf = certificate_leaf(
            &contest_id,
            &batch_id,
            &ctx.accounts.wallet.key().to_string(),
            top_n,
            rank,
            &metadata_uri,
            &snapshot_hash,
        );
        let root = merkle_root_from_proof(leaf, &proof);
        require!(
            root == ctx.accounts.contest.certificate_root,
            ContestNftError::InvalidMerkleProof
        );

        let certificate = &mut ctx.accounts.certificate;
        certificate.contest = ctx.accounts.contest.key();
        certificate.wallet = ctx.accounts.wallet.key();
        certificate.batch_id = batch_id;
        certificate.top_n = top_n;
        certificate.rank = rank;
        certificate.metadata_uri = metadata_uri;
        certificate.snapshot_hash = snapshot_hash;
        certificate.claimed_at = Clock::get()?.unix_timestamp;
        certificate.bump = ctx.bumps.certificate;
        Ok(())
    }
}

#[derive(Accounts)]
#[instruction(contest_id: String)]
pub struct InitializeContest<'info> {
    #[account(
        init,
        payer = admin,
        space = ContestState::LEN,
        seeds = [b"contest", contest_id.as_bytes()],
        bump
    )]
    pub contest: Account<'info, ContestState>,
    #[account(mut)]
    pub admin: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct SetJoinEnabled<'info> {
    #[account(
        mut,
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump = contest.bump,
        has_one = admin
    )]
    pub contest: Account<'info, ContestState>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct JoinContest<'info> {
    #[account(
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump = contest.bump
    )]
    pub contest: Account<'info, ContestState>,
    #[account(
        init,
        payer = wallet,
        space = Participant::LEN,
        seeds = [b"participant", contest.key().as_ref(), wallet.key().as_ref()],
        bump
    )]
    pub participant: Account<'info, Participant>,
    #[account(mut)]
    pub wallet: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct PublishCertificateRoot<'info> {
    #[account(
        mut,
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump = contest.bump,
        has_one = admin
    )]
    pub contest: Account<'info, ContestState>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct ClaimCertificate<'info> {
    #[account(
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump = contest.bump
    )]
    pub contest: Account<'info, ContestState>,
    #[account(
        init,
        payer = wallet,
        space = CertificateClaim::LEN,
        seeds = [b"certificate", contest.key().as_ref(), wallet.key().as_ref()],
        bump
    )]
    pub certificate: Account<'info, CertificateClaim>,
    #[account(mut)]
    pub wallet: Signer<'info>,
    pub system_program: Program<'info, System>,
}

#[account]
pub struct ContestState {
    pub admin: Pubkey,
    pub contest_id: String,
    pub join_enabled: bool,
    pub certificate_root: [u8; 32],
    pub snapshot_hash: [u8; 32],
    pub certificate_top_n: u16,
    pub certificate_batch_id: String,
    pub bump: u8,
}

impl ContestState {
    pub const LEN: usize =
        8 + 32 + 4 + MAX_CONTEST_ID_LEN + 1 + 32 + 32 + 2 + 4 + MAX_BATCH_ID_LEN + 1;
}

#[account]
pub struct Participant {
    pub contest: Pubkey,
    pub wallet: Pubkey,
    pub joined_at: i64,
    pub bump: u8,
}

impl Participant {
    pub const LEN: usize = 8 + 32 + 32 + 8 + 1;
}

#[account]
pub struct CertificateClaim {
    pub contest: Pubkey,
    pub wallet: Pubkey,
    pub batch_id: String,
    pub top_n: u16,
    pub rank: u8,
    pub metadata_uri: String,
    pub snapshot_hash: [u8; 32],
    pub claimed_at: i64,
    pub bump: u8,
}

impl CertificateClaim {
    pub const LEN: usize =
        8 + 32 + 32 + 4 + MAX_BATCH_ID_LEN + 2 + 1 + 4 + MAX_METADATA_URI_LEN + 32 + 8 + 1;
}

fn certificate_leaf(
    contest_id: &str,
    batch_id: &str,
    wallet: &str,
    top_n: u16,
    rank: u8,
    metadata_uri: &str,
    snapshot_hash: &[u8; 32],
) -> [u8; 32] {
    let payload = format!(
        "{{\"batch_id\":\"{}\",\"contest_id\":\"{}\",\"metadata_uri\":\"{}\",\"rank\":{},\"snapshot_hash\":\"{}\",\"top_n\":{},\"wallet\":\"{}\"}}",
        batch_id,
        contest_id,
        metadata_uri,
        rank,
        hex_lower(snapshot_hash),
        top_n,
        wallet
    );
    hashv(&[payload.as_bytes()]).to_bytes()
}

fn merkle_root_from_proof(mut leaf: [u8; 32], proof: &[[u8; 32]]) -> [u8; 32] {
    for sibling in proof {
        leaf = hash_sorted_pair(&leaf, sibling);
    }
    leaf
}

fn hash_sorted_pair(left: &[u8; 32], right: &[u8; 32]) -> [u8; 32] {
    if left <= right {
        hashv(&[left.as_ref(), right.as_ref()]).to_bytes()
    } else {
        hashv(&[right.as_ref(), left.as_ref()]).to_bytes()
    }
}

fn hex_lower(bytes: &[u8; 32]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(64);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

#[error_code]
pub enum ContestNftError {
    #[msg("Contest id must fit in a Solana PDA seed")]
    ContestIdTooLong,
    #[msg("Contest joins are disabled")]
    JoinDisabled,
    #[msg("Certificate contest does not match")]
    ContestMismatch,
    #[msg("Certificate metadata URI is too long")]
    MetadataUriTooLong,
    #[msg("Certificate batch id is too long")]
    BatchIdTooLong,
    #[msg("Certificate topN must be between 1 and 100")]
    CertificateTopNInvalid,
    #[msg("Certificate batch id does not match")]
    CertificateBatchMismatch,
    #[msg("Certificate topN does not match")]
    CertificateTopNMismatch,
    #[msg("Merkle proof is too long")]
    ProofTooLong,
    #[msg("Certificate snapshot hash does not match")]
    SnapshotHashMismatch,
    #[msg("Certificate Merkle proof is invalid")]
    InvalidMerkleProof,
}
