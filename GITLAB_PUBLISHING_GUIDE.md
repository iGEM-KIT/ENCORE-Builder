# Publish this ENCORE Community Contributions snapshot to GitLab

**Important:** This ZIP is an offline snapshot, not a live Git repository. It has no `.git` directory and cannot push to GitLab by itself. Publish from a local clone of your team's repository using your own GitLab permissions. **Do not delete the `.git` directory.**

## Suggested safe workflow — Windows PowerShell + VS Code

### 1. Clone or update your team's GitLab repository

In a separate parent folder, use the URL of **your actual team GitLab repository** (replace the placeholder):

```powershell
git clone <YOUR_TEAM_GITLAB_CLONE_URL> ENCORE-gitlab
cd ENCORE-gitlab
git switch develop
git pull --ff-only origin develop
git switch -c feature/open-database-tp-curation
```

If `develop` is not your team's current integration branch, substitute the correct branch. If you already have a clone, work in that clone, but run `git status` and commit or stash unrelated changes first.

### 2. Copy the completed snapshot into that clone

Extract `ENCORE_Community_Contributions_GitLab_TP_Curation_16_10_2026.zip`. The files you want are inside its `ENCORE-Builder-main` folder.

From a PowerShell window in the parent folder (adjust paths to your computer):

```powershell
robocopy ".\ENCORE-Builder-main" ".\ENCORE-gitlab" /E /XD .git node_modules .venv .nuxt .output /XF .env .env.local
```

`robocopy` can return exit codes from 0 through 7 even after a successful copy. **Do not use `/MIR`**, which could delete repository files absent from the ZIP.

### 3. Validate before committing

```powershell
cd .\ENCORE-gitlab
py scripts/export-excel-to-json.py --check
py scripts/test-tp-curation-only.py
node --test tests/unit/selector/simple-filter.test.mjs tests/unit/selector/builder-visibility.test.mjs
git status --short
git diff --stat
git diff --check
```

Inspect the changed files in VS Code's **Source Control** panel. Verify you are not overwriting newer changes made by teammates. The expected essential update is `encapsulin_selector/data/Open_Encapsulin_Databank.xlsx`, along with the Community Contributions Overview/page components if your live branch is behind this snapshot, and the new documentation/test files.

### 4. Push a reviewable branch

```powershell
git add -A
git commit -m "Add public TP curation sheet; keep database filters unchanged"
git push -u origin feature/open-database-tp-curation
```

Open GitLab and create a **Merge Request** targeting your team's integration branch (`develop` in this example). Review the diff and merge only after team approval. Do not force-push.

### 5. Confirm the deployed result

- `Overview` still displays the Community Contributions placeholder and downloads the new Excel.
- Public Excel contains the `targeting_peptides` sheet with 22 records.
- `Builder Filter` still has 24 approved **shell CDS** selections and shows **no TP selection**.
- `Explore Encapsulins` still shows shell candidates and assemblies but no TP interface.

If `git clone` or `git push` reports a permissions/authentication error, sign into GitLab in VS Code or configure an SSH key / personal access token approved by your team. The ZIP does not contain GitLab credentials.
