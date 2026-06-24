# Crypto Admin Contest Management Design

## Goal

Define the administrator capabilities for the crypto trading contest system while protecting participant balances, positions, PnL, orders, and fills from manual modification.

The existing Admin Dashboard and contest-related tabs should be extended. A separate replacement dashboard is not required.

## Admin Capabilities

Administrators may:

- Create a contest.
- Edit a contest while its state permits configuration changes.
- Set the title and description.
- Set the initial virtual capital.
- Select the supported Spot symbols.
- Set the simulated trading fee.
- Set the start and end times.
- Publish or schedule a contest.
- Start, complete, or cancel a contest through valid state transitions.
- View participants, accounts, positions, orders, fills, equity, ROI, and leaderboard results.
- Extend the end time of an active contest.
- Lock or disqualify a participant when an error, abuse, or rule violation is detected.
- Record an explanatory reason for participant moderation.
- View market-data health and contest operational status.

## Prohibited Capabilities

Administrators must not:

- Change a participant's available or locked balance.
- Change position quantity or average entry price.
- Change realized or unrealized PnL.
- Create, edit, or delete a participant's order or fill.
- Rewrite portfolio or leaderboard history.
- manually assign a leaderboard rank.
- Backdate trades or contest participation.
- Bypass the trading engine to grant virtual assets.

No administrative API or UI control should expose these actions.

## Contest State Rules

### Draft

The administrator may change:

- Initial capital.
- Supported symbols.
- Trading fee.
- Start time.
- End time.
- Title, description, and rules.

The contest is not visible as an active trading arena.

### Scheduled

The administrator may change configuration before the contest starts. Changes must be recorded in the audit log.

If participants have already joined, changes to initial capital, supported symbols, or fees require an explicit confirmation in the Admin UI.

### Active

The following fields are immutable:

- Initial capital.
- Supported symbols.
- Trading fee.
- Start time.
- Core trading rules.

The administrator may only:

- Extend the end time.
- Lock or disqualify a participant.
- Complete or cancel the contest when operationally necessary.

The end time cannot be moved earlier than the current configured end time.

### Completed Or Cancelled

The contest is read-only. Participants, orders, fills, balances, positions, and leaderboard results remain available for inspection.

## Participant Moderation

Supported moderation actions:

- `lock`: prevent new orders while preserving the participant and their history.
- `disqualify`: prevent new orders and exclude the participant from official ranking.

Every moderation action requires:

- Administrator user ID.
- Participant ID.
- Contest ID.
- Action type.
- Non-empty reason.
- Timestamp.

Unlocking or reversing a disqualification also requires a reason and creates a new audit event. Existing audit events are immutable.

Moderation must never modify existing balances, positions, orders, fills, or calculated PnL.

## Audit Log

The backend must create append-only audit records for:

- Contest creation.
- Contest configuration changes.
- Contest state transitions.
- Active-contest end-time extensions.
- Participant lock and unlock actions.
- Participant disqualification and reinstatement.

Each audit record stores:

- Administrator ID.
- Event type.
- Target entity type and ID.
- Previous values.
- New values.
- Reason when required.
- Creation timestamp.

Audit records cannot be edited or deleted through the application.

## Admin Views

Extend the current Admin Dashboard with these views:

### Overview

- Active and scheduled contest counts.
- Participant count.
- Order count.
- Binance market-data status.
- DuckDB backfill and freshness status when Phase 2 is available.

### Contests

- Contest list and state.
- Create and edit form.
- Initial capital, symbols, fee, start time, and end time.
- Valid state-transition controls.
- Active-contest end-time extension.

### Participants

- User identity.
- Contest status.
- Account equity and ROI.
- Trade count.
- Lock and disqualify actions with mandatory reason dialogs.

### Orders And Fills

- Read-only order and fill inspection.
- Filters for contest, participant, symbol, side, status, and time.
- Rejection reasons and execution details.

### Results

- Read-only leaderboard.
- Included and disqualified participant indicators.
- Contest completion status.

### Audit Log

- Administrator actions.
- Target entity.
- Change summary.
- Reason.
- Timestamp.

## Backend Rules

- Every Admin endpoint requires the existing `admin` role.
- Contest updates validate the current state before applying changes.
- State transitions use an explicit transition table.
- Active contest configuration is enforced in backend services, not only hidden in the UI.
- Participant moderation and contest updates execute in database transactions.
- Unauthorized or invalid changes return `403` or `409`.
- Trading services reject orders from locked or disqualified participants.

## Suggested API Surface

```text
GET    /api/admin/crypto/overview
GET    /api/admin/crypto/contests
POST   /api/admin/crypto/contests
GET    /api/admin/crypto/contests/{contest_id}
PATCH  /api/admin/crypto/contests/{contest_id}
POST   /api/admin/crypto/contests/{contest_id}/transition
POST   /api/admin/crypto/contests/{contest_id}/extend
GET    /api/admin/crypto/contests/{contest_id}/participants
POST   /api/admin/crypto/participants/{participant_id}/lock
POST   /api/admin/crypto/participants/{participant_id}/unlock
POST   /api/admin/crypto/participants/{participant_id}/disqualify
POST   /api/admin/crypto/participants/{participant_id}/reinstate
GET    /api/admin/crypto/orders
GET    /api/admin/crypto/audit-logs
```

There is intentionally no endpoint for editing balances, positions, PnL, orders, fills, or leaderboard ranks.

## Testing Requirements

- Verify valid and invalid contest state transitions.
- Verify active contest configuration cannot be changed.
- Verify active contest end time can only be extended.
- Verify moderation requires a non-empty reason.
- Verify locked and disqualified participants cannot place orders.
- Verify disqualification does not mutate account history.
- Verify non-admin users receive `403`.
- Verify no balance or position mutation endpoint exists.
- Verify every successful Admin mutation creates an audit record.
- Verify audit records are append-only.

## Delivery Order

1. Complete the transactional trading foundation.
2. Add Admin backend services and authorization.
3. Connect the existing Admin Dashboard tabs to real data.
4. Add market-data monitoring after the DuckDB warehouse is implemented.
5. Add realtime connection monitoring after Binance WebSocket ingestion is implemented.

## Acceptance Criteria

- Admin can configure and schedule contests before they start.
- Active contest trading rules cannot be modified.
- Active contest end time can be extended but not shortened.
- Admin can lock or disqualify participants with a required reason.
- Locked or disqualified participants cannot submit new orders.
- Admin cannot alter financial or trading history.
- Every Admin mutation is traceable through an immutable audit log.
