# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Renamed the project from `decision-picker` to `tiltrank` (repo, skill directory, pi extension and tool name). The log env var is now `$TILTRANK_LOG` (was `$DECISION_PICKER_LOG`).

## [0.2.0] - 2026-09-21

### Added
- MIT LICENSE file
- CONTRIBUTING.md, SECURITY.md, community health files (issue templates, PR template)
- Prerequisites, Changelog, and Acknowledgments sections in README
- `when_to_use` and `compatibility` frontmatter fields in SKILL.md
- `extensions/package.json` and `extensions/tsconfig.json` for pi extension type-checking
- Ruff lint step and macOS to CI matrix
- Extension type-check job in CI

### Changed
- Expanded `.gitignore` to industry-standard Python patterns
- Removed HTML wrapper from README; marked `claude plugin validate` as optional
- Sanitized internal provider details from docs/ and PLAN.md
- Added docs/README.md and PLAN.md design-history header
- Updated README Testing section with honest live-gate status

### Fixed
- License contradiction (README said 'all rights reserved', SKILL.md said MIT)
- Stale local branches removed
- Cached artifacts cleaned from working tree
