# Upstream Sync and Runtime Release

This fork tracks `NousResearch/hermes-agent` while serving a live, multi-profile
runtime. An upstream sync is a proposed release, never an in-place update of the
running checkout.

## Branch policy

- `upstream/main` is read-only and is never pushed to.
- `origin/main` is the reviewed fork baseline. Changes arrive only through pull
  requests.
- `sync/upstream-YYYY-MM-DD` is an automatically proposed merge of upstream.
  It is a draft until CI and the release checklist pass.
- `fix/*` and `security/*` branches start from `origin/main` and remain small.
- `release/YYYY.MM.DD-<short-sha>` identifies a tested deployment candidate.

The scheduled **Upstream sync proposal** workflow fetches upstream every Monday,
opens at most one draft proposal, and opens an issue if a merge conflict needs a
human resolution. It never merges a PR, restarts a service, or changes a deployed
checkout.

## Initial catch-up

Use a separate worktree. Do not run these commands from the checkout under
`~/.hermes/hermes-agent`, because it is loaded by LaunchAgents.

```bash
git fetch origin upstream --prune
git worktree add -b sync/upstream-YYYY-MM-DD ../hermes-upstream-sync origin/main
cd ../hermes-upstream-sync
git merge --no-ff upstream/main
```

Resolve conflicts in the sync worktree, run the checks below, push the branch,
and open a draft PR into `origin/main`. If the merge is too large to review as
one change, first sync to an upstream release tag, then make subsequent weekly
merges from `upstream/main`.

## Required checks before merging a sync PR

1. GitHub CI's `All required checks pass` gate is green.
2. Review the upstream release notes, dependency and lockfile changes, config
   migrations, and gateway/platform changes.
3. In the isolated worktree, run the affected test slices through
   `scripts/run_tests.sh`; do not invoke pytest directly.
4. Run `hermes doctor` against a non-production test home and record the result.
5. Create a deployment candidate tag after PR merge:

```bash
git tag -a release/YYYY.MM.DD-<short-sha> -m "Validated runtime candidate"
git push origin release/YYYY.MM.DD-<short-sha>
```

## Deployment and rollback

Deploy only in a maintenance window and record the exact commit in the manifest.

1. Save the current runtime SHA and confirm all active profiles are healthy.
2. Test the candidate on the `dev` profile first.
3. Confirm gateway, dashboard, Workspace and Telegram health.
4. Roll out `family`, `home`, and `partner` one at a time; stop on any failure.
5. If a check fails, restore the previous SHA and restart only the affected
   service. Never use `git reset --hard` on a live checkout.

Use this manifest for every release:

```text
candidate SHA:
previous SHA:
release tag:
upstream base SHA:
CI run URL:
dev validation:
family validation:
home validation:
partner validation:
rollback decision / reason:
operator:
timestamp (UTC):
```

## Repository hygiene

- Run `git fetch --all --prune` before creating a release branch.
- Remove a worktree only after its PR is merged or explicitly abandoned and its
  working tree is clean.
- Preserve an uncertain branch or stash; remove only generated artifacts and
  clearly confirmed merged worktrees.
- Keep `origin/main` protected: require pull requests and the CI aggregate
  check, disallow force pushes and branch deletion.
