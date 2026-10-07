# Job post fixtures

Real Upwork job posts, copied by the operator with select-all / copy and pasted as plain text. They are the inputs for the F1 parser tests and the evidence behind the F1 entry in [FEATURE_REGISTER.md](../../../docs/governance/FEATURE_REGISTER.md).

| File | Source | What it exercises |
|---|---|---|
| `job_desktop_hourly_zoho_consulting.txt` | Desktop browser, 2026-10-06 | Baseline desktop layout. Hourly with rate range. Established client with ratings, spend, and a populated *Client's recent history* section. Job link present. |
| `job_desktop_hourly_vs_fixed_conflict_mortgage.txt` | Desktop browser, 2026-10-06 | Upwork fields say *Hourly $9–$21*; the description says *fixed price, 3 milestones* → `conflicts`. Screening questions embedded in prose, not in an Upwork section. Brand-new client: no rating, no spend, no history, payment not verified. `Contract-to-hire` flag with boilerplate lines. Job link present. |
| `job_mobile_relayed_airtable_law_dashboard.txt` | Upwork mobile app, 2026-10-06, **relayed through a chat app** | Mobile layout: connects line before *Summary*, no rate range, `6+ months` wording, Upwork-native screening questions, populated *Preferred qualifications*, *Client's recent history* header with no entries, **no job link**. |

## Substitutions

Upwork shows nothing regulated in a job post, but this is a public repository and there is no reason for it to name real businesses or people. Structure is what the tests need, so these were replaced with fictional values:

- Client business names in descriptions (`Northwind Funding`, `Northstar Law Group`)
- First names and freelancer display names in desktop review entries (`Alex`, `Freelancer A.`, `Freelancer B.`)
- Job IDs in the job link (`~0210000000000000000NN`, same length as the originals)

Cities, countries, rates, statistics, dates, skills, product names and public documentation URLs are unchanged.

## Caveats

- The mobile fixture was moved from phone to desktop through a chat app, so typographic quotes and dashes may have been altered in transit and a line could have been dropped (the missing rate range may be the client's choice or a relay artefact). Replace it with a raw mobile paste (email-to-self or a synced note) when one is available, and keep the file name's `relayed` marker until then.
- Upwork changes its layout. When a fixture stops matching a real paste, add a new dated fixture rather than editing an old one, so the parser keeps handling both.
