# sayintel for Cursor and Claude Code

Conference outbound from your agent. Point sayintel at a conference's speaker or agenda page and it reads the roster, qualifies each person against your ICP, and drafts a 3-message LinkedIn sequence per lead. This plugin lets Cursor or Claude Code run that loop with you: create the campaign, follow the run, review the drafts and fix what fails QA.

Nothing sends from this plugin. It connects with read and write access only. Sending needs a send-scoped token that only the account owner mints in sayintel, and a person still arms the HeyReach campaign.

## What is inside

One folder works in both hosts.

| Path                                 | What it is                                                                         | Cursor | Claude Code |
| ------------------------------------ | ---------------------------------------------------------------------------------- | ------ | ----------- |
| `.cursor-plugin/plugin.json`         | Cursor manifest                                                                    | yes    |             |
| `.claude-plugin/plugin.json`         | Claude Code manifest                                                               |        | yes         |
| `.claude-plugin/marketplace.json`    | Lets `/plugin marketplace add` install from this repo                              |        | yes         |
| `mcp.json`                           | The `sayintel` MCP server, `https://sayintel.com/mcp` (Agent Plugins 1.0.0 schema) | yes    | yes         |
| `skills/sayintel/SKILL.md`           | The sayintel loop and its rules                                                    | yes    | yes         |
| `commands/`                          | Three commands, listed below                                                       | yes    | yes         |
| `rules/sayintel.mdc`                 | Short safety rule for any sayintel tool call                                       | yes    |             |
| `assets/logo.png`, `assets/logo.svg` | The Si mark, copied from the sayintel app                                          | yes    |             |

Commands:

| Cursor                                         | Claude Code                | Does                                                                 |
| ---------------------------------------------- | -------------------------- | -------------------------------------------------------------------- |
| `/sayintel-new-conference <url> [client]`      | `/sayintel:new-conference` | Previews the cost, creates the campaign on your yes, follows the run |
| `/sayintel-review [campaign]`                  | `/sayintel:review`         | Finds failing drafts and fixes them with rewrites or edits           |
| `/sayintel-brief <name> [company or LinkedIn]` | `/sayintel:brief`          | A sourced brief on a person before a meeting (1 credit)              |

Every command uses read and write tools only, and asks before anything that spends credits.

## Sign-in

The server is `https://sayintel.com/mcp`. Your editor opens a browser to sign in to sayintel and approve the connection (in Claude Code, start it from `/mcp`). No key goes in the plugin, and you never paste one into chat.

**Headless use (CI, scripts, a server with no browser).** sayintel also has a bearer door at `https://sayintel.com/api/public/mcp` that takes a personal token you mint in sayintel under Connections. This plugin does not configure it. If you need it, add it yourself in your own MCP settings with the token in a header, keep the token out of any repo, and mint it without the send scope unless you mean to send.

## Install in Cursor

From the marketplace, once listed: open **Customize**, search for sayintel, select **Install**.

To test locally before that:

```bash
mkdir -p ~/.cursor/plugins/local
cp -R . ~/.cursor/plugins/local/sayintel
```

Copy the folder rather than symlinking it: Cursor skips symlinks that point outside `~/.cursor/plugins/local`. Then run **Developer: Reload Window**, open **Customize**, and check that the `sayintel` skill, the `sayintel` rule, the three commands and the `sayintel` MCP server are there. Enable the server and sign in when asked. On Enterprise, an admin must turn on **Allow Local Plugin Imports**.

## Install in Claude Code

From this repository:

```text
/plugin marketplace add dennis-noah/sayintel-plugin
/plugin install sayintel@sayintel
```

Then run `/mcp`, pick `plugin:sayintel:sayintel`, and sign in. To test a local copy instead: `claude --plugin-dir ./` from this folder.

Check it with:

```bash
claude plugin validate --strict .
```

## The loop the skill teaches

1. `whoami` for the signed-in account and its clients.
2. `list_campaigns`, or `create_campaign` with a conference URL (dry run first for the cost).
3. `get_run_status` every 15 to 30 seconds while the pipeline scrapes, qualifies, researches and drafts.
4. Review with `campaign_stats`, `search_speakers`, `get_speaker_dossier`, `list_messages`, `get_draft_qa`.
5. Curate with `request_rewrite`, `update_message` then `rescore_drafts`, and `set_speaker_selected`.

Approving and pushing to HeyReach stay with the user, in sayintel.

**Agencies:** on an account with clients, every new campaign names its client (`client_id`) or says it is for your own company (`own_company: true`). The agent asks when you did not say, and never carries one client's pitch, ICP, people or wording into another client's campaign.

## Support

Docs: https://sayintel.com/docs/mcp. Privacy: https://sayintel.com/privacy. Terms: https://sayintel.com/terms.

## License

MIT. See `LICENSE`.
