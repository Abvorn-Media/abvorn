# Launching the Abvorn daemon on a VPS (Oracle Cloud Free Tier)

This runs the real continuous organism: `abvorn/daemon.py` 24/7 (brain,
research/content/deploy agents, supervisor, platform agents, GA4 analytics,
Telegram ops, backups) plus the content-cycle builds moved off GitHub Actions
onto the persistent host — which is what finally makes the multi-core
**genesis** path meaningful (a regenerating child core, not an ephemeral CI
job).

Live site stays on GitHub Pages; the VPS just owns the organism + the cycle
that feeds the site.

## 0. What you pay

Oracle Cloud "Always Free" Ampere A1 (ARM): **$0/month** for a
`VM.Standard.A1.Flex` with up to 4 OCPU / 24 GB RAM. Caveats: the free pool is
shared and Oracle can occasionally reclaim idle instances; bills stay at $0 as
long as you stay inside the free quota.

## 1. Create the instance

1. Sign in at <https://cloud.oracle.com> → Compute → Instances → **Create instance**.
2. Name: `abvorn`. Image: **Canonical Ubuntu 22.04 (aarch64)**.
3. Shape: **Ampere A1 Flex**, OCPUs `4`, Memory `24 GB` (always-free eligible).
4. Add SSH key: click "Paste public keys". Generate a key first in PowerShell:

   ```powershell
   ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\abvorn_oracle -C "abvorn@oracle"
   Get-Content $env:USERPROFILE\.ssh\abvorn_oracle.pub
   ```

   Paste the `.pub` content into Oracle.
5. Create. Wait for the state to become **Running**. Copy the **Public IP**.

Security list: leave defaults (SSH 22 ingress only). The site is GitHub
Pages, so we don't open 80/443. See §8 if you later add n8n or a click server.

## 2. Prepare secrets

On your PC, copy the template and fill in every key (one value per line,
quote values containing spaces; `GA4_CREDENTIALS_JSON` must be a single line):

```powershell
Copy-Item deploy\vps\.env.example deploy\vps\.env
notepad deploy\vps\.env
```

The exact keys needed by the cycle and the daemon are listed in the template.
Missing keys just degrade that feature (e.g., no GA4 creds → simulated clicks),
so filling everything is what makes the autonomous loop real.

## 3. Upload secrets and run setup

```powershell
ssh -i $env:USERPROFILE\.ssh\abvorn_oracle ubuntu@<PUBLIC_IP>
```

On the box:

```bash
scp deploy/vps/.env   # (do this from your PC instead — see below)
```

Simplest: from PowerShell on your PC:

```powershell
scp -i $env:USERPROFILE\.ssh\abvorn_oracle deploy\vps\.env ubuntu@<PUBLIC_IP>:/tmp/.env
ssh -i $env:USERPROFILE\.ssh\abvorn_oracle ubuntu@<PUBLIC_IP> "sudo bash -c 'curl -sL https://raw.githubusercontent.com/Abvorn-Media/abvorn/main/deploy/vps/setup.sh -o /tmp/setup.sh && bash /tmp/setup.sh --env-file /tmp/.env'"
```

What setup does (idempotent): installs Python 3.11 + pango libs, creates the
`abvorn` user, clones/pulls the repo to `/opt/abvorn/abvorn`, venv + deps,
installs your `.env`, materializes `~/.abvorn/boardroom/secrets.json` for the
daemon, runs **one initial content cycle**, then installs + starts:

- `abvorn-daemon.service` — the 24/7 organism
- `abvorn-cycle.timer` — content cycle at 03:50 / 09:50 / 15:50 / 21:50 UTC
  (offset from the GitHub Actions schedules so their pushes rarely collide)

## 4. Verify

```bash
systemctl status abvorn-daemon abvorn-cycle.timer
journalctl -u abvorn-daemon -f          # daemon life
tail -n 100 /opt/abvorn/abvorn/data/cycle-run.log   # last cycle
curl -s https://abvorn.com | head       # site still live
```

## 5. Ops

- Restart daemon: `sudo systemctl restart abvorn-daemon`
- Trigger a cycle now: `sudo systemctl start abvorn-cycle`
- Watch cycles: `sudo journalctl -u abvorn-cycle -f`
- Stop everything: `sudo systemctl disable --now abvorn-daemon abvorn-cycle.timer`

Failures ping your Telegram from the cycle script; the daemon restarts itself
on crash (`Restart=on-failure`).

## 6. Genesis / evolution (optional, explicit)

The genesis child-core transfer (`GenesisProtocol.transfer_genome` +
`start.sh`, parent dies at evolution) is **entitlement-gated by design** —
operator approval is the gate. To enable it:

```bash
sudo bash /opt/abvorn/abvorn/deploy/vps/setup.sh --with-evolution
tmux new -s evolve
cd /opt/abvorn/abvorn && /opt/abvorn/venv/bin/python run_evolution.py
```

`run_evolution.py` keeps one RelentlessCore alive; after ~10 drive cycles it
calls `spawn_child`, which writes a `../abvorn_vN+1/` genome, launches
`start.sh` (a `run_cycle.py --genesis-version N+1` child in the background),
then exits the parent **on purpose**. Run one evolution at a time in tmux;
after the child starts, `Ctrl-b d` to detach and check
`/opt/abvorn/abvorn/data/genesis/` for lineage + death certificates.

Without `--with-evolution`, evolution requests stay blocked (safe default).

## 7. GitHub Actions becomes backup

The workflows stay enabled, so even if the VPS is down, content keeps being
published. After the VPS has run stable for ~2 weeks, disable the CI schedules
(`content-cycle.yml`, `abvorn-daily.yml`) in the Actions UI to stop double
work — keep `workflow_dispatch` for manual emergency runs.

## 8. Later: n8n / click tracking (not installed by default)

The 5 n8n workflows in `n8n/` need credentials that are per-credential, so
they're left out of the base pack. To add: install n8n (Docker), import the
JSONs, fill credentials, and open port 5678. Real `/click/` affiliate
attribution (click-redirect server + `clicks.db`) is a separate future leg —
the pages don't emit `/click/` links yet, and GA4 is the engagement source
until then.