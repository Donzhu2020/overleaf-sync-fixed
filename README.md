# Overleaf-Sync-Fixed
### Modern Overleaf Two-Way Synchronization (Fixed 2024+)

![Maintenance](https://img.shields.io/badge/Maintenance-Active-green.svg)
![PyPI - License](https://img.shields.io/pypi/l/overleaf-sync.svg)

> **Note:** This is a maintained fork of the original [moritzgloeckl/overleaf-sync](https://github.com/moritzgloeckl/overleaf-sync) which had become incompatible with Overleaf's updated page structure.

This tool provides an easy way to synchronize Overleaf projects from and to your local computer. It has been updated to support the latest Overleaf web interface (specifically fixing the `ols list` and project discovery errors).

----

## What's New in this Version

- **Fixed Project Discovery:** Rewrote the project list parsing logic to handle Overleaf's modern obfuscated HTML/JSON structure.
- **Removed Socket.IO:** Migrated from buggy Socket.IO to robust HTTP GET for fetching project data, making syncing much faster and more reliable.
- **Refactored `download` command:** Position-based arguments and direct source code ZIP downloading with automatic extraction.
- **Improved Security:** No sensitive information is stored in the source code; authentication uses a local `.olauth` cookie file (not tracked by Git).

----

## Bug Fixes & Code Improvements (v1.2.1)

The following issues were identified and fixed in `olclient.py`, `olsync.py`, and `pyproject.toml`:

### `olclient.py`

| # | Issue | Fix |
|---|-------|-----|
| 1 | **`status_code` compared to strings** — `r.status_code == str(200)` / `str(204)` / `str(400)` are always `False` because `requests` returns an `int`. This silently broke `upload_file` (always returned `False`), `delete_file` (always returned `False`), and `create_folder` (never detected existing folders). | Changed all comparisons to integers: `== 200`, `== 204`, `== 400`. |
| 2 | **`delete_file` matched wrong file name in nested paths** — when deleting a file inside a subfolder (e.g. `figures/plot.pdf`), the code compared `v['name'] == file_name` (the full path) instead of `v['name'] == "plot.pdf"` (the basename). Files in subdirectories could never be deleted. | Split the path, capture `base_name = parts[-1]`, and match against that. |
| 3 | **`create_folder` return value not guarded in `upload_file`** — when a folder already exists, `create_folder` returns `None`. The code still called `.append(new_folder)` and read `new_folder['_id']`, causing a `TypeError` crash. | Added `if new_folder:` guard before using the return value. |
| 4 | **`json.loads(r.content)` used throughout** — this is the low-level approach that ignores encoding. `requests` provides `r.json()` which handles encoding correctly and gives clearer errors. | Replaced all `json.loads(r.content)` with `r.json()`. |
| 5 | **`raise reqs.HTTPError()` with no context** — raised a bare exception with no status code or URL, making debugging nearly impossible. | Replaced with `r.raise_for_status()` which includes the status code and URL automatically. |
| 6 | **Dead import `from socketIO_client import SocketIO`** — the Socket.IO migration was completed but the old imports (`socketIO_client`, `time`) were left in, causing an unnecessary (and potentially broken) install dependency. | Removed both dead imports. |
| 7 | **No `requests.Session` reuse** — every API call opened a new TCP connection, adding latency for every request in a sync run. | Introduced a shared `self._session = requests.Session()` for connection reuse across all requests. |

### `olsync.py`

| # | Issue | Fix |
|---|-------|-----|
| 8 | **`open()` calls without context managers in lambdas** — file handles passed to `upload_file` were never explicitly closed, relying on the garbage collector. Added `_read_local()` helper using `with open(...)` for the equality-check lambdas. | Documented that `requests` closes upload handles; used `with open(...)` properly elsewhere. |
| 9 | **`olignore_keep_list()` called multiple times per sync** — in the local sync branch it was called inside `files_from=`, `deleted_files=`, and repeatedly inside comparison lambdas — causing redundant filesystem scans on every file comparison. | Called once, result stored in `keep_list` and reused throughout. |
| 10 | **`execute_action` treated `None` return as success** — `if success:` would incorrectly treat `None` (e.g. from `download_pdf` when no PDF exists) or an empty list as a failure, and could mask legitimate falsy results. | Changed to explicit `if result is not None and result is not False`. |
| 11 | **Blank lines in `.olignore` treated as patterns** — empty strings were passed to `fnmatch.fnmatch()`, which is harmless but wasteful and semantically wrong (a blank line should mean "ignore nothing"). | Added filtering of empty/whitespace-only lines when reading `.olignore`. |

### `pyproject.toml`

| # | Issue | Fix |
|---|-------|-----|
| 12 | **`socketIO-client` still listed as a dependency** — the Socket.IO code was removed but the package remained in `requires`, forcing an unnecessary install that may fail on newer Python versions. | Removed `socketIO-client` from dependencies. |
| 13 | **Over-pinned dependency versions** — `beautifulsoup4 == 4.11.1` (exact pin) and `python-dateutil~=2.8.1` are unnecessarily strict, preventing users from using newer compatible releases. | Relaxed to compatible ranges: `>=4.11,<5` and `>=2.8,<3`. |

----

## Features

- Sync your locally modified `.tex` (and other) files to your Overleaf projects
- Sync your remotely modified `.tex` (and other) files to computer
- Works with free Overleaf account
- No Git or Dropbox required

----

## How To Use

### 1. Install from Source

Since this is the fixed version, install it locally in your Python environment:

```bash
git clone https://github.com/Donzhu2020/overleaf-sync-fixed
cd overleaf-sync-fixed
pip3 install .
```

### 2. Login to Overleaf

```bash
ols login
```

*Tip: Get the cookie from your browser: F12 → Application → Cookies → `overleaf_session2` value.*

### 3. List your Projects

Verify that the tool can see your Overleaf projects:

```bash
ols list
```

**Expected output:**
```
✅ Querying all projects
03/08/2026, 14:30:15 - My Paper Title
02/15/2026, 09:12:33 - IEEE Conference Template
```

### 4. Download Project Source

```bash
# Usage: ols download [PROJECT_NAME]
ols download "My Paper Title"
```

The current directory will be populated with `.tex`, `.bib`, and image files from Overleaf.

### 5. Two-Way Sync

Once you've modified files locally, run the main command to sync changes back and forth:

```bash
# Run 'ols' in the project directory
ols
```

The CLI will compare local and remote files and prompt you to resolve any conflicts.

----

## Credits

Based on the original work by **Moritz Glöckl** ([original repository](https://github.com/moritzgloeckl/overleaf-sync)).

## Disclaimer

THIS SOFTWARE IS NOT AFFILIATED WITH OVERLEAF OR WRITELATEX LIMITED. USE AT YOUR OWN RISK.
