# Documentation Template

Use this template when documenting new features, fixes, or changes during development sessions.

---

## When to Create Documentation

| Type | Location | Template |
|------|----------|----------|
| New feature | `docs/features/FEATURE_NAME.md` | Feature Template |
| Algorithm change | `docs/algorithms/*.md` | Update existing |
| API change | `docs/api/API_REFERENCE.md` | Update existing |
| Bug fix | `docs/development/CHANGELOG.md` | Add entry |
| Config change | `docs/guides/CONFIGURATION.md` | Update existing |

---

## Feature Template

Use this for new features in `docs/features/`:

```markdown
# Feature Name

Brief one-line description.

## Overview

What this feature does and why it exists (2-3 sentences).

## Usage

### Basic Usage

\`\`\`typescript
// Code example
\`\`\`

### Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| option1 | string | "default" | What it does |

## Technical Details

### Architecture

How it's implemented (components, data flow).

### Files

- `path/to/file.ts` - Description

## See Also

- [Related Feature](./OTHER_FEATURE.md)
```

---

## Changelog Entry Template

Add to `docs/development/CHANGELOG.md`:

```markdown
## [YYYY.MM] - Month Year

### Added

- **Feature Name**: Brief description of what was added

### Changed

- **Component**: What changed and why

### Fixed

- **Bug Name**: What was broken and how it was fixed
```

---

## Session Workflow

### During Development

1. **Don't create session logs** - These become clutter
2. **Update existing docs** - Modify relevant files directly
3. **Add changelog entry** - Document significant changes

### After Feature Complete

1. Create feature doc if new feature
2. Update API reference if endpoints changed
3. Update configuration guide if new options
4. Add changelog entry

### What NOT to Document

❌ Debug scripts (put in `scripts/` not `docs/`)  
❌ Temporary fixes (just fix and changelog)  
❌ Session summaries (use changelog instead)  
❌ PR descriptions (keep in git history)  
❌ Benchmark results (summarize in changelog)  

---

## Documentation Standards

### File Naming

- Use `SCREAMING_SNAKE_CASE.md`
- Be descriptive: `ADAPTIVE_TIME_STEPPING.md` not `ADAPTIVE.md`
- No dates in filenames: use changelog for history

### Content Guidelines

- **Be concise** - Respect reader's time
- **Show code** - Examples over explanations
- **Use tables** - For parameters and options
- **Link related** - Cross-reference other docs

### Markdown Style

```markdown
# Title (one per file)

Brief intro paragraph.

## Section

Content with **bold** for emphasis.

### Subsection

- Bullet points for lists
- Keep them short

| Column | Description |
|--------|-------------|
| Value | Explanation |

\`\`\`language
code_example()
\`\`\`
```

---

## Quick Reference

### Adding a New Feature

```bash
# 1. Create feature doc
touch docs/features/MY_FEATURE.md

# 2. Use feature template above

# 3. Add changelog entry
# Edit docs/development/CHANGELOG.md

# 4. Update README if major feature
# Edit docs/README.md navigation table
```

### Fixing a Bug

```bash
# Just add changelog entry
# Edit docs/development/CHANGELOG.md

# Add under "### Fixed" section
```

### Updating Configuration

```bash
# Update config guide
# Edit docs/guides/CONFIGURATION.md

# Add changelog entry if significant
```

---

## Folder Structure Reference

```text
docs/
├── README.md              # Main index - update for major changes
├── getting-started/       # Onboarding - rarely changes
├── architecture/          # System design - update for major refactors
├── guides/                # How-to guides - update as needed
├── frontend/              # React/UI docs - update with UI changes
├── backend/               # API/logic docs - update with backend changes
├── algorithms/            # Algorithm details - update with algorithm changes
├── api/                   # API reference - update with endpoint changes
├── features/              # Feature docs - add new features here
├── development/           # Contributing + changelog
├── validation/            # Testing guides
└── reference/             # Terminology, glossary
```

---

## Maintenance Checklist

Monthly review:

- [ ] Remove outdated content
- [ ] Update version numbers
- [ ] Check broken links
- [ ] Consolidate duplicates
- [ ] Update changelog

---

*Follow this template to keep documentation clean, organized, and useful.*
