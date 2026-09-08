#!/usr/bin/env python3
"""Fork-specific modifications applied AFTER transform.py.

These are the changes that make the tree a Loukious/SimpleMusic fork rather
than just a rebranded copy:

  1. Repoint every maxrave-dev/SimpMusic reference to Loukious/SimpleMusic
     (README, conveyor vcs-url, Discord RPC, review/credit screens, ...).
     This also covers the in-app update-check URL in core's Ytmusic.kt.
  2. Give UpdateData the release's APK download URL and have the update
     dialog's Download button open it directly instead of the upstream
     website.

Every code replacement is EXACT and verified: if upstream edits any of the
touched regions, this script exits non-zero with the failing pattern so the
CI run fails loudly instead of silently shipping a half-patched build.

Line-ending agnostic: patterns are written with \n and matched against a
\n-normalised copy; the file's original ending (LF or CRLF) is preserved.

Usage: python forkify.py <repo-root>
"""
import os
import sys

FORK_REPOINTS = [
    ("maxrave-dev/SimpleMusic", "Loukious/SimpleMusic"),
    ("maxrave-dev%2FSimpleMusic", "Loukious%2FSimpleMusic"),
]

EXACT_EDITS = [
    # ---- UpdateData gains the APK download URL (core) ----
    (
        "core/domain/src/commonMain/kotlin/com/maxrave/domain/data/model/update/UpdateData.kt",
        """data class UpdateData(
    val tagName: String,
    val releaseTime: String?,
    val body: String,
)""",
        """data class UpdateData(
    val tagName: String,
    val releaseTime: String?,
    val body: String,
    /** Direct download URL of the release's primary APK asset, when the release carries one. */
    val downloadUrl: String? = null,
)""",
    ),
    # ---- UpdateRepositoryImpl picks the APK asset (core) ----
    (
        "core/data/src/commonMain/kotlin/com/maxrave/data/repository/UpdateRepositoryImpl.kt",
        """import com.maxrave.kotlinytmusicscraper.YouTube
""",
        """import com.maxrave.kotlinytmusicscraper.YouTube
import com.maxrave.kotlinytmusicscraper.models.simpmusic.Asset
""",
    ),
    (
        "core/data/src/commonMain/kotlin/com/maxrave/data/repository/UpdateRepositoryImpl.kt",
        """                                body = response.body ?: "",
                            ),
                        ),
                    )
                }.onFailure {
                    emit(Resource.Error<UpdateData>(it.localizedMessage ?: "Unknown error"))
                }
        }.flowOn(Dispatchers.IO)
""",
        """                                body = response.body ?: "",
                                downloadUrl = pickApkDownloadUrl(response.assets),
                            ),
                        ),
                    )
                }.onFailure {
                    emit(Resource.Error<UpdateData>(it.localizedMessage ?: "Unknown error"))
                }
        }.flowOn(Dispatchers.IO)
""",
    ),
    (
        "core/data/src/commonMain/kotlin/com/maxrave/data/repository/UpdateRepositoryImpl.kt",
        """        }.flowOn(Dispatchers.IO)
}""",
        """        }.flowOn(Dispatchers.IO)

    private fun pickApkDownloadUrl(assets: List<Asset?>?): String? =
        assets
            ?.filterNotNull()
            ?.filter { it.name?.endsWith(".apk", ignoreCase = true) == true }
            ?.maxByOrNull { it.size ?: 0 }
            ?.browserDownloadUrl
}""",
    ),
    # ---- update dialog: direct APK download instead of the website ----
    (
        "composeApp/src/commonMain/kotlin/com/maxrave/simpmusic/App.kt",
        """                        confirmButton = {
                            TextButton(
                                onClick = {
                                    shouldShowUpdateDialog = false
                                    viewModel.showedUpdateDialog = false
                                    openUrl("https://simpmusic.org/download")
                                },
                            ) {""",
        """                        confirmButton = {
                            TextButton(
                                onClick = {
                                    val url =
                                        response.downloadUrl
                                            ?: "https://github.com/Loukious/SimpleMusic/releases/latest"
                                    shouldShowUpdateDialog = false
                                    viewModel.showedUpdateDialog = false
                                    openUrl(url)
                                },
                            ) {""",
    ),
]

# Removal edits: delete a block, fail loudly if the block's anchor changed.
# (path, exact block to remove including its trailing blank line)
REMOVE_EDITS = [
    # upstream CLAUDE.md mandates Vietnamese translation parentheticals in
    # every response — the fork's maintainer removed it from the working
    # tree, so CI must remove it too or dev would drift back every sync.
    (
        "CLAUDE.md",
        """
## 🌐 Language Rule

**Response language**: Always respond in **English**, and after each sentence, add a **Vietnamese translation in parentheses**.
Example: "Hello, how are you? (Xin chào, bạn khỏe không?)"

This applies to all conversations in this project. The user is using Max plan so token cost is not a concern.
""",
    ),
]

def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    failures = []

    # blanket repoint over all text files
    repointed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", ".gradle", ".idea", "build", "mpv-natives", "ci")]
        for name in filenames:
            # fork-owned CI files reference upstream by name on purpose
            if name.startswith("fork-") and dirpath.replace(os.sep, "/").endswith(".github/workflows"):
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
            if not any(marker in data for marker in (b"maxrave-dev/SimpleMusic", b"maxrave-dev%2FSimpleMusic")):
                continue
            text = data.decode("utf-8", errors="surrogateescape")
            for old, new in FORK_REPOINTS:
                text = text.replace(old, new)
            with open(path, "wb") as fh:
                fh.write(text.encode("utf-8", errors="surrogateescape"))
            repointed += 1

    # exact code edits, verified
    edited = 0
    for rel, old, new in EXACT_EDITS:
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                raw = fh.read()
        except OSError as e:
            failures.append(f"{rel}: cannot read ({e})")
            continue
        crlf = "\r\n" in raw
        norm = raw.replace("\r\n", "\n")
        if new in norm:
            continue  # already applied (idempotent)
        if old not in norm:
            failures.append(f"{rel}: pattern not found — upstream changed?\n---\n{old[:300]}\n---")
            continue
        norm = norm.replace(old, new, 1)
        out = norm.replace("\n", "\r\n") if crlf else norm
        with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(out)
        edited += 1

    # block removals, verified (idempotent: block gone = already applied)
    removed = 0
    for rel, block in REMOVE_EDITS:
        path = os.path.join(root, rel)
        try:
            with open(path, "r", encoding="utf-8", errors="surrogateescape", newline="") as fh:
                raw = fh.read()
        except OSError as e:
            failures.append(f"{rel}: cannot read ({e})")
            continue
        crlf = "\r\n" in raw
        norm = raw.replace("\r\n", "\n")
        if block not in norm:
            # distinguish "already removed" from "anchor changed"
            probe = block.strip().splitlines()[0]
            if probe in norm:
                failures.append(f"{rel}: removal block changed — upstream edited it?\n---\n{block[:300]}\n---")
            continue
        norm = norm.replace(block, "", 1)
        # collapse the double blank line the removal leaves behind
        norm = norm.replace("\n\n\n", "\n\n", 1)
        out = norm.replace("\n", "\r\n") if crlf else norm
        with open(path, "w", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(out)
        removed += 1

    print(f"forkify: repointed {repointed} files, applied {edited} code edits, "
          f"{removed} removals")
    if failures:
        print("\nFAILED PATTERNS:", file=sys.stderr)
        for f in failures:
            print(f"  * {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
