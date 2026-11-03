# Operations

Owner-run procedures that are intentionally **not** automated from CI (they need
repository admin rights or external accounts). Day-to-day incident handling lives
in `docs/runbook.md`.

## Branch protection

`main` is protected but, as of audit item A21, only `backend` and `frontend` were
required status checks. CI also runs `mobile` and `secrets`; both must gate merges.
Nothing in the repository changes protection automatically; the owner runs this once
with a token that has `administration:write` on `suleymansd/Svontai`.

Update only the required checks (keeps every other protection setting as is):

```sh
gh api -X PATCH repos/suleymansd/Svontai/branches/main/protection/required_status_checks \
  -F strict=true \
  -f 'contexts[]=backend' \
  -f 'contexts[]=frontend' \
  -f 'contexts[]=mobile' \
  -f 'contexts[]=secrets'
```

If the endpoint returns 404 (protection not yet created through the REST API, or a
ruleset is used instead), set the whole protection object in one call:

```sh
gh api -X PUT repos/suleymansd/Svontai/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["backend", "frontend", "mobile", "secrets"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON
```

Verify:

```sh
gh api repos/suleymansd/Svontai/branches/main/protection/required_status_checks --jq '.contexts'
# expected: ["backend","frontend","mobile","secrets"]
```

The context names are the CI job ids in `.github/workflows/ci.yml` (`secrets`,
`backend`, `frontend`, `mobile`). Renaming a job requires re-running the command.
