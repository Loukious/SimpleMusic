#!/usr/bin/env python3
"""Deterministic SimpMusic -> SimpleMusic rebrand transform.

Runs on a PRISTINE upstream checkout (parent repo or core submodule) and
produces exactly the "user-visible rebrand, identifiers intact" state:

  Phase 1 — blanket word-boundary rename of the three casings.
            '_' counts as a word character, so compound identifiers
            (enjoying_simpmusic, simpmusic_lyrics, SIMPMUSIC const) are
            NEVER touched — only whole words are renamed.

  Phase 2 — precise reverts of everything that is an identifier, an app
            identity value, or upstream infrastructure rather than
            display text: package paths, the deep-link scheme literals,
            the simpmusic.org / simpmusic-files hosts, the desktop data
            directory, proguard keep rules, generated-Res imports.

Usage: python transform.py <repo-root>
Exits non-zero if a file cannot be read. Idempotent: running it on an
already-transformed tree is a no-op.
"""
import os
import sys

TEXT_EXT = (
    ".kt", ".kts", ".java", ".xml", ".pro", ".json", ".toml", ".conf",
    ".bat", ".sh", ".properties", ".yml", ".yaml", ".md", ".gradle",
    ".txt", ".gitmodules", ".editorconfig",
)
TEXT_NAMES = {"conveyor.conf", "gradlew", "gradlew.bat", "LICENSE", "README"}

# --- Phase 1: byte-level word-boundary rename -----------------------------

PATTERNS = [
    (b"SimpMusic", b"SimpleMusic"),
    (b"simpmusic", b"simplemusic"),
    (b"SIMPMUSIC", b"SIMPLEMUSIC"),
]


def is_word_byte(b: int) -> bool:
    return (48 <= b <= 57) or (65 <= b <= 90) or (97 <= b <= 122) or b == 95


def replace_word(data: bytes, old: bytes, new: bytes) -> bytes:
    out = bytearray()
    i = 0
    n = len(data)
    ln = len(old)
    while i < n:
        j = data.find(old, i)
        if j == -1:
            out.extend(data[i:])
            break
        start_ok = j == 0 or not is_word_byte(data[j - 1])
        end = j + ln
        end_ok = end >= n or not is_word_byte(data[end])
        if start_ok and end_ok:
            out.extend(data[i:j])
            out.extend(new)
            i = end
        else:
            out.extend(data[i:j + ln])
            i = j + ln
    return bytes(out)

# --- Phase 2: identifier / identity / infrastructure reverts --------------
# Applied to decoded text. Order: simplemusic-files / simplemusic.org stay
# ahead of the generic quoted-literal revert so domains are restored first.

REVERTS = [
    # dotted package paths (dots are non-word bytes, so phase 1 renamed them)
    ("com.maxrave.simplemusic", "com.maxrave.simpmusic"),
    ("org.simplemusic", "org.simpmusic"),
    # generated resources Res class package follows the gradle namespace
    ("simplemusic.composeapp", "simpmusic.composeapp"),
    # remaining dotted FQNs: com.simplemusic.media_jvm, models.simplemusic,
    # com.simplemusic.lyrics.parser (proguard + imports)
    (".simplemusic.", ".simpmusic."),
    # upstream infrastructure hosts (mpv natives, remote-config, registry)
    ("maxrave-dev/simplemusic-files", "maxrave-dev/simpmusic-files"),
    # the repo's name in comments (cosmetic but keeps diffs against the
    # working tree identical)
    ("(simplemusic-files)", "(simpmusic-files)"),
    # upstream website / deep-link / lyrics / chart hosts
    ("simplemusic.org", "simpmusic.org"),
    # Product Hunt product page (upstream's actual product slug)
    ("products/simplemusic", "products/simpmusic"),
    # Sentry release prefix (kept matching upstream's org naming)
    ("simplemusic-desktop@", "simpmusic-desktop@"),
    # docker image tag for the mpv natives registry
    ("simplemusic-libmpv", "simpmusic-libmpv"),
    # AppImage .desktop scheme handler + macOS Info.plist scheme entry
    ("x-scheme-handler/simplemusic", "x-scheme-handler/simpmusic"),
    ("<string>simplemusic</string>", "<string>simpmusic</string>"),
    # desktop home data directory (~/.simpmusic) — hidden path, not branding
    ('".simplemusic', '".simpmusic'),
    # same directory assembled by concatenation in ReverbIrFiles/ExpectFileSystem
    ('".simplemusic"', '".simpmusic"'),
    # dotted package in the scraper's models dir (line-start package stmts)
    ("kotlinytmusicscraper.models.simplemusic", "kotlinytmusicscraper.models.simpmusic"),
    # widget / notification deep-link URIs (registered scheme is simpmusic)
    ('"simplemusic://', '"simpmusic://'),
    # scheme literals + DataStore persisted value: manifest android:scheme,
    # conveyor.conf url-schemes, SIMPLEMUSIC = "..."
    ('"simplemusic"', '"simpmusic"'),
    # root project name: Compose Multiplatform derives the generated Res
    # class package from it, so renaming it here breaks every
    # `import simpmusic.composeapp.generated.resources.*` at compile time.
    # Build identity, not branding — every other quoted "SimpleMusic" is
    # user-visible (User-Agent, share cards, WM_CLASS) and stays renamed.
    ('rootProject.name = "SimpleMusic"', 'rootProject.name = "SimpMusic"'),
]

# Forward renames phase 1's word-boundary rule cannot reach: inside the
# credit_app XML literal the word is glued to the preceding "\n" escape
# ("\n\nSimpMusic is..."), so 'n' counts as a word char and blocks the match.
FORWARD_FIXES = [
    ("\\n\\nSimpMusic", "\\n\\nSimpleMusic"),
    # README trendshift badge alt text: "%2FSimpMusic" — the 'F' is a word
    # char. The badge links to upstream's entry, so the alt stays upstream's.
    ("maxrave-dev%2FSimpleMusic", "maxrave-dev%2FSimpMusic"),
]


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    changed = 0
    errors = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", ".gradle", ".idea", "build", "mpv-natives", "ci")]
        for name in filenames:
            # fork-owned CI files reference upstream by name on purpose
            if name.startswith("fork-") and dirpath.replace(os.sep, "/").endswith(".github/workflows"):
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT and name not in TEXT_NAMES:
                continue
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as fh:
                    data = fh.read()
            except OSError as e:
                print(f"ERROR reading {path}: {e}", file=sys.stderr)
                errors += 1
                continue
            original = data
            for old, new in PATTERNS:
                data = replace_word(data, old, new)
            text = data.decode("utf-8", errors="surrogateescape")
            for old, new in REVERTS:
                text = text.replace(old, new)
            for old, new in FORWARD_FIXES:
                text = text.replace(old, new)
            data = text.encode("utf-8", errors="surrogateescape")
            if data != original:
                with open(path, "wb") as fh:
                    fh.write(data)
                changed += 1
    print(f"transform: changed {changed} files under {root}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
