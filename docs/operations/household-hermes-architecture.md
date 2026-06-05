# Household Hermes Architecture SSOT

Status: current foundation + target architecture
Last verified: 2026-06-05
Scope: local macOS host `/Users/hermes`, shared Hermes source tree, Hermes profiles used for household/family/home assistants.

This document is the source of truth for the household multi-profile deployment shape. It intentionally records secret ownership and key names only; never paste token values, OAuth blobs, passwords, chat IDs, or raw `.env` contents here.

## Goal

Run a role-separated Hermes household platform where each role has an isolated profile, its own Telegram bot, its own gateway process, and its own memory/session store. Privileged development/admin capabilities stay in the `dev` profile. Household profiles run with constrained runtimes and explicit gates, especially for physical-world home automation.

Target invariant:

```text
1 Hermes profile = 1 Telegram bot = 1 gateway service = 1 memory/session store
```

Shared code is acceptable; shared profile state is not.

## Current topology

Shared source/runtime:

```text
/Users/hermes/.hermes/hermes-agent
```

Profile homes:

```text
/Users/hermes/.hermes/profiles/<profile>/
```

The legacy/default profile lives at:

```text
/Users/hermes/.hermes/
```

Current profile registry:

- `default`
  - Role: legacy/default profile; not the household control plane.
  - Gateway: stopped.
  - Runtime: local terminal backend.
  - Memory: enabled; user profile enabled.
- `dev`
  - Role: admin/development profile for Hermes source work, diagnostics, infrastructure repair, git/GitHub, and privileged host work.
  - Gateway: running manually, not as launchd service.
  - Runtime: local terminal backend.
  - Memory: enabled; user profile enabled.
  - Secret boundary: may hold admin-only keys such as sudo, KeePass, GitHub, and the dev Telegram bot. Do not clone `dev` into household profiles.
- `family`
  - Role: shared family assistant.
  - Gateway: running as macOS LaunchAgent `ai.hermes.gateway-family`.
  - Runtime: Docker terminal backend.
  - Memory: enabled; user profile disabled.
  - Privacy/security: secret redaction enabled; PII redaction enabled.
- `home`
  - Role: home/automation assistant.
  - Gateway: running as macOS LaunchAgent `ai.hermes.gateway-home`.
  - Runtime: Docker terminal backend.
  - Memory: enabled; user profile disabled.
  - Privacy/security: secret redaction enabled; PII redaction enabled.
  - Current automation posture: actuation gated; `homeassistant` and `vision` are disabled and image input is off until a policy/integration pass approves them.
- `household-template`
  - Role: non-admin template for future household profiles.
  - Gateway: stopped.
  - Runtime: Docker terminal backend.
  - Memory: enabled; user profile disabled.
  - Privacy/security: secret redaction enabled; PII redaction enabled.
  - Intended use: clone role profiles from this template, never from `dev`.
- `devops`
  - Role: future operational specialist profile.
  - Gateway: stopped.
  - Runtime: Docker terminal backend.
  - Memory: enabled; user profile enabled.
- `research`
  - Role: future research specialist profile.
  - Gateway: stopped.
  - Runtime: Docker terminal backend.
  - Memory: enabled; user profile enabled.

Model/provider baseline, verified across listed profiles:

```text
provider: openai-codex
model: gpt-5.5
```

## Gateway supervision

Production household gateways should be launchd-managed on macOS:

```text
~/Library/LaunchAgents/ai.hermes.gateway-<profile>.plist
```

Current running services:

- `family`: launchd LaunchAgent, `state = running`, `HERMES_HOME=/Users/hermes/.hermes/profiles/family`
- `home`: launchd LaunchAgent, `state = running`, `HERMES_HOME=/Users/hermes/.hermes/profiles/home`
- `dev`: running manually; acceptable for development, but not a permanent production supervision pattern.

macOS status check rule:

- Do not rely on `launchctl list <label>` alone.
- Cross-check `hermes --profile <profile> gateway status`, `launchctl print gui/$(id -u)/<label>`, `ps`, and fresh gateway logs when status looks contradictory.
- Hermes now has a local fix for the launchd domain quirk where `launchctl list <label>` can miss a running profile LaunchAgent that is visible in `gui/<uid>/<label>`.

## Capability tiers

### Tier 0: `dev` / admin

Allowed:

- local terminal backend
- Hermes source changes
- git/GitHub workflow
- gateway/profile diagnostics
- host repair and sudo when explicitly needed
- KeePass/admin credential workflows when scoped to the owner

Forbidden for clones:

- do not copy this profile wholesale into family/home/child/partner profiles
- do not share its `.env`, Telegram token, sudo/KeePass entries, local runtime assumptions, or memory store

### Tier 1: `family` / shared household assistant

Allowed:

- family logistics, planning, shared notes, non-sensitive reminders
- Docker terminal backend only
- shared family memory
- model/web/file tools only as configured and safe for household use

Requires caution:

- private personal topics should move to a personal profile
- no host maintenance, sudo, KeePass, Docker daemon administration, or GitHub admin work

### Tier 2: `home` / automation assistant

Allowed now:

