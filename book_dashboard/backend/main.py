"""
Classic Librarian — FastAPI Backend
=====================================
Endpoints:
  GET  /api/books            paginated, filtered, sorted catalog
  GET  /api/filters          available categories, stores, price bounds
  GET  /api/insights         stats + top-rated + books-per-category
  POST /api/recommendations  greedy-knapsack bundle within a budget

Environment:
  BOOKS_DB_PATH   path to the SQLite database  (default: final_books.db)

Run:
  uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Allow running from repo root: `uvicorn api.main:app`
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from book_framework.BooksManager import BooksManager  # noqa: E402

# ── App & CORS ────────────────────────────────────────────────────────────────

app = FastAPI(title="Classic Librarian API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── DB bootstrap (lazy, cached) ───────────────────────────────────────────────

DB_PATH = os.getenv("BOOKS_DB_PATH", "final_books.db")
_manager: BooksManager | None = None
_df_cache: pd.DataFrame | None = None


def get_df() -> pd.DataFrame:
    """Load + cache the full DataFrame on first call."""
    global _manager, _df_cache
    if _df_cache is None:
        if not os.path.exists(DB_PATH):
            raise FileNotFoundError(f"Database not found at '{DB_PATH}'. Set the BOOKS_DB_PATH environment variable.")
        _manager = BooksManager(DB_PATH)
        _df_cache = _manager.fetch_all_as_dataframe()
        # Ensure category is always a list
        if "category" in _df_cache.columns:
            _df_cache["category"] = _df_cache["category"].apply(
                lambda x: (
                    x
                    if isinstance(x, list)
                    else (
                        [s.strip() for s in str(x).split(",") if s.strip()]
                        if x and not (isinstance(x, float) and math.isnan(x))
                        else []
                    )
                )
            )
    return _df_cache


def _serialize(row: dict) -> dict:
    """Replace NaN/float-nan with None for clean JSON output."""
    out = {}
    for k, v in row.items():
        if isinstance(v, list):
            out[k] = v
        elif isinstance(v, float) and math.isnan(v) or (pd.isna(v) if not isinstance(v, (list, dict, str, bool)) else False):
            out[k] = None
        else:
            out[k] = v
    return out


def _apply_filters(
    df: pd.DataFrame,
    search: str | None,
    categories: list[str],
    stores: list[str],
    min_rating: float | None,
    min_price: float | None,
    max_price: float | None,
) -> pd.DataFrame:
    if search:
        q = search.strip()
        mask = df["title"].str.contains(q, case=False, na=False) | df["author"].str.contains(q, case=False, na=False)
        df = df[mask]

    if categories:
        cats_lower = [c.lower() for c in categories]
        df = df[df["category"].apply(lambda x: any(c.lower() in cats_lower for c in x) if isinstance(x, list) else False)]

    if stores:
        df = df[df["store"].isin(stores)]

    if min_rating is not None and min_rating > 0:
        df = df[df["rating"].notna() & (df["rating"] >= min_rating)]

    if min_price is not None:
        df = df[df["price"] >= min_price]

    if max_price is not None:
        df = df[df["price"] <= max_price]

    return df


# ── Routes ────────────────────────────────────────────────────────────────────

_SORT_COLUMNS = {"title", "author", "price", "rating"}


@app.get("/api/books")
def get_books(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(24, ge=1, le=100),
    search: str | None = Query(None),
    categories: list[str] = Query(default=[]),
    stores: list[str] = Query(default=[]),
    min_rating: float | None = Query(None, ge=0, le=5),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    sort_by: str = Query("title"),
    sort_dir: str = Query("asc"),
):
    df = get_df()
    filtered = _apply_filters(df, search, categories, stores, min_rating, min_price, max_price)

    col = sort_by if sort_by in _SORT_COLUMNS and sort_by in filtered.columns else "title"
    ascending = sort_dir != "desc"
    filtered = filtered.sort_values(col, ascending=ascending, na_position="last")

    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size))
    start = (page - 1) * page_size
    page_df = filtered.iloc[start : start + page_size]

    books = [_serialize(r) for r in page_df.to_dict("records")]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "books": books,
    }


@app.get("/api/filters")
def get_filters():
    df = get_df()
    all_cats: list[str] = sorted(df["category"].explode().dropna().unique().tolist())
    all_stores: list[str] = sorted(df["store"].dropna().unique().tolist())
    price_min = float(df["price"].min()) if not df.empty else 0.0
    price_max = float(df["price"].max()) if not df.empty else 1000.0
    return {
        "categories": all_cats,
        "stores": all_stores,
        "price_range": {"min": round(price_min, 2), "max": round(price_max, 2)},
    }


@app.get("/api/insights")
def get_insights():
    df = get_df()

    total_volumes = len(df)
    avg_price = round(float(df["price"].mean()), 2) if not df.empty else 0.0

    # Books per category (top 10 by count)
    cats_series = df["category"].explode().dropna()
    num_categories = int(cats_series.nunique())
    bpc = cats_series.value_counts().head(10).rename_axis("category").reset_index(name="count").to_dict("records")

    # Top rated: sort descending by raw rating field (weighted score)
    rated = df[df["rating"].notna() & (df["rating"] > 0)].copy()
    top_rated = rated.nlargest(10, "rating")[["title", "author", "rating", "goodreads_url"]].to_dict("records")
    top_rated = [_serialize(r) for r in top_rated]

    return {
        "total_volumes": total_volumes,
        "avg_price": avg_price,
        "num_categories": num_categories,
        "books_per_category": bpc,
        "top_rated": top_rated,
    }


class RecommendationRequest(BaseModel):
    budget: float
    subject: str = "Any"  # maps to a category substring
    source: str = "Any Available"  # maps to store name


@app.post("/api/recommendations")
def get_recommendations(req: RecommendationRequest):
    df = get_df()

    pool = df[df["price"].notna() & (df["price"] > 0)].copy()

    # Filter by subject/category
    subj = req.subject.strip()
    if subj and subj.lower() not in ("any", "any available", ""):
        pool = pool[
            pool["category"].apply(lambda x: any(subj.lower() in c.lower() for c in x) if isinstance(x, list) else False)
        ]

    # Filter by store
    src = req.source.strip()
    if src and src.lower() not in ("any", "any available", ""):
        pool = pool[pool["store"].str.lower() == src.lower()]

    # Cap to budget
    pool = pool[pool["price"] <= req.budget]

    # Prefer rated books, fallback to unrated
    rated_pool = pool[pool["rating"].notna()].sort_values("rating", ascending=False)
    unrated_pool = pool[pool["rating"].isna()]

    bundle: list[dict] = []
    remaining = float(req.budget)

    for frame in (rated_pool, unrated_pool):
        for _, row in frame.iterrows():
            price = float(row["price"])
            if price <= remaining:
                bundle.append(_serialize(row.to_dict()))
                remaining -= price
                if len(bundle) >= 10:
                    break
        if len(bundle) >= 10:
            break

    total_spent = round(req.budget - remaining, 2)

    return {
        "bundle": bundle,
        "total_spent": total_spent,
        "budget": req.budget,
    }


# ── Dev entry ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("book_dashboard.backend.main:app", host="0.0.0.0", port=8000, reload=True)
