# Claude Code Configuration

This directory contains configuration for using this project with Claude Code, particularly in the online environment.

## SessionStart Hook

The `hooks/SessionStart` script automatically runs when a new Claude Code session begins. It:

1. **Installs pixi** (if not already installed) - The package and environment manager
2. **Installs project dependencies** - All Python packages and tools defined in `pyproject.toml`
3. **Sets up prek hooks** - For automatic code quality checks
4. **Configures git** - Sets up merge drivers for lockfiles

## Usage with Claude Code Online

When you start a Claude Code online session, the SessionStart hook will automatically run and set up your environment. You'll see output indicating the setup progress.

### Available Commands

Once setup is complete, Claude can use these pixi tasks:

#### Testing & Quality
- `pixi run test` - Run pytest tests
- `pixi run coverage` - Run tests with coverage report
- `pixi run lint` - Run ruff and pylint linters
- `pixi run format` - Format code with ruff

#### CI Tasks
- `pixi run ci` - Run full CI pipeline (format, lint, test, coverage)
- `pixi run fix` - Auto-fix common issues (update lock, format, lint)

#### Prek Hooks
- `pixi run prek` - Run all prek hooks
- `pixi run prek-update` - Update prek hook versions

### How It Works

1. **First session**: The hook installs pixi and all dependencies (may take a few minutes)
2. **Subsequent sessions**: The hook verifies the environment is ready (much faster)
3. **Environment activated**: All pixi commands are available to Claude

### Troubleshooting

If you encounter issues:

1. **Dependencies not found**: Run `pixi install` manually
2. **Lockfile conflicts**: Run `pixi run update-lock`
3. **Prek issues**: Run `pixi run prek-update`
4. **Full reset**: Delete `.pixi` directory and restart session

### Customization

You can modify `hooks/SessionStart` to:
- Install additional tools
- Run custom setup scripts
- Configure environment variables
- Set up external services

## Ralph Orchestrator

This project includes [ralph-orchestrator](https://github.com/mikeyobrien/ralph-orchestrator), an autonomous agent orchestrator for managing complex multi-step tasks.

### Installation

Ralph is installed as a pixi dependency. After running `pixi install`, it's available in the environment.

### Basic Usage

```bash
# Initialize ralph (creates ralph.yml and PROMPT.md if not present)
pixi run ralph init

# Plan a task (creates a spec file)
pixi run ralph plan "Implement feature X"

# Run ralph with the current PROMPT.md
pixi run ralph run

# Check ralph version
pixi run ralph --version
```

### Configuration Files

- `ralph.yml` - Main configuration (event loop, hats, backends)
- `PROMPT.md` - Task description for ralph to execute
- `specs/` - Directory for task specifications

### Customization

Edit `ralph.yml` to customize:
- `event_loop.max_iterations` - Maximum iterations before stopping
- `event_loop.max_runtime_seconds` - Maximum runtime
- `cli.backend` - AI backend (claude, gemini, codex, etc.)
- `hats` - Define custom personas for multi-agent workflows

See the [ralph-orchestrator documentation](https://github.com/mikeyobrien/ralph-orchestrator) for more details.

## Learn More

- [Claude Code Documentation](https://docs.claude.com/claude-code)
- [Pixi Documentation](https://pixi.sh)
- [Ralph Orchestrator](https://github.com/mikeyobrien/ralph-orchestrator)
- [Project README](../README.md)