- explain home state/design
- maintain device/room/scene notes
- read-only automation planning
- Docker runtime

Gated before activation:

- Home Assistant, Hue, locks, alarms, cameras, climate extremes, network/router changes, purchases, and anything that changes the physical world.

Current default:

```text
homeassistant: disabled
vision: disabled
image_input_mode: off
```

### Tier 3: future `partner` / `child-*` profiles

Expected defaults:

- clone from `household-template`
- own Telegram bot and allowed users/chats
- Docker runtime
- no sudo/KeePass/admin host access
- minimal tool surface
- role-specific memory boundary
- child profiles should disable dangerous tools and use restricted web/media policy

## Credential and secret boundaries

Document key ownership, not values.

Admin-only keys stay in `dev` unless explicitly approved for another role:

- `SUDO_PASSWORD`
- `SUDO_ASKPASS`
- `KEEPASSXC_*`
- broad `GITHUB_TOKEN`
- dev Telegram bot token/home channel

Household profiles may have only role-scoped operational keys:

- profile-specific `TELEGRAM_BOT_TOKEN`
- profile-specific `TELEGRAM_ALLOWED_USERS`
- profile-specific `TELEGRAM_HOME_CHANNEL`
- model/search credentials approved for household use
- Docker runtime configuration keys

Current high-level env-key observations:

- `dev` has admin-capable key names including `SUDO_*`, `KEEPASSXC_*`, `GITHUB_TOKEN`, and Telegram keys.
- `family` and `home` have Telegram/model/search/Docker runtime keys, with no sudo/KeePass/GitHub key names observed.
- `household-template` has model/search/Docker runtime keys and no Telegram bot token/home channel, which is correct for a template.

Every profile `.env` should be mode `0600`.

## Memory/session isolation

Current invariant:

```text
profile-local config + profile-local .env + profile-local logs + profile-local sessions + profile-local memory
```

Rules:

- `dev` memory may include admin/operator preferences.
- `family` memory is shared family memory, not a private diary.
- `home` memory is device/room/scene/automation memory, not personal memory.
- Future personal profiles should not share memory stores with `family` or `dev`.
- Future child profiles should use minimal, supervised memory.

## Operations runbook

### Inventory

```bash
cd /Users/hermes/.hermes/hermes-agent
./venv/bin/hermes profile list
for p in dev family home household-template devops research default; do
  ./venv/bin/hermes --profile "$p" gateway status
 done
```

### Verify household launchd services

```bash
uid=$(id -u)
launchctl print "gui/$uid/ai.hermes.gateway-family"
launchctl print "gui/$uid/ai.hermes.gateway-home"
```

Expected for running services:

```text
state = running
HERMES_HOME => /Users/hermes/.hermes/profiles/<profile>
```

### Restart one profile gateway

```bash
cd /Users/hermes/.hermes/hermes-agent
./venv/bin/hermes --profile family gateway restart
./venv/bin/hermes --profile family gateway status
```

Use the target profile name deliberately; do not rely on the ambient active profile for cross-profile operations.

### Add a new household profile

1. Clone/create from `household-template`, not from `dev`.
2. Set model/provider if not inherited.
3. Add only the new profile's Telegram token, allowed users, and home channel.
4. Confirm `.env` mode `0600`.
5. Smoke-test model access before installing gateway.
6. Install/start gateway.
7. Validate Telegram identity with Bot API `getMe` without printing the token.
8. Validate memory isolation.
9. Update this SSOT and the audit script expectations.

## Launch acceptance checklist

A profile is household-production-ready when all of these are true:

- [ ] It has a clear role and owner.
- [ ] It was created from `household-template` or equivalent non-admin baseline.
- [ ] It has a unique Telegram bot token and allowed-users/home-channel configuration.
- [ ] Its gateway is launchd-managed if it must stay online.
- [ ] Its terminal backend matches its role; household profiles use Docker unless explicitly justified.
- [ ] It has no admin-only key names unless explicitly approved and documented.
- [ ] Secret redaction is enabled.
- [ ] PII redaction is enabled for shared household profiles.
- [ ] Memory scope is documented.
- [ ] Dangerous actions are denied, dry-run, or confirmation-gated.
- [ ] Model smoke test passed.
- [ ] Gateway status and logs are clean.
- [ ] Telegram inbound/outbound delivery works.
- [ ] The redacted household audit script passes or only reports documented exceptions.

## Known current gaps

- `dev` is running manually, not as a launchd service. This is acceptable for now, but not production supervision.
- `family` still has broad image input/tool defaults; decide whether family should keep image support or follow the same strict visual-input policy as `home`.
- `devops` and `research` have Telegram/GitHub-capable env key names while stopped. Before activating them, revalidate whether those keys are intentional for their roles.
- `default` remains local/admin-like and should not be used as a household template.
- `home` automation remains deliberately gated; Home Assistant/Hue/etc. should not be enabled until the action policy is written and accepted.

## Verification artifact

Run the redacted audit:

```bash
cd /Users/hermes/.hermes/hermes-agent
./venv/bin/python scripts/audit_household_profiles.py
```

The script must emit no secret values. It reports profile topology, config booleans, env key names, launchd status, and invariant findings.
