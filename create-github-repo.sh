#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/create-github-repo.sh
#
# Creates a new GitHub repository and pushes the VerseFlow codebase to it.
#
# Requirements:
#   - git        (https://git-scm.com)
#   - gh CLI     (https://cli.github.com) — run `gh auth login` first
#
# Usage:
#   bash scripts/create-github-repo.sh
#
# Optional: pass a repo name as an argument (default: verseflow)
#   bash scripts/create-github-repo.sh my-verseflow
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

REPO_NAME="${1:-verseflow}"
REPO_DESC="Real-time Bible verse and worship lyric detection for church services"
BRANCH="main"

# ── Pre-flight checks ─────────────────────────────────────────────────────────

echo ""
echo " =================================================="
echo "  VerseFlow → GitHub"
echo " =================================================="
echo ""

if ! command -v git &>/dev/null; then
  echo " ERROR: git is not installed."
  echo " Download it from https://git-scm.com and re-run."
  exit 1
fi

if ! command -v gh &>/dev/null; then
  echo " ERROR: GitHub CLI (gh) is not installed."
  echo " Download it from https://cli.github.com and run 'gh auth login' first."
  exit 1
fi

if ! gh auth status &>/dev/null; then
  echo " You are not logged in to GitHub. Running 'gh auth login'..."
  gh auth login
fi

# ── Initialise git if needed ──────────────────────────────────────────────────

if [ ! -d ".git" ]; then
  echo "[1/4] Initialising git repository..."
  git init -b "$BRANCH"
else
  echo "[1/4] Git repository already initialised."
  # Make sure we're on the right branch
  git checkout -B "$BRANCH" 2>/dev/null || true
fi

# ── Stage and commit ──────────────────────────────────────────────────────────

echo "[2/4] Staging all files..."
git add .

# Only commit if there is something to commit
if git diff --cached --quiet; then
  echo "      Nothing new to commit — working tree is clean."
else
  echo "[2/4] Creating initial commit..."
  git commit -m "Initial commit: VerseFlow v$(node -p "require('./package.json').version" 2>/dev/null || echo '1.0.0')"
fi

# ── Create GitHub repository ──────────────────────────────────────────────────

echo "[3/4] Creating GitHub repository '$REPO_NAME'..."

# gh repo create will fail if the repo already exists — catch that gracefully.
if gh repo create "$REPO_NAME" \
    --public \
    --description "$REPO_DESC" \
    --source=. \
    --remote=origin \
    --push 2>/dev/null; then
  echo "      Repository created and code pushed successfully."
else
  # Repo may already exist — just push.
  echo "      Repository may already exist. Pushing to existing remote..."
  GITHUB_USER=$(gh api user --jq .login)
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$GITHUB_USER/$REPO_NAME.git"
  git push -u origin "$BRANCH"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

GITHUB_USER=$(gh api user --jq .login)

echo ""
echo " =================================================="
echo "  Done!"
echo " =================================================="
echo ""
echo "  Your repository is live at:"
echo "  https://github.com/$GITHUB_USER/$REPO_NAME"
echo ""
echo "  To push future changes:"
echo "    git add ."
echo "    git commit -m \"Your message\""
echo "    git push"
echo ""
