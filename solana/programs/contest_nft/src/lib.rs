use anchor_lang::prelude::*;
use anchor_spl::{
    associated_token::AssociatedToken,
    metadata::{
        create_metadata_accounts_v3, mpl_token_metadata::types::DataV2,
        CreateMetadataAccountsV3, Metadata,
    },
    token::{mint_to, Mint, MintTo, Token, TokenAccount},
};
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

        let signer_seeds: &[&[&[u8]]] = &[&[
            b"contest",
            ctx.accounts.contest.contest_id.as_bytes(),
            &[ctx.bumps.contest],
        ]];

        mint_to(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                MintTo {
                    mint: ctx.accounts.mint.to_account_info(),
                    to: ctx.accounts.token_account.to_account_info(),
                    authority: ctx.accounts.contest.to_account_info(),
                },
                signer_seeds,
            ),
            1,
        )?;

        create_metadata_accounts_v3(
            CpiContext::new_with_signer(
                ctx.accounts.token_metadata_program.to_account_info(),
                CreateMetadataAccountsV3 {
                    metadata: ctx.accounts.metadata.to_account_info(),
                    mint: ctx.accounts.mint.to_account_info(),
                    mint_authority: ctx.accounts.contest.to_account_info(),
                    payer: ctx.accounts.wallet.to_account_info(),
                    update_authority: ctx.accounts.contest.to_account_info(),
                    system_program: ctx.accounts.system_program.to_account_info(),
                    rent: ctx.accounts.rent.to_account_info(),
                },
                signer_seeds,
            ),
            DataV2 {
                name: certificate_name(&ctx.accounts.contest.contest_id, rank),
                symbol: "CDTC".to_string(),
                uri: metadata_uri.clone(),
                seller_fee_basis_points: 0,
                creators: None,
                collection: None,
                uses: None,
            },
            true,
            true,
            None,
        )?;

        let certificate = &mut ctx.accounts.certificate;
        certificate.contest = ctx.accounts.contest.key();
        certificate.wallet = ctx.accounts.wallet.key();
        certificate.mint = ctx.accounts.mint.key();
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
        bump,
        has_one = admin
    )]
    pub contest: Account<'info, ContestState>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct JoinContest<'info> {
    #[account(
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump
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
        bump,
        has_one = admin
    )]
    pub contest: Account<'info, ContestState>,
    pub admin: Signer<'info>,
}

#[derive(Accounts)]
pub struct ClaimCertificate<'info> {
    #[account(
        seeds = [b"contest", contest.contest_id.as_bytes()],
        bump
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
    #[account(
        init,
        payer = wallet,
        mint::decimals = 0,
        mint::authority = contest,
        mint::freeze_authority = contest
    )]
    pub mint: Account<'info, Mint>,
    #[account(
        init,
        payer = wallet,
        associated_token::mint = mint,
        associated_token::authority = wallet
    )]
    pub token_account: Account<'info, TokenAccount>,
    #[account(
        mut,
        seeds = [
            b"metadata",
            token_metadata_program.key().as_ref(),
            mint.key().as_ref()
        ],
        bump,
        seeds::program = token_metadata_program.key()
    )]
    /// CHECK: The Metaplex token metadata program validates and owns this PDA.
    pub metadata: UncheckedAccount<'info>,
    #[account(mut)]
    pub wallet: Signer<'info>,
    pub token_program: Program<'info, Token>,
    pub associated_token_program: Program<'info, AssociatedToken>,
    pub token_metadata_program: Program<'info, Metadata>,
    pub system_program: Program<'info, System>,
    pub rent: Sysvar<'info, Rent>,
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
    pub mint: Pubkey,
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
        8 + 32 + 32 + 32 + 4 + MAX_BATCH_ID_LEN + 2 + 1 + 4 + MAX_METADATA_URI_LEN + 32 + 8 + 1;
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

fn certificate_name(contest_id: &str, rank: u8) -> String {
    let suffix = format!(" #{}", rank);
    let max_prefix_len = 32usize.saturating_sub(suffix.as_bytes().len());
    let mut prefix = contest_id.to_string();
    if prefix.as_bytes().len() > max_prefix_len {
        prefix.truncate(max_prefix_len);
    }
    format!("{}{}", prefix, suffix)
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
