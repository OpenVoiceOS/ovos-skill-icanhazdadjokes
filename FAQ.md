Last Edit: Claude Sonnet 4.6 - 2026-03-09 - Motive: Created FAQ.md; documented workflow migration from TigreGotico@master to OpenVoiceOS@dev, skill.json fix, and new skill-check/release-preview workflows.

# FAQ — ovos-skill-icanhazdadjokes

## Workflows

### Why were the GitHub Actions workflows changed?

The workflows were migrated from the archived `TigreGotico/gh-automations@master` ref to
`OpenVoiceOS/gh-automations@dev`, which is the active development branch with bug fixes and new features.

Several anti-patterns were also removed:
- `actions/checkout@v6` / `actions/setup-python@v6` — v6 does not exist; fixed to `@v4` / `@v5`
- `python-version: "3.14"` — not a real release; fixed to `"3.11"`
- `python setup.py sdist bdist_wheel` — replaced with `python -m build` inside the reusable
- `echo "::set-output name=..."` — deprecated syntax; removed (handled by reusable)
- Inline `translations` job in `release_workflow.yml` — extracted to `sync_translations.yml` reusable

### What does sync_translations.yml do?

It runs `scripts/sync_translations.py` (already present in this repo) whenever
`gitlocalize-app[bot]` pushes to `dev`, or on manual dispatch. Translation commits are
auto-committed back to `dev` by `stefanzweifel/git-auto-commit-action`.

### What does skill_check.yml do?

On every PR to `dev`, it checks:
- Locale directory structure and en-us file counts
- Translation coverage per language (warns below 95%, fails below 50% if configured)
- skill.json validity (required fields: `skill_id`, `name`, `description`, `examples`, `tags`)
- Gitlocalize readiness (sync script, translations/ dir, sync workflow)

Results are posted as the `🎙️ Skill` section in the OVOS PR Checks comment.

### What does release_preview.yml do?

On every PR to `dev`, it predicts the next version based on PR labels and/or conventional
commit prefix in the PR title (`feat:` → minor, `fix:` → build, `breaking change:` → major).
Results are posted as the `🏷️ Release Preview` section in the OVOS PR Checks comment.

---

## Locale / Translations

### Why does skill.json now have `skill_id` and `name`?

The previous `skill.json` used `title` instead of `name` and was missing `skill_id`.
The required fields are: `skill_id`, `name`, `description`, `examples`, `tags`.
`skill_id` is `ovos-skill-icanhazdadjokes.openvoiceos` (derived from the GitHub URL in `setup.py`).

### Why do many languages have low translation coverage?

Most languages only have partial translations — some were contributed via gitlocalize but
not all en-us locale files were ported. The `skill_check.yml` workflow now surfaces this
on every PR so contributors can see which files are missing.
