#!/usr/bin/env python3
"""Build a GitHub branch and safely replace a local Content Extract.app."""
from __future__ import annotations

import argparse
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

REPOSITORY = "https://github.com/AbenezerW2/Content-extract.git"
APP_NAME = "Content Extract.app"
APP_ID = "com.abenezer.contentextract"


def run(*args, cwd=None, capture=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def app_info(path):
    with (path / "Contents/Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    if info.get("CFBundleIdentifier") != APP_ID:
        raise ValueError(f"This is not a Content Extract app: {path}")
    executable = path / "Contents/MacOS" / info["CFBundleExecutable"]
    if not executable.is_file():
        raise ValueError(f"Missing app executable: {executable}")
    return info


def is_running(path):
    executable = str(path / "Contents/MacOS/Content Extract")
    processes = run("ps", "-axo", "command=", capture=True)
    return any(line == executable or line.startswith(executable + " ")
               for line in processes.splitlines())


def replace_app(staged, destination, backup):
    """Same-volume rename with rollback if installing the new bundle fails."""
    if backup.exists():
        raise FileExistsError(f"Backup already exists: {backup}")
    had_previous = destination.exists()
    if had_previous:
        destination.rename(backup)
    try:
        staged.rename(destination)
    except BaseException:
        if had_previous:
            backup.rename(destination)
        raise
    return backup if had_previous else None


def install_app(source, destination):
    app_info(source)
    if destination.exists():
        app_info(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Stage on the destination volume so final renames are atomic.
    staging_root = Path(tempfile.mkdtemp(prefix=".content-extract-update-", dir=destination.parent))
    staged = staging_root / APP_NAME
    try:
        print("Preparing the new app...", flush=True)
        run("ditto", str(source), str(staged))
        app_info(staged)
        run("codesign", "--verify", "--deep", "--strict", str(staged))
        while destination.exists() and is_running(destination):
            input("The build is ready. Finish any extraction, quit Content Extract, then press Return to install: ")
        backup = destination.with_name(f"Content Extract.backup-{datetime.now():%Y%m%d-%H%M%S-%f}.app")
        saved = replace_app(staged, destination, backup)
        print(f"Installed: {destination}")
        if saved:
            print(f"Previous app saved at: {saved}")
        return saved
    finally:
        shutil.rmtree(staging_root)


def prepare_checkout(checkout, branch):
    run("git", "check-ref-format", "--branch", branch, capture=True)
    if not checkout.exists():
        run("git", "clone", "--single-branch", "--branch", branch, REPOSITORY, str(checkout))
    if run("git", "remote", "get-url", "origin", cwd=checkout, capture=True).strip() != REPOSITORY:
        raise ValueError("Updater checkout has an unexpected origin; refusing to replace it.")
    if run("git", "status", "--porcelain", cwd=checkout, capture=True).strip():
        raise ValueError(f"The updater checkout has local changes. Preserve them before retrying: {checkout}")
    run("git", "fetch", "origin", f"refs/heads/{branch}", cwd=checkout)
    # The managed checkout is detached; refuse to silently discard local commits.
    old = run("git", "rev-parse", "HEAD", cwd=checkout, capture=True).strip()
    ahead = run("git", "rev-list", "--count", f"FETCH_HEAD..{old}", cwd=checkout, capture=True).strip()
    if int(ahead):
        raise ValueError("The managed checkout has commits outside the selected branch. Use a separate cache for that branch.")
    run("git", "checkout", "--detach", "FETCH_HEAD", cwd=checkout)
    return run("git", "rev-parse", "HEAD", cwd=checkout, capture=True).strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="main", help="GitHub branch to build")
    parser.add_argument("--app", type=Path, default=Path.home() / "Applications" / APP_NAME)
    parser.add_argument("--cache", type=Path, default=Path.home() / "Library/Caches/Content Extract Updater")
    parser.add_argument("--force", action="store_true", help="Rebuild even if this revision is installed")
    parser.add_argument("--check", action="store_true", help="Fetch and compare versions without building or installing")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("This updater requires macOS.")
    if args.app.name != APP_NAME or args.app.is_symlink():
        parser.error("--app must be a real Content Extract.app path, not a symbolic link.")
    destination = args.app.expanduser().absolute()
    cache = args.cache.expanduser().absolute()
    cache.mkdir(parents=True, exist_ok=True)
    # Keep different branch histories and dependency environments separate.
    import hashlib
    checkout = cache / ("source-" + hashlib.sha256(args.branch.encode()).hexdigest()[:12])
    try:
        with (cache / "update.lock").open("w") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("An update is already running. Wait for it to finish.")
            installed = app_info(destination) if destination.exists() else {}
            revision = prepare_checkout(checkout, args.branch)
            print(f"Selected branch: {args.branch}\nLatest revision: {revision[:12]}", flush=True)
            if installed.get("ContentExtractRevision") == revision and not args.force:
                print("Content Extract is already up to date.")
                return 0
            if args.check:
                print("An update is available." if installed else "Content Extract is not installed at this location.")
                return 0
            for tool in ("git", "node", "npm", "python3", "codesign", "ditto"):
                if shutil.which(tool) is None:
                    raise ValueError(f"Required build tool is missing: {tool}")
            if shutil.disk_usage(cache).free < 5 * 1024**3:
                raise ValueError("At least 5 GB of free space is required to build an update.")
            print("Building the update. Your installed app stays intact until the build succeeds.", flush=True)
            run("bash", str(checkout / "scripts/build_macos.sh"), cwd=checkout)
            built = checkout / "dist" / APP_NAME
            if app_info(built).get("ContentExtractRevision") != revision:
                raise ValueError("Build revision is missing or does not match the selected source.")
            backup = install_app(built, destination)
            receipt = {"branch": args.branch, "revision": revision, "app": str(destination),
                       "backup": str(backup) if backup else None, "installed_at": datetime.now().isoformat()}
            (cache / "last-update.json").write_text(json.dumps(receipt, indent=2) + "\n")
            run("open", str(destination))
            print("Update complete. Your saved history and extracted files were not changed.")
            return 0
    except (KeyboardInterrupt, EOFError):
        print("Update cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Update stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
