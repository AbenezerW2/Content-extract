# One-click Mac updates

The local updater fetches a chosen branch from `AbenezerW2/Content-extract`,
builds the interface and Mac application, and installs the completed bundle.
It requires Git, Python 3, Node.js/npm and an internet connection. It does not
require a GitHub token for this public repository. Builds can take several
minutes and require at least 5 GB free space.

## First setup

From the repository root:

```bash
python3 scripts/update_macos.py --branch v2.2 \
  --app "$HOME/Applications/Content Extract.app"
```

Use the actual path of an existing installation with `--app` to preserve Dock
shortcuts. Otherwise the default is `~/Applications/Content Extract.app`.
The script never requires administrator access; the destination must be writable.

For one-click use, make a copy of `Update Content Extract.command` and change
its Python invocation to use the absolute path of `update_macos.py`, followed
by your desired `--branch` and `--app` arguments. Keep that source script in
place. Mark the launcher executable with `chmod +x`, then double-click it in
Finder. A launcher configured for this Mac is also supplied with the setup.

## What happens on each update

1. Fetch the selected branch into a separate managed checkout under
   `~/Library/Caches/Content Extract Updater`. Your development checkout is
   not modified. Checkouts are isolated by branch.
2. Compare its commit with `ContentExtractRevision` inside the installed app.
   If they match, finish without rebuilding. `--force` rebuilds the same commit;
   `--check` only fetches and reports whether a build is needed.
3. Build the app and bundled browser. The installed app stays intact while
   the build runs. A second simultaneous updater is rejected.
4. Copy the new build to a temporary folder beside the destination and verify
   its code signature. The build uses local ad-hoc signing, not Apple notarization.
5. If Content Extract is running, ask you to finish any extraction and quit it.
   The updater never kills an extraction. Press Return after quitting.
6. Rename the old app to a timestamped backup, put the new app in its place,
   and launch it. A failed replacement restores the old app automatically.

Saved history under `~/Library/Application Support/Content Extract` and your
extracted files are not replaced. A receipt in the cache records the installed
commit, branch, application path and backup path. Backups are retained until
you remove them yourself, so repeated updates need additional disk space.

## Roll back

Quit Content Extract. In Finder, move the new app aside and rename the desired
timestamped backup to `Content Extract.app` in the same directory. Open it.
The receipt gives the exact backup path. Rollback replaces the executable;
it does not roll back user data or future data-format migrations.

## Scope

Only changes committed and pushed to the selected branch are included. The
updater does not merge other branches or publish your local edits. It refuses
to discard changes or unmerged commits in its managed checkout. To change the
selected branch, edit `--branch` in the launcher.

New command-line features need explicit desktop interface integration before
they appear as buttons. In particular, the current Kortext capture tool is
still command-line only; rebuilding this branch does not add a Kortext screen.

This is a local build/install updater, not a background auto-update service or
a downloadable GitHub Releases update channel. The updater launcher itself
uses the local script path saved at setup; update that copy when adopting
future changes to the updater implementation.
