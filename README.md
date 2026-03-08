# Overleaf-Sync-Fixed
### Modern Overleaf Two-Way Synchronization (Fixed 2024+)

![Maintenance](https://img.shields.io/badge/Maintenance-Active-green.svg) ![PyPI - License](https://img.shields.io/pypi/l/overleaf-sync.svg)

> **Note:** This is a maintained fork of the original [moritzgloeckl/overleaf-sync](https://github.com/moritzgloeckl/overleaf-sync) which had become incompatible with Overleaf's updated page structure.

This tool provides an easy way to synchronize Overleaf projects from and to your local computer. It has been updated to support the latest Overleaf web interface (specifically fixing the `ols list` and project discovery errors).

----

## What's New in this Version
- **Fixed Project Discovery:** Rewrote the project list parsing logic to handle Overleaf's modern obfuscated HTML/JSON structure.
- **Robust Bracket Counting:** Implemented a new extraction method that correctly identifies the projects array even when it's deeply nested or HTML-escaped.
- **Improved Error Handling:** Clearer messages when authentication fails or cookies expire.

## Features
- Sync your locally modified `.tex` (and other) files to your Overleaf projects
- Sync your remotely modified `.tex` (and other) files to computer
- Works with free Overleaf account
- No Git or Dropbox required

## How To Use
### Install from Source
Until this is published to PyPI, you can install it locally:

```bash
git clone https://github.com/lawrencee/overleaf-sync-fixed
cd overleaf-sync-fixed
pip install .
```

### Usage
#### Login
```bash
ols login
```
Follow the prompts to paste your `overleaf_session2` cookie from your browser's developer tools.

#### List Projects
```bash
ols list
```

#### Syncing
```bash
# Two-way sync the current folder with an Overleaf project of the same name
ols
```

## Credits
This project is based on the excellent work by **Moritz Glöckl** ([original repository](https://github.com/moritzgloeckl/overleaf-sync)). Special thanks to the original author for the foundational logic.

## Disclaimer
THE AUTHOR OF THIS SOFTWARE AND THIS SOFTWARE IS NOT ENDORSED BY, DIRECTLY AFFILIATED WITH, MAINTAINED, AUTHORIZED, OR SPONSORED BY OVERLEAF OR WRITELATEX LIMITED. USE AT YOUR OWN RISK.
