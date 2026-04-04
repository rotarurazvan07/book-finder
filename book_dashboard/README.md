# Book Finder — Dashboard

A full-stack web dashboard for browsing, filtering, and analysing the Book Finder
price-tracking database.

```
book-finder/
├── book_dashboard/          ← you are here
│   ├── backend/             FastAPI (Python)
│   ├── frontend/            React 18 + TypeScript + Vite
│   ├── docker-compose.yml
│   └── .env.example
├── book_framework/          shared Python library (used by backend)
├── book_crawler/            scraping jobs
└── merge.db                 SQLite database produced by the crawler
```

---

## Features

| Page | Description |
|---|---|
| **Catalog** | Paginated, searchable, filterable list of all volumes. Filters: category, store, price range. Sort by title, author, price, or popularity. |
| **Recommendations** | Set a budget + preferred subject and the librarian assembles an optimal reading bundle. |
| **Insights** | Collection statistics — total volumes, average price, books per category bar chart, most popular titles. |

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 + |
| Node.js | 20 + |
| npm | 10 + |
| Docker + Compose | 24 + (optional, for containerised run) |

---

## Option A — Local Development

### 1. Backend

```bash
# From repo root
cd book_dashboard/backend

# Create + activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Point to your database (default looks for merge.db at repo root)
# Windows PowerShell
$env:BOOKS_DB_PATH = "..\merge.db"
# macOS / Linux
export BOOKS_DB_PATH=../merge.db

# Start the API server
uvicorn main:app --reload --port 8000
```

The API is now live at **http://localhost:8000**.
Interactive docs: **http://localhost:8000/docs**

---

### 2. Frontend

```bash
# From repo root
cd book_dashboard/frontend

# Install dependencies (first time only)
npm install

# Start the dev server (proxies /api → localhost:8000 automatically)
npm run dev
```

Open **http://localhost:5173** in your browser.

> The Vite dev server is pre-configured to proxy every `/api/*` request to
> `http://localhost:8000`, so no CORS issues during development.

---

## Option B — Docker (Production)

### 1. Configure environment

```bash
cd book_dashboard

# Create your local .env from the example
cp .env.example .env
```

Edit `.env`:

```env
# Path to your SQLite database on the HOST machine
# Can be absolute or relative to book_dashboard/
BOOKS_DB_HOST_PATH=../merge.db

# Port to expose the app on
FRONTEND_PORT=3000
```

### 2. Build and start

```bash
# From inside book_dashboard/
docker compose up --build
```

The dashboard is now live at **http://localhost:3000** (or whatever
`FRONTEND_PORT` you set).

The frontend container handles `/api/*` routing to the backend internally —
only port 3000 is exposed to the host.

### 3. Useful commands

```bash
# Run in background
docker compose up --build -d

# Tail logs
docker compose logs -f

# Stop and remove containers
docker compose down

# Rebuild only the backend after a code change
docker compose up --build backend -d
```

---

## Environment Variables

### Backend

| Variable | Default | Description |
|---|---|---|
| `BOOKS_DB_PATH` | `final_books.db` | Path to the SQLite `.db` file **inside the container** |

### Docker Compose

| Variable | Default | Description |
|---|---|---|
| `BOOKS_DB_HOST_PATH` | `../merge.db` | Path to the `.db` file on the **host** machine |
| `FRONTEND_PORT` | `3000` | Host port the dashboard is served on |

---

## API Reference

All endpoints are prefixed with `/api`.

### `GET /api/books`

Returns a paginated, filtered page of books.

| Query param | Type | Default | Description |
|---|---|---|---|
| `page` | int | `1` | Page number (1-based) |
| `page_size` | int | `24` | Results per page (max 100) |
| `search` | string | — | Full-text search on title + author |
| `categories` | string[] | — | Filter by one or more categories |
| `stores` | string[] | — | Filter by one or more stores |
| `min_price` | float | — | Minimum price (RON) |
| `max_price` | float | — | Maximum price (RON) |
| `sort_by` | string | `title` | `title` \| `author` \| `price` \| `rating` |
| `sort_dir` | string | `asc` | `asc` \| `desc` |

### `GET /api/filters`

Returns available categories, stores, and price bounds for the filter sidebar.

### `GET /api/insights`

Returns aggregate statistics: total volumes, average price, books per category,
and the top-10 most popular titles.

### `POST /api/recommendations`

Body:
```json
{
  "budget": 100,
  "subject": "History",
  "source": "Any Available"
}
```

Returns a curated bundle of books within the budget, sorted by popularity.

---

## Tech Stack

**Backend**
- [FastAPI](https://fastapi.tiangolo.com/) — API framework
- [Pandas](https://pandas.pydata.org/) — DataFrame filtering and aggregation
- [Uvicorn](https://www.uvicorn.org/) — ASGI server

**Frontend**
- [React 18](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/)
- [Vite](https://vitejs.dev/) — build tool and dev server
- [React Router v6](https://reactrouter.com/) — client-side routing
- [Recharts](https://recharts.org/) — bar chart on Insights page
- [Tailwind CSS](https://tailwindcss.com/) — utility-first styling
- [Axios](https://axios-http.com/) — HTTP client

**Infrastructure (Docker)**
- Backend: `python:3.11-slim`
- Frontend: `node:20-alpine` (build) → `nginx:1.27-alpine` (serve)