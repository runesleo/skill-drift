# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-10-26

### Added

- `skill-drift check` compares the text of Claude skills, Cursor rules, and a second skills directory. File modification time is ignored.
- `skill-drift merge` prints a symlink plan. `--apply` archives the replaced file and writes the link. `--add-missing` also creates a link in a directory that has no copy yet.
- `skill-drift doctor` is a read-only self-check for the Python version and the three usual directories.
- `install.md` for an AI agent installing the tool.
