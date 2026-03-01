#! /bin/bash

git config --global pull.rebase false
git remote add template https://github.com/blooop/python_template.git
git fetch --all
git checkout main && git pull origin main
git checkout -B feature/update_from_template; git pull
git merge template/main --allow-unrelated-histories -m 'feat: pull changes from remote template'
git checkout --ours pixi.lock

# regenerate lockfile to match merged pyproject.toml
pixi update
git add pixi.lock
git diff --cached --quiet || git commit -m 'chore: update pixi.lock after template merge'

git remote remove template
git push --set-upstream origin feature/update_from_template
git checkout main
