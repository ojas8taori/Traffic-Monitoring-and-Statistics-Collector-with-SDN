# GitHub Publish Guide (WSL2)

This guide publishes this project to a **public** GitHub repo.

## 1. Quick cleanup checklist

- Ensure Mininet is stopped: `exit` in Mininet CLI
- Cleanup Mininet once: `sudo mn -c`
- Keep controller stopped (`Ctrl+C`)
- Confirm evidence exists under `results/` (screenshots + logs)

Note:
- `venv/` is intentionally not committed (ignored via `.gitignore`).
- `results/logs/openflow_capture.pcap` is ignored by default to avoid large binaries.

## 2. Initialize git repo (from project root)

```bash
cd /mnt/c/OJ/sem4/CN/orange-2.1
git init
git branch -M main
```

## 3. Review what will be committed

```bash
git status
```

Optional: check ignored files (should include `venv/`):

```bash
git status --ignored
```

## 4. Add and commit

```bash
git add .
git commit -m "SDN traffic monitoring (Mininet + Ryu)"
```

## 5. Create GitHub repo (manual)

On GitHub:
- New repository
- Name suggestion: `sdn-traffic-monitor`
- Visibility: **Public**
- Do NOT initialize with README (this project already has one)

Copy the repo URL.

## 6. Add remote and push

```bash
git remote add origin <PASTE_YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## 7. Verify submission requirements

On GitHub repo page confirm:
- README renders and includes run steps
- `DEMO_EXECUTION_GUIDE.md` is present
- `results/screenshots/` and `results/logs/` are present
- Project is **public**

## 8. If you need to update evidence after pushing

```bash
git add results/ README.md
git commit -m "Add execution evidence"
git push
```
