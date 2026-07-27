# NVGS Server: Start Here

This is the only setup file you need to follow. Do not edit the other project
files unless the development copy on Windows is being changed.

Run one section at a time. If a command fails, stop and save the complete error.

## 1. Download the project

```bash
cd ~
git clone https://github.com/KyleJBonachita/NVGS-Server.git
cd NVGS-Server
git status
```

Expected result:

```text
nothing to commit, working tree clean
```

## 2. Check Docker

```bash
docker --version
docker compose version
sudo docker run --rm hello-world
```

Look for `Hello from Docker!`.

## 3. Create private passwords

```bash
cd ~/NVGS-Server
chmod +x scripts/*.sh
./scripts/bootstrap-secrets.sh
```

Do not display or send anything inside `secrets/`.

## 4. Start locally

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build
sudo docker compose ps
```

The initial configuration listens only on `127.0.0.1`. It is not yet exposed
to the production LAN.

Expected services:

- `db`
- `app`
- `caddy`

## 5. If the database fails

Do not delete anything. Collect these diagnostics:

```bash
sudo docker compose ps -a
sudo docker inspect nvgs-server-db-1 \
  --format='Status={{.State.Status}} Exit={{.State.ExitCode}} Error={{.State.Error}}'
sudo docker logs nvgs-server-db-1
```

Save or photograph the complete output, including the line immediately before
`operation not permitted`.

## 6. After all services are healthy

Create the first system-administrator account:

```bash
sudo docker compose exec app python manage.py createsuperuser \
  --email YOUR-NVIDIA-EMAIL@nvidia.com
```

Replace `YOUR-NVIDIA-EMAIL` with your actual email. Do not share the password.

Then open this page on the Ubuntu laptop:

```text
https://localhost/admin/
```

Do not configure a static IP or expose the server to the LAN yet.

## Getting future updates

From the Ubuntu project folder:

```bash
cd ~/NVGS-Server
./scripts/update-ubuntu-server.sh
```

This update command creates a database backup before pulling new code.
