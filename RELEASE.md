# Release Workflow

OpenSwarm releases use one normal path: `Build TUI Binaries` builds the required assets, publishes the GitHub Release, then publishes `@vrsen/openswarm` to npm in the same workflow run. The release tag, npm package version, lockfile version, and Python project metadata must use the same semver version.

## Release Inputs

- Source version: `X.Y.Z` or `X.Y.Z-prerelease` in `package.json`
- Matching metadata: `package-lock.json` and `pyproject.toml`
- GitHub tag format: `vX.Y.Z` or `vX.Y.Z-prerelease`
- GitHub release assets:
  - `agentswarm-darwin-arm64`
  - `agentswarm-darwin-x64`
  - `agentswarm-darwin-x64-baseline`
  - `agentswarm-linux-arm64`
  - `agentswarm-linux-arm64-musl`
  - `agentswarm-linux-x64`
  - `agentswarm-linux-x64-baseline`
  - `agentswarm-linux-x64-baseline-musl`
  - `agentswarm-linux-x64-musl`
  - `agentswarm-windows-arm64.exe`
  - `agentswarm-windows-x64.exe`
  - `agentswarm-windows-x64-baseline.exe`

## Release Steps

1. Bump `package.json`, `package-lock.json`, and `pyproject.toml` to the same version.
2. Merge the version bump to `main`.
3. Run the `Build TUI Binaries` workflow from the `main` branch in GitHub Actions. Leave `version` blank to use `package.json`, or pass the exact version without the `v` prefix.
4. Confirm the workflow creates the matching GitHub Release with all required binary assets.
5. Let the downstream npm publish job in the same workflow publish `@vrsen/openswarm` from the release tag. Stable versions publish to `latest`; prereleases publish to the prerelease label such as `rc`.

Pushing a matching version tag also runs the binary release workflow. The manual workflow is the preferred path because it builds assets, publishes the GitHub Release, and publishes npm in one run.

GitHub releases created with `${{ github.token }}` do not start separate `on: release` workflows. `Fallback Publish npm on Release` exists only for releases that are published manually, externally, or through an API token that can trigger release workflows. It is not the normal release path.

## Release Gates

- The binary release workflow fails if the tag/input version does not match `package.json`, `package-lock.json`, and `pyproject.toml`.
- The npm publish job fails if `NPM_TOKEN` is missing, versions do not match, or the GitHub Release is missing any required TUI binary asset.
- The fallback npm publish workflow runs the same key checks for manually or externally published releases, including prereleases.
- The npm package uses `publishConfig.access=public` so scoped publishes do not depend on CLI flags alone.
