# Deployment Guide

Running Book Finder Dashboard using pre-built
GitHub Container Registry images.

---

## 1 — Install Docker

```bash
# One-liner official install script
curl -fsSL https://get.docker.com | sh

# Add your user to the docker group so you don't need sudo every time
sudo usermod -aG docker $USER

# Log out and back in, then verify
docker --version
docker compose version
```

---

## 2 — Set up the deployment folder

```bash
# Pick wherever you want — home directory is fine
mkdir -p ~/book-finder
cd ~/book-finder
```

Create `docker-compose.yml`:

```bash
nano docker-compose.yml
```

Paste this (replace `YOUR_GITHUB_USERNAME` with your actual username):

```yaml
name: book-finder-dashboard

services:

  backend:
    image: ghcr.io/YOUR_GITHUB_USERNAME/book-finder-backend:latest
    restart: unless-stopped
    environment:
      BOOKS_DB_PATH: /data/books.db
    volumes:
      - ./books.db:/data/books.db:ro
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "python", "-c",
             "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/filters')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  frontend:
    image: ghcr.io/YOUR_GITHUB_USERNAME/book-finder-frontend:latest
    restart: unless-stopped
    ports:
      - "3000:80"
    depends_on:
      backend:
        condition: service_healthy
```

---

## 2b — (Optional) Authenticate if images are private

```bash
# Create a GitHub Personal Access Token with read:packages scope at:
# https://github.com/settings/tokens

echo "YOUR_GITHUB_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

---

## 3 — Copy the database to the Pi

**From your PC** (run this on your PC, not the Pi):

```bash
# Replace pi@raspberrypi.local with your Pi's user@hostname or IP
scp path/to/final_books.db pi@raspberrypi.local:~/book-finder/books.db
```

Or if you're already on the Pi and the file is on a USB drive:

```bash
cp /media/pi/USB_DRIVE/final_books.db ~/book-finder/books.db
```

---

## 4 — Pull and start

```bash
cd ~/book-finder

# Pull both images (arm64 layers will be selected automatically)
docker compose pull

# Start in background
docker compose up -d

# Confirm both containers are healthy
docker compose ps
```

The dashboard is now live at **http://RASPBERRY_PI_IP:3000**

Find your Pi's IP with:
```bash
hostname -I | awk '{print $1}'
```

---

## 5 — Enable autostart on boot

Docker's `restart: unless-stopped` policy already handles container restarts.
To make sure Docker itself starts on boot:

```bash
sudo systemctl enable docker
sudo systemctl enable containerd
```

---

## 6 — Updating the database

Whenever you run a new scrape and have a fresh `final_books.db`, copy it over
and restart only the backend:

```bash
# From your PC
scp final_books.db pi@raspberrypi.local:~/book-finder/books.db

# On the Pi — restart backend to pick up new data (frontend stays up)
docker compose restart backend
```

---

## 7 — Updating to a new image version

When you push to `main` on GitHub, Actions rebuilds and pushes new `:latest`
images automatically. To deploy the update on the Pi:

```bash
cd ~/book-finder
docker compose pull          # fetch new :latest layers
docker compose up -d         # recreate containers with new images

# Optional: remove old dangling image layers to free disk space
docker image prune -f
```

To do this **automatically**, add Watchtower to your compose file:

```yaml
  watchtower:
    image: containrrr/watchtower:1.7.1
    restart: unless-stopped
    environment:
      WATCHTOWER_POLL_INTERVAL: 300     # check every 5 minutes
      WATCHTOWER_CLEANUP: "true"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      # If images are private, mount your docker credentials:
      # - /home/pi/.docker/config.json:/config.json:ro
```

---

## 8 — Useful commands

```bash
# Live logs for both services
docker compose logs -f

# Logs for just the backend
docker compose logs -f backend

# Stop everything
docker compose down

# Check resource usage (CPU, memory)
docker stats
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `frontend` stuck on "starting" | backend healthcheck failing | `docker compose logs backend` — usually a missing or wrong-path `.db` file |
| `pull` fails with 403 | images are private | Authenticate (step 3b) or make packages public (step 2) |
| Page loads but shows "Failed to load" | nginx can't reach backend | Make sure both containers are in the same compose project; `docker compose ps` |
| Slow first load | Pi pulling arm64 layers | Normal on first pull; subsequent starts are fast |
| `exec format error` | Pulled amd64 image on arm64 | The workflow builds both platforms; re-push from a fresh `git push` to regenerate |