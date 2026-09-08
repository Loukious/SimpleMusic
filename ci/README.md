# SimpleMusic fork CI

This fork tracks upstream [maxrave-dev/SimpMusic](https://github.com/maxrave-dev/SimpMusic)
without ever rebasing. The `dev` branch is **regenerated** on every sync:

```
upstream dev ──clone──▶ fresh checkout
                         │
              ci/transform.py   (deterministic rebrand: user-visible text only,
                         │       packages / schemes / infra URLs stay upstream's)
              ci/forkify.py     (repoint to Loukious/SimpleMusic, GitHub update
                         │       check, direct-APK download button)
              vendor `core`     (the submodule becomes plain files — the fork
                         │       cannot push into maxrave-dev/core)
              replace CI        (upstream workflows out, fork workflows in)
                         │
                force-push ──▶ fork dev ──▶ version changed? ──▶ FOSS APK release
```

Because the rebrand is a script re-applied to a *pristine* upstream checkout,
upstream edits to any renamed line are absorbed silently — a rebase of the
same diff would conflict on every single one.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `fork-sync.yml` | daily cron + manual | Rebuild `dev` from upstream, rebrand, vendor `core`, force-push, then call the release job |
| `fork-release.yml` | called by sync, push to `dev`, manual | Build the FOSS APK (`isFullBuild=false`), tag `v<version-name>`, publish a GitHub Release with the APK as an asset. Skips itself when the tag already exists, so it only actually builds when the version changed |

The release chain is a **reusable-workflow call, not a pushed event**: the
default `GITHUB_TOKEN` cannot dispatch `workflow_dispatch` events (403
"Resource not accessible by integration") and — the subtler trap — a
`GITHUB_TOKEN` push does **not** trigger `on: push` workflows at all
(GitHub's recursion guard). So `fork-sync.yml` finishes by calling
`fork-release.yml` as a `workflow_call` job in the same run, against the dev
HEAD it just force-pushed. Pushes made with real user credentials still
trigger the release workflow directly.

The in-app update checker (`core/…/Ytmusic.kt`) queries
`api.github.com/repos/Loukious/SimpleMusic/releases/latest`; the update
dialog's Download button opens the release's `.apk` asset directly.

## One-time setup

1. **Create the fork repo** (a fresh repo, not a GitHub fork, so GitHub's
   fork UI doesn't interfere): `Loukious/SimpleMusic`.

2. **Push this branch as `dev` and make it the default branch** (scheduled
   workflows only fire from the default branch):

   ```bash
   git remote add fork https://github.com/Loukious/SimpleMusic.git
   git push fork dev
   # Settings → Branches → default branch → dev
   ```

3. **Signing key** (recommended — see below): generate a keystore and add the
   secrets. Then run **Actions → Fork sync → Run workflow** once to verify the
   whole chain, and **Fork release** for the first release.

## Stable APK signing

Without secrets, the release workflow generates a throwaway keystore each
run. Android refuses to install an update whose signature differs from the
installed app, so every release would require uninstall + reinstall. Fix it
once:

```bash
keytool -genkeypair -v \
  -keystore simplemusic.jks \
  -alias simplemusic \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -storepass '<KEY_STORE_PASSWORD>' -keypass '<KEY_PASSWORD>' \
  -dname "CN=SimpleMusic, OU=Fork, O=Loukious, C=US"

base64 -w0 simplemusic.jks > simplemusic.jks.b64
```

Add four repository secrets (**Settings → Secrets and variables → Actions**):

| Secret | Value |
|---|---|
| `BASE_64_SIGNING_KEY` | contents of `simplemusic.jks.b64` |
| `KEY_STORE_PASSWORD` | the `-storepass` |
| `ALIAS` | `simplemusic` |
| `KEY_PASSWORD` | the `-keypass` |

Keep `simplemusic.jks` somewhere safe (not in the repo) — it is the only way
to ship an update your users can install in place.

## When upstream changes something the scripts touch

`ci/forkify.py` applies its code edits with **exact-match verification**: if
upstream refactors `Ytmusic.kt`, `UpdateRepositoryImpl.kt`, `UpdateData.kt`
or the update dialog in `App.kt`, the sync run **fails loudly** with the
pattern that no longer matches instead of silently shipping a half-patched
build. When that happens, update the `EXACT_EDITS` block in `ci/forkify.py`
against the new upstream source — it is the only maintenance this fork needs.

`ci/transform.py` never fails: it is pure string replacement and re-applies
cleanly whatever upstream does.
