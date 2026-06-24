# Release Process

Releases are automated via [release-please](https://github.com/googleapis/release-please) and triggered by [conventional commits](https://www.conventionalcommits.org/).

## How it works

```
PR (conventional commits) → merge to main → release PR → merge → git tag → PyPI publish
```

1. **Open a PR** with conventional commit messages in the PR title and/or individual commits (see below).
2. **Merge the PR** into `main`. release-please accumulates merged commits and opens/updates a draft Release PR that bumps the version in `CHANGELOG.md`.
3. **Merge the Release PR** when ready to ship. release-please creates a `vX.Y.Z` git tag and a GitHub release.
4. The **Publish** workflow triggers automatically: builds the wheel, runs a smoke test, and publishes to [PyPI](https://pypi.org/p/physicalai).

The package version is derived from the git tag at build time via [hatch-vcs](https://github.com/ofek/hatch-vcs) — there is no static version in source files.

## Commit message format

```
<type>(<optional scope>): <description>
```

| Type | Version bump | Appears in changelog |
|---|---|---|
| `feat` | minor (`0.x.0`) | ✅ Features |
| `fix` | patch (`0.0.x`) | ✅ Bug Fixes |
| `perf` | patch | ✅ Performance |
| `refactor` | — | ✅ Code Refactoring |
| `docs` | — | ✅ Documentation |
| `test` | — | ✅ Tests |
| `ci` | — | ✅ CI/CD |
| `chore` | — | ✅ Chores |
| `revert` | — | ✅ Reverts |

**Breaking change** → major bump (`x.0.0`): add `!` after the type or a `BREAKING CHANGE:` footer.

```
feat!: drop support for Python 3.10

# or

feat: redesign robot API

BREAKING CHANGE: RobotBase.connect() now requires an explicit timeout argument
```

## For maintainers

### Triggering a release

No manual steps are needed. Once enough PRs with conventional commit messages are merged to `main`, release-please opens a Release PR automatically. Review the generated `CHANGELOG.md`, then merge to publish.

### Forcing a specific version

Edit `.github/.release-please-manifest.json` directly in the Release PR to override the calculated version before merging.

### Manual workflow run

The **Publish** workflow can be triggered manually via `workflow_dispatch` to test the build and smoke-test pipeline without publishing (the publish job is skipped on manual runs).

### PyPI environment

Publishing requires the `pypi` GitHub Actions environment (Settings → Environments). It uses [Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/) — no API token needed.

### GitHub Actions permissions

The `GITHUB_TOKEN` must be allowed to create pull requests:  
Settings → Actions → General → **Allow GitHub Actions to create and approve pull requests** ✅
