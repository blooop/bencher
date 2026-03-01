#!/bin/bash
# Source this file to activate the pixi environment in your current shell
# Usage: source .claude/activate.sh

# Add pixi to PATH
export PATH="$HOME/.pixi/bin:$PATH"

# Optional: Activate pixi shell if available
if command -v pixi &> /dev/null; then
    echo "✅ Pixi environment activated"
    echo "💡 Available commands:"
    echo "   pixi run test        - Run tests"
    echo "   pixi run lint        - Run linters"
    echo "   pixi run format      - Format code"
    echo "   pixi run ci          - Run full CI"
    pixi task list --summary 2>/dev/null || true
else
    echo "⚠️  Pixi not found. Please run .claude/hooks/SessionStart first."
fi
