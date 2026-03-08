# Overleaf-Sync-Fixed
### Modern Overleaf Two-Way Synchronization (Fixed 2024+)

![Maintenance](https://img.shields.io/badge/Maintenance-Active-green.svg) ![PyPI - License](https://img.shields.io/pypi/l/overleaf-sync.svg)

> **Note:** This is a maintained fork of the original [moritzgloeckl/overleaf-sync](https://github.com/moritzgloeckl/overleaf-sync) which had become incompatible with Overleaf's updated page structure.

This tool provides an easy way to synchronize Overleaf projects from and to your local computer. It has been updated to support the latest Overleaf web interface (specifically fixing the `ols list` and project discovery errors).

----

## What's New in this Version
- **Fixed Project Discovery:** Rewrote the project list parsing logic to handle Overleaf's modern obfuscated HTML/JSON structure.
- **Removed Socket.IO:** Migrated from buggy Socket.IO to robust HTTP GET for fetching project data, making syncing much faster and more reliable.
- **Refactored `download` command:** Position-based arguments and direct source code ZIP downloading with automatic extraction.
- **Improved Security:** No sensitive information is stored in the source code; authentication uses a local `.olauth` cookie file (not tracked by Git).

## Features
- Sync your locally modified `.tex` (and other) files to your Overleaf projects
- Sync your remotely modified `.tex` (and other) files to computer
- Works with free Overleaf account
- No Git or Dropbox required

## How To Use

### 1. Install from Source
Since this is the fixed version, install it locally in your Python environment:

```bash
git clone https://github.com/lawrencee/overleaf-sync-fixed
cd overleaf-sync-fixed
pip install .
```

### 2. Login to Overleaf
You need to provide your `overleaf_session2` cookie to authenticate.

```bash
ols login
```
*Tip: Get the cookie from your browser: F12 -> Application -> Cookies -> `overleaf_session2` Value.*

### 3. List your Projects
Verify that the tool can see your Overleaf projects:

```bash
ols list
```
**Expected Output:**
```text
✅  Querying all projects
03/08/2026, 14:30:15 - My Paper Title
02/15/2026, 09:12:33 - IEEE Conference Template
...
```

### 4. Download Project Source (NEW)
To get the LaTeX source code of a specific project and extract it into the current directory:

```bash
# Usage: ols download [PROJECT_NAME]
ols download "My Paper Title"
```
**Expected Results:**
- 📁 Current directory will be populated with `.tex`, `.bib`, and image files from Overleaf.
- ✅ CLI will output: `Source downloaded successfully. Extracted source to: /your/local/path`

### 5. Two-way Sync
Once you've modified files locally, run the main command to sync changes back and forth:

```bash
# Simply run 'ols' in the project directory
ols
```
**Expected Results:**
- CLI will compare local and remote files.
- You'll be prompted to resolve conflicts if both sides have changes.

---

## Credits
Based on the original work by **Moritz Glöckl** ([original repository](https://github.com/moritzgloeckl/overleaf-sync)).

## Disclaimer
THIS SOFTWARE IS NOT AFFILIATED WITH OVERLEAF OR WRITELATEX LIMITED. USE AT YOUR OWN RISK.
