#!/bin/bash

# Escape characters special in sed replacement strings (\, &, /)
escape_sed() { printf '%s\n' "$1" | sed 's/[\\&/]/\\&/g'; }

mv python_template "$1"

ESCAPED_1=$(escape_sed "$1")

# change project name in all files (exclude main devcontainer.json to protect template image URL)
find . \( -type d -name .git -prune \) -o \( -type f -not -name 'tasks.json' -not -name 'update_from_template.sh' -not -name 'pixi.lock' -not -path './.devcontainer/devcontainer.json' \) -print0 | xargs -0 sed -i "s/python_template/$ESCAPED_1/g"

# update just the name field in devcontainer.json
sed -i "s/\"name\": \"python_template\"/\"name\": \"$ESCAPED_1\"/" .devcontainer/devcontainer.json

# regenerate lockfile to match renamed project
pixi update

# author name
if [ -n "$2" ]; then
    ESCAPED_2=$(escape_sed "$2")
    find . \( -type d -name .git -prune \) -o \( -type f -not -name 'tasks.json' -not -name 'update_from_template.sh'  \) -print0 | xargs -0 sed -i "s/Austin Gregg-Smith/$ESCAPED_2/g"
fi

# author email
if [ -n "$3" ]; then
    ESCAPED_3=$(escape_sed "$3")
    find . \( -type d -name .git -prune \) -o \( -type f -not -name 'tasks.json' -not -name 'update_from_template.sh'  \) -print0 | xargs -0 sed -i "s/blooop@gmail.com/$ESCAPED_3/g"
fi

# github username (exclude main devcontainer.json to protect template image URL)
if [ -n "$4" ]; then
    ESCAPED_4=$(escape_sed "$4")
    find . \( -type d -name .git -prune \) -o \( -type f -not -name 'setup_host.sh' -not -name 'update_from_template.sh' -not -path './.devcontainer/devcontainer.json' \) -print0 | xargs -0 sed -i "s/blooop/$ESCAPED_4/g"
fi
