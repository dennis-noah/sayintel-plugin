---
name: sayintel-brief
description: Get a sourced brief on a person before a meeting: what they said in public, their company now, watch-outs and three questions to ask.
argument-hint: <full name> [company or LinkedIn URL]
---

Brief me on this person before a meeting: $ARGUMENTS

Use only the read and write tools of the `sayintel` MCP server. This command does not send outreach. A brief can email the account owner when it is ready; keep that off unless the user asks for the email.

1. Call `whoami`.
2. You need a full name plus a company or a LinkedIn URL. A name alone is refused, so ask for the missing piece before any lookup that would spend a credit.
3. If the user named a campaign, or the person may already be a lead in one, call `search_speakers`. `campaign_id` is optional: pass it when a campaign is in scope, and otherwise search by `name`. Each row's identifier is `id`, not `speaker_id`. If exactly one row fits, keep that `id` and the full name. If several fit, ask which. If none fit, continue with the name and company or LinkedIn URL.
4. `brief_person` spends 1 credit. Say so in one line and go ahead when the user agrees.
5. Call `brief_person` with `name` every time, `email_when_ready: false` unless the user asked to be emailed, plus `speaker_id` set to the row's `id` when you have one, or `company` or `linkedin_url`. It returns a `brief_id` and a status.
6. Poll `get_meeting_brief(brief_id)` every 15 seconds only while status is `queued` or `researching`. On `failed`, stop and relay `error`. On `ready`, stop and present the brief. If it is still queued or researching after a few minutes, say so instead of polling without a limit.
7. Present the brief: their public statements, the company right now, career, watch-outs and the three questions. Keep every source link. Do not add claims the brief does not carry.
