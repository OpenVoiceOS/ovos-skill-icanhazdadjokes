Last Edit: Claude Sonnet 4.6 - 2026-03-09 - Motive: Updated to reflect workflow migration and new skill-check/release-preview workflows.

# ovos-skill-icanhazdadjokes — Audit Report

## Documentation Status
- [ ] AGENTS.md Header Format
- [x] FAQ.md
- [ ] MAINTENANCE_REPORT.md
- [x] AUDIT.md
- [ ] SUGGESTIONS.md

## CI / Workflow Status (as of 2026-03-09)

| File | Status | Notes |
|------|--------|-------|
| `publish_stable.yml` | ✅ Fixed | Migrated to `OpenVoiceOS/gh-automations@dev`; removed inline publish/sync_dev jobs |
| `release_workflow.yml` | ✅ Fixed | Removed broken inline translations job; fixed `python-version: "3.14"` → `"3.11"`; dangling `publish_pypi`/`notify_matrix` keys resolved; migrated to `@dev` |
| `sync_translations.yml` | ✅ New | Calls `sync-translations.yml` reusable; replaces inline translation sync |
| `skill_check.yml` | ✅ New | Locale coverage, skill.json, gitlocalize readiness in OVOS PR Checks comment |
| `release_preview.yml` | ✅ New | Next-version prediction from labels/title in OVOS PR Checks comment |
| `license_tests.yml` | ✅ New | License compliance via `license-check.yml` reusable |
| `conventional-label.yml` | ✅ OK | Uses `bcoe/conventional-release-labels@v1` |

## locale/en-us/skill.json
- ✅ Fixed: Added `skill_id: "ovos-skill-icanhazdadjokes.openvoiceos"`
- ✅ Fixed: Renamed `title` → `name` (required field)

## Remaining Issues
- `[MAJOR]` **tests**: No unit tests found — add `test/unittests/`
- `[INFO]` **packaging**: Uses `setup.py`; consider migrating to `pyproject.toml`
- `[INFO]` **translations**: 11 of 16 languages below 95% coverage (visible in skill_check PR comments)
