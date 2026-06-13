# Deploying on AWS (single EC2 instance)

This deploys the whole app on **one EC2 box** with Docker: the FastAPI backend, the
SQLite database, the chart files, and the React frontend — all behind Caddy on port 80.
Access is over `http://<your-ec2-ip>` (raw IP, no domain/HTTPS for now).

```
Internet ─► EC2 (Ubuntu, t3.small)
              └─ Caddy :80
                   ├─ /api/*  → backend (uvicorn :8000)  ── SQLite + charts on a volume
                   └─ /*      → built React SPA
```

**Cost:** a `t3.small` is ~$15/mo on-demand; your $150 credit covers ~10 months. (Your
OpenAI usage is billed separately by OpenAI, not AWS.)

---

## 1. Launch the EC2 instance

1. EC2 console → **Launch instance**.
2. **AMI:** Ubuntu Server 24.04 LTS.
3. **Type:** `t3.small` (2 GB RAM — pandas/matplotlib need the headroom; `t3.micro` can OOM).
4. **Key pair:** create/select one so you can SSH in.
5. **Network / security group** — allow inbound:
   - SSH (22) from **My IP**
   - HTTP (80) from **Anywhere (0.0.0.0/0)**
6. **Storage:** 20 GB gp3 is plenty.
7. Launch, then copy the instance's **Public IPv4 address**.

## 2. SSH in and install Docker

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

# Docker + compose plugin
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
sudo usermod -aG docker ubuntu
newgrp docker        # apply the group now (or just log out/in)
```

## 3. Get the code onto the box

```bash
git clone <your-repo-url> app && cd app
```

> If your repo is private, the easiest path is to push it to a private GitHub repo and use
> a [deploy token / SSH deploy key](https://docs.github.com/en/authentication), or just
> `scp` the project folder up.

## 4. Set the OpenAI key

```bash
cp data_analyst/.env.example data_analyst/.env
nano data_analyst/.env          # set OPENAI_API_KEY=sk-...   (save: Ctrl-O, Enter, Ctrl-X)
```

## 5. (Optional) Add the bundled sample dataset

The `data/` folder is gitignored, so `telco_churn.csv` is **not** in the clone. Users can
always **upload their own CSV** without it — but if you want the "Telco churn sample"
button to work, copy the file up from your machine:

```bash
# 1) on the SERVER, make sure the target folder exists:
mkdir -p ~/app/data_analyst/data

# 2) on your LOCAL machine (Windows PowerShell or Git Bash), not the server:
scp -i your-key.pem "data_analyst/data/telco_churn.csv" \
    ubuntu@<EC2_PUBLIC_IP>:~/app/data_analyst/data/telco_churn.csv
```

## 6. Build and run

```bash
docker compose up -d --build      # first build takes a few minutes
docker compose ps                 # both services should be "running"
docker compose logs -f backend    # watch for "Application startup complete"
```

Open **`http://<EC2_PUBLIC_IP>`** in your browser, upload a CSV, and start chatting.

---

## Day-2 operations

```bash
docker compose logs -f            # tail logs
docker compose restart            # restart after a config change
git pull && docker compose up -d --build   # deploy a new version
docker compose down               # stop everything (data in data_analyst/data/ persists)
```

**Backups:** everything stateful lives in `data_analyst/data/` (SQLite db + chart files).
Back it up with `tar czf backup.tgz data_analyst/data` or an EBS snapshot.

---

## ⚠️ Security note — read before sharing the URL

The backend runs **model-written Python in a subprocess sandbox**. The project's stated
threat model is *"buggy, not malicious"*. Because the code the model writes is driven by
user prompts, a determined user could potentially get arbitrary code to run **inside the
backend container** (not your host — Docker gives one layer of isolation, but it is not a
hard security boundary).

For a personal deploy on the raw IP this is acceptable. **Before sharing the URL widely:**
- Harden the sandbox (the README's "Next improvements" calls out swapping the subprocess
  for a Docker/e2b executor — the interface already allows it).
- Add a domain + HTTPS (Caddy does this automatically once a domain points at the box —
  change the `:80` in `app/Caddyfile` to `your.domain.com`).
- Consider basic auth in the Caddyfile to gate access.
