---
name: sayintel-review
description: Review a sayintel campaign's drafts, find what fails QA and fix it with rewrites or edits. Never approves or sends.
argument-hint: [campaign name or id]
---

Review the drafts of a sayintel campaign: $ARGUMENTS

Use only the read and write tools of the `sayintel` MCP server. Nothing sends from this connection, and you never approve on the user's behalf.

1. Call `whoami`. If no campaign was named, call `list_campaigns` and ask which one. On an agency account, stay inside that campaign's client the whole time.
2. Call `campaign_stats(campaign_id)`. Call `get_draft_qa` twice and page each with `next_cursor` until `has_more` is false. `bucket_counts` is only the current page, so add `ready_to_send` across every page of the unfiltered call.
   - `only_failing: true` for rewrites and human review. This page omits approvable drafts.
   - No `only_failing` to count sequences that cleared QA (`bucket` `ready_to_send`, `recommended_action` `push_approved`).
3. Report the summed `ready_to_send` count as sequences that cleared QA. From the failing-only pages, count how many need a rewrite, how many need a human, and the most common fail codes. If you also mention `campaign_stats` `supply`, label `supply.ready` as leads a person has already approved and that are cleared to send, and `supply.awaitingApproval` as full sequences still waiting on a person. `supply.ready` is not the QA-cleared count. If `supply` is null, say that read failed and do not invent a zero.
4. Work person by person from each speaker's `recommended_action` on the failing pages:
   - `request_rewrite`: group the people by fail code and propose one `request_rewrite(campaign_id, instruction, speaker_ids)` per group, built from their fix hints. Show the instruction and the count, then run it when the user agrees.
   - `human_review`: show the user the draft with `list_messages` and the reason. Let them decide. If they want a change, use `update_message`, then `rescore_drafts` on that person.
   - `wait`: QA has not finished, or the person is skipped or sent. Leave it.
   - `push_approved`: the sequence is ready. Leave it; pushing is the user's step in sayintel.

   Inside a person's drafts, each `fixes[].action` says what to do with one slot. `rescore` means the text was hand-edited: run `rescore_drafts(campaign_id, speaker_ids)`. `human_review` is the user's call, as above. `none` means leave the slot alone. Every other action (`rewrite_opener`, `rewrite_cta`, `rewrite_body`, `redraft`, `vary_phrasing`, `shorten` and the rest) is a hint for `request_rewrite`: put its text in the instruction.

5. To look closer at one person, use `get_speaker_dossier(speaker_id)`. To drop someone, `set_speaker_selected(speaker_id, false)` after the user says so.
6. End with what changed and what is left. Approving and pushing to HeyReach happen in sayintel, by the user.
