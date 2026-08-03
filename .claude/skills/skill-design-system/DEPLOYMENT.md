# Deployment

This skill lives in two places. The standalone repo is the source of truth. The af-agents copy stays in sync via a simple pull.

## Repo locations

| Location                                              | Purpose                                                              |
|-------------------------------------------------------|----------------------------------------------------------------------|
| `KentNunezNYC/af-design-system`                       | Canonical. Source of truth. Versioned independently.                 |
| `KentNunezNYC/af-agents/skills/af-design-system/`     | Mirror. What the agent fleet reads at runtime.                       |

## Why both

- **Standalone repo** lets people, partners, and outside agents reference the skill on its own, link to specific commits, file issues against it, and version it independently of the agent fleet.
- **af-agents copy** keeps the skill discoverable inside the existing agent governance setup (registry, role-based credentials, shared execution machine). Agents don't have to reach outside the fleet repo to find it.

## Initial setup

### Step 1: Push to standalone repo

```bash
cd af-design-system
git init
git add .
git commit -m "Initial release v1.0 from Brand Guidelines v5"
gh repo create KentNunezNYC/af-design-system --public --source=. --push
```

### Step 2: Mirror into af-agents

```bash
# In your local af-agents checkout
mkdir -p skills/af-design-system
rsync -av --exclude='.git' /path/to/af-design-system/ skills/af-design-system/

# Add a header note in the mirror SKILL.md pointing back to canonical
# (already handled by sync.sh below)

git add skills/af-design-system
git commit -m "Add af-design-system skill v1.0"
git push
```

### Step 3: Register in the agent fleet

Add an entry to the af-agents skill registry pointing to `skills/af-design-system/SKILL.md`. Agents discover it through the registry, same as every other skill in the fleet.

## Keeping the two in sync

When the design system updates (new template, token change, version bump), update the standalone repo first, then mirror to af-agents.

### Suggested sync.sh (drop this in af-agents/scripts/)

```bash
#!/usr/bin/env bash
# Sync af-design-system from canonical repo into af-agents
set -euo pipefail

TARGET="skills/af-design-system"
CANONICAL="https://github.com/KentNunezNYC/af-design-system.git"
TMP=$(mktemp -d)

git clone --depth 1 "$CANONICAL" "$TMP"
rm -rf "$TARGET"
mkdir -p "$TARGET"
rsync -av --exclude='.git' "$TMP/" "$TARGET/"
rm -rf "$TMP"

# Add a sync header to the mirror's SKILL.md (idempotent)
SYNC_HEADER="<!-- This is a mirror of KentNunezNYC/af-design-system. Source of truth is the standalone repo. -->"
if ! grep -q "mirror of" "$TARGET/SKILL.md"; then
  sed -i "1i $SYNC_HEADER\n" "$TARGET/SKILL.md"
fi

echo "Synced. Review changes with: git status $TARGET"
```

Run it whenever the canonical updates:

```bash
./scripts/sync.sh
git add skills/af-design-system
git commit -m "Sync af-design-system v$(grep '^version:' skills/af-design-system/SKILL.md | awk '{print $2}')"
git push
```

## Version policy

| Change type                                | Version bump | Action                              |
|--------------------------------------------|--------------|-------------------------------------|
| Token value change, logo swap              | Patch (1.0.x)| Update canonical, run sync          |
| New template, new asset, new rule          | Minor (1.x)  | Update canonical, run sync, announce|
| Underlying brand guidelines version change | Major (x.0)  | Full review, both repos, announce   |
