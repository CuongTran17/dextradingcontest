use anchor_lang::prelude::*;

declare_id!("Fg6PaFpoGXkYsidMpWxTWqGxUQimA1H8XmRjgoSvnF");

const MAX_CONTEST_ID_LEN: usize = 32;

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
    ) -> Result<()> {
        ctx.accounts.contest.certificate_root = root;
        ctx.accounts.contest.snapshot_hash = snapshot_hash;
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

#[account]
pub struct ContestState {
    pub admin: Pubkey,
    pub contest_id: String,
    pub join_enabled: bool,
    pub certificate_root: [u8; 32],
    pub snapshot_hash: [u8; 32],
    pub bump: u8,
}

impl ContestState {
    pub const LEN: usize = 8 + 32 + 4 + MAX_CONTEST_ID_LEN + 1 + 32 + 32 + 1;
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

#[error_code]
pub enum ContestNftError {
    #[msg("Contest id must fit in a Solana PDA seed")]
    ContestIdTooLong,
    #[msg("Contest joins are disabled")]
    JoinDisabled,
}
