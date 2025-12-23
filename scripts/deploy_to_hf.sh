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

# Exclude all files in datasets/
echo "" >> .gitignore
echo "# HF Space Excludes" >> .gitignore
echo "datasets/" >> .gitignore

# Disable LFS for everything by default, then enable for binary files (gpickle), otw. rejected by huggingface
echo "*.gpickle filter=lfs diff=lfs merge=lfs -text" > .gitattributes

# 3. Stage files
# Clear index
git read-tree --empty

# Strip notebooks to avoid pre-commit hook failure
if command -v nbstripout &> /dev/null; then
    echo "Stripping output from notebooks..."
    find . -type f -name "*.ipynb" -not -path '*/.*' -exec nbstripout --extra-keys "metadata.kernelspec metadata.language_info.version" {} +
else
    echo "Warning: nbstripout not found. Notebooks might contain outputs."
fi

# Add files back respecting new .gitignore
git add .

# Force re-add the allowed gpickle files from datasets
echo "Re-adding allowed dataset files..."
find datasets -name "*.gpickle" | xargs git add -f

# 4. Commit
echo "Committing deployment snapshot..."
# --no-verify to skip pre-commit hooks
git commit -m "Deploy to HF Space" --quiet --no-verify

# 5. Push
echo "Pushing to $REMOTE_NAME..."
git push --force $REMOTE_NAME $DEPLOY_BRANCH:main

# 6. Cleanup
echo "Cleaning up..."
git checkout $MAIN_BRANCH
git branch -D $DEPLOY_BRANCH

echo "Deployment complete!"
