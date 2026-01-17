# Fix GitHub Issue

Fix the GitHub issue: $ARGUMENTS

## Steps

1. Fetch issue details: `pixi run gh issue view $ARGUMENTS`
2. Extract the issue number from the URL for commit messages
3. Understand the problem and locate relevant code
4. Implement the fix
5. Run `pixi run ci` to verify (format, lint, test, coverage)
6. Commit with message referencing the issue (e.g., `Fixes #123`)
7. Create PR: `pixi run gh pr create`

## Notes

- Input can be a GitHub URL (e.g., `https://github.com/owner/repo/issues/123`) or issue number
- Keep changes minimal and focused on the issue
- Add tests if fixing a bug
- Run full CI before committing
