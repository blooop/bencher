#! /bin/bash
set -eo pipefail

export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" #gets the current directory

#move to the project root folder
cd "$SCRIPT_DIR"/..

if ! dpkg -l | grep -q python3-venv; then
    echo "python3-venv is not installed. Installing..."
    sudo apt-get update
    sudo apt-get install -y python3-venv
else
    echo "python3-venv is already installed."
fi

# Define the directory for the virtual environment
VENV_DIR="venv"

# Check if the virtual environment directory exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    echo "Activating the virtual environment..."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "Installing deps rocker..."
    pip install deps-rocker pixi-rocker rockervsc
    echo "Virtual environment setup and deps rocker installation complete."
else
    echo "Virtual environment already exists in $VENV_DIR."
    echo "Activating the existing virtual environment..."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

rockervsc

deactivate
