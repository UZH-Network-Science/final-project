#!/bin/bash
set -e

# Usage: ./scripts/deploy_to_hf.sh [remote_name]
# Default remote: hf-space

REMOTE_NAME=${1:-hf-space}
DEPLOY_BRANCH="hf-deploy"
MAIN_BRANCH=$(git branch --show-current)

echo "Starting deployment to Hugging Face Space ($REMOTE_NAME)..."

# Ensure clean state
if [[ -n $(git status -s) ]]; then
    echo "Error: Working directory is not clean. Please commit or stash changes first."
    exit 1
fi

# 1. Create orphan branch
echo "Creating fresh deploy branch: $DEPLOY_BRANCH"
git checkout --orphan $DEPLOY_BRANCH

# 2. Configure .gitignore and .gitattributes
echo "Excluding large files & disabling LFS..."

# Exclude heavy files
echo "" >> .gitignore
echo "# HF Space Excludes" >> .gitignore
echo "datasets/**/*" >> .gitignore
echo "!datasets/**/*.gpickle" >> .gitignore

# DISABLE LFS (Clear attributes)
# This ensures files are added as standard git blobs, not LFS pointers
echo "" > .gitattributes

# 3. Stage files
# We must clear the index to remove any existing LFS pointers from the orphan branch state
git rm -r --cached . > /dev/null 2>&1 || true

# Strip notebooks before adding (avoids pre-commit hook failure)
if command -v nbstripout &> /dev/null; then
    echo "Stripping output from notebooks..."
    find . -type f -name "*.ipynb" -not -path '*/.*' -exec nbstripout {} +
else
    echo "Warning: nbstripout not found. Notebooks might contain outputs."
fi

git add .

# 4. Commit
echo "Committing deployment snapshot..."
git commit -m "Deploy to HF Space" --quiet

# 5. Push
echo "Pushing to $REMOTE_NAME..."
git push --force $REMOTE_NAME $DEPLOY_BRANCH:main

# 6. Cleanup
echo "Cleaning up..."
git checkout $MAIN_BRANCH
git branch -D $DEPLOY_BRANCH

echo "Deployment complete!"
