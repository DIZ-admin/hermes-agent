# Branching workflow

This fork uses a mirror-first workflow for `main`.

## Policy

- `upstream/main` is the canonical source of truth.
- Local `main` must stay a mirror of `upstream/main`.
- `origin/main` must also stay a mirror of `upstream/main`.
- Do not develop directly on `main`.
- Start every code change from a short-lived branch created from `upstream/main`.
- Open PRs from those short-lived branches into the fork as needed.

## Daily flow

Update the mirror:

```bash
git sync-main
```

Start a new branch:

```bash
git newpr fix/my-change
```

Rebase your branch on the latest upstream main:

```bash
git sync-branch
```

Publish the branch:

```bash
git push -u origin <branch>
```

## What the aliases do

- `git sync-main` fetches `upstream` and `origin`, hard-resets local `main` to `upstream/main`, then force-pushes `origin/main` to keep the fork mirrored.
- `git newpr <branch>` refreshes the mirror and creates a new branch from `upstream/main`.
- `git sync-branch` fetches both remotes and rebases the current branch onto `upstream/main`.

## Safety notes

- Treat `main` as read-only except for mirror maintenance.
- If you have local work in progress, commit it or stash it before running `git sync-main`.
- Keep feature branches narrow and short-lived.
