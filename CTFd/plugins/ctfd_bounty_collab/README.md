# ctfd_bounty_collab

**Plugin for:** CyberCast Platform (CTFd fork)
**Created:** 2026-07-15
**Table prefix:** `bntc_`
**URL prefix:** `/plugins/bounty-collab/`
**Blueprint name:** `bounty_collab`

## What this plugin does

Team-based enterprise collaboration bounties:
1. An **Enterprise** user (org_type `company`) posts a research project.
2. **Expert** users (org_type `university`) browse and apply.
3. Enterprise owner selects a team, sets payout percentages, funds escrow.
4. Team submits deliverables; owner approves or requests revisions.
5. On approval, 90% of escrow is split among researchers, 10% goes to platform.

## How it differs from `ctfd_bounty`

| | `ctfd_bounty` | `ctfd_bounty_collab` |
|---|---|---|
| Submission model | One user, one report | Team, versioned deliverables |
| Payment model | Admin-set reward | Escrowed, split 90/10 on approval |
| Table prefix | `bnt_` | `bntc_` |
| NDA support | ✗ | ✓ |
| Dispute resolution | ✗ | ✓ (admin queue) |

## Tables created

| Table | Purpose |
|---|---|
| `bntc_projects` | Core project record |
| `bntc_applications` | Expert applications |
| `bntc_team_members` | Locked-in researchers + payout % |
| `bntc_nda_acceptances` | NDA acceptance records |
| `bntc_deliverables` | Versioned deliverable submissions |
| `bntc_escrow_ledger` | One-per-project escrow (funded/released/refunded) |
| `bntc_wallets` | Per-researcher internal wallet |
| `bntc_wallet_transactions` | Immutable ledger of all wallet movements |
| `bntc_audit_log` | Immutable audit trail of all state changes |

## Project state machine

```
draft → published → recruiting → team_locked → in_progress
      → submitted_for_review → approved → paid_out → closed
                             → revision_requested → in_progress
                             → disputed → approved (admin)
                                       → cancelled (admin, triggers refund)
draft/published/recruiting → cancelled (triggers escrow refund if funded)
```

## Related plugins

- **ctfd_organizations** — Enterprise/expert role is detected via `org_type`
  (`company` = enterprise, `university` = expert). No changes to that plugin.
- **ctfd_monetization** — Invoice creation reused via
  `create_enterprise_publish_invoice()` (optional; `invoice_id` FK is nullable).
  No wallet model existed in ctfd_monetization — `bntc_wallets` is new here.

## Running tests

```bash
pytest tests/plugins/test_ctfd_bounty_collab.py -v
```
