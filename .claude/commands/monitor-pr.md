# Monitor PR

Monitor the pull request for CI failures and review comments, then fix any issues.

PR: $ARGUMENTS

## Steps

1. Identify the PR number from the argument (URL or number)
2. Check PR CI status: `gh pr checks <number>`
3. Check for review comments: `gh api repos/{owner}/{repo}/pulls/<number>/reviews` and `gh api repos/{owner}/{repo}/pulls/<number>/comments`
4. If CI checks are still pending, wait and re-check
5. If any CI checks fail:
   - Fetch the failed job logs: `gh run view <run-id> --log-failed`
   - Diagnose and fix the issue
   - Run `pixi run ci` locally to verify the fix
   - Commit and push the fix
6. If there are review comments:
   - Read and address each comment
   - Make the requested changes
   - Run `pixi run ci` to verify
   - Commit and push
7. Repeat until all checks pass and all comments are addressed
8. Report final status to the user

## Notes

- Input can be a GitHub PR URL or a PR number
- Always run `pixi run ci` locally before pushing fixes
- Keep fix commits focused and descriptive
- Continue monitoring until everything is green and addressed
