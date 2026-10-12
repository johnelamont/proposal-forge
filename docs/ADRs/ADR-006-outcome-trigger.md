# ADR-006: Lost and Withdrawn Outcomes — the Zoho-Side Trigger

**Status:** Accepted  
**Date:** 2026-10-12  
**Deciders:** John Lamont

## Context

[ADR-005](ADR-005-zoho-integration.md) decided that outcomes are pushed from Zoho to `POST /api/integrations/zoho/outcome`, with a **Won** button for wins, and deferred one thing: how lost and withdrawn outcomes are sent. The endpoint and contract ([ZOHO_INTEGRATION.md](../ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho)) already allow them.

Since then, F6 (Lead out) has shipped and been used against the operator's CRM, which settled two facts:

- The Lead is created with `Lead_Status` = `Submitted Proposal`, because the operator submits on Upwork before pushing the Lead.
- On the Upwork layout, the operator closes a Lead by changing `Lead_Status`. Four values mean lost: `Job Closed`, `Lost Lead`, `Junk Lead`, `Not Qualified`. The first two account for about nine in ten lost Leads. `Withdrawn` is its own value.

There is also a side effect to resolve: the Lead-out upsert sends `Lead_Status` on every press, including an update. Once outcomes live in `Lead_Status`, an **Update Lead** press after the operator has marked a Lead lost would reset it to `Submitted Proposal`.

## Options Considered

| Option | Assessment |
|---|---|
| **Workflow rule on `Lead_Status` edit — Recommended** | Fires when the operator does what they already do: change the status. No extra click. Zoho workflow rules can call a Deluge function on a field update and can be limited to the five values. |
| One button per outcome on the Lead | Four or five more buttons beside **Won**, duplicating a status change the operator makes anyway. Rejected. |
| A single **Lost** button that reads `Lead_Status` | Still an extra click, and it is easy to press before setting the status. Rejected. |
| The app polls Leads for status changes | Needs read access to Leads, which carry client PII by then; rejected in ADR-005 for the same reason. |

## Decision

1. **Trigger.** A Zoho workflow rule on the Leads module, *on edit* of `Lead_Status`, limited to the Upwork layout, with the condition `Lead_Status` is one of `Job Closed`, `Lost Lead`, `Junk Lead`, `Not Qualified`, `Withdrawn`. Its action is a Deluge function that calls the shared helper from ADR-005 with the mapped outcome.
2. **Mapping.** Every status is its own `lost_reason`, so nothing is collapsed before it reaches the RAG index:

   | `Lead_Status` | `outcome` | `lost_reason` |
   |---|---|---|
   | `Lost Lead` | `lost` | `hired_other` |
   | `Job Closed` | `lost` | `job_closed` |
   | `Junk Lead` | `lost` | `junk_lead` |
   | `Not Qualified` | `lost` | `not_qualified` |
   | `Withdrawn` | `withdrawn` | — |

   `junk_lead` and `not_qualified` are judgements about the job, not losses to a competitor. They still count as `lost` for status, and the index keeps the reason so F2's advisory can learn "don't bid on this kind of post" separately from "we bid and lost".
3. **Corrections.** A later status change to another trigger value posts again; the app appends a new `proposal_outcomes` row and the latest wins, as the register already says. Changing the status back to `Submitted Proposal` is not a trigger value and is not posted; the app keeps the last recorded outcome. If that matters in practice, a reversal becomes a trigger value in a later decision.
4. **Failure visibility (Rule 8).** A workflow function cannot show a message the way a button does, so the function writes the app's response to a text field on the Lead, `Forge_Sync` (for example `Recorded lost (job_closed) 2026-10-12 14:02` or `ERROR 401: integration secret rejected`), and on any non-2xx response also sends the operator an email. The field is added to the Upwork layout by the operator before the function is deployed. The **Won** button keeps its return message and writes the same field.
5. **Lead out stops touching `Lead_Status` on update.** The upsert includes `Lead_Status` = `Submitted Proposal` only when the proposal has no Zoho Lead ID yet. On an update (a Lead ID is known from an earlier successful attempt), the field is omitted, so a status the operator has set is never reset. If an update unexpectedly inserts (the Lead was deleted in Zoho) and Zoho rejects the missing layout-required field, the app shows the error and the next press, which again has no Lead ID, includes the constant. This change ships with F8 and updates the F6 mapping doc.

## Consequences

**Easier:** recording a lost or withdrawn outcome is the status change the operator already makes; nothing new to learn. Five statuses give the RAG index a finer signal than one `lost`.

**Harder:** one more Deluge function and one workflow rule deployed by hand in Zoho, with source kept in this repo. A new text field on the Lead. The outcome enum grows by two values that the endpoint, the database check constraint and the RAG indexer must all accept.

**Revisit:** if the `Forge_Sync` field proves unread, replace it with a Zoho notification; if status reversals happen, add `Submitted Proposal` as a trigger that posts a `reopened` outcome.

## Related Decisions

- ADR-003: RAG learning — consumer of the finer-grained `lost_reason`.
- ADR-005: Zoho integration — transport, secret and allow-list that this trigger reuses.
