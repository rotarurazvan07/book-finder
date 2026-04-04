export interface Book {
    rowid: number;
    isbn: string | null;
    title: string;
    author: string | null;
    category: string[];
    rating: number | null; // weighted score: rating_value × ratings_count
    goodreads_url: string | null;
    store: string | null;
    url: string | null;
    price: number | null;
}

export interface BooksResponse {
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
    books: Book[];
}

export interface FiltersResponse {
    categories: string[];
    stores: string[];
    price_range: { min: number; max: number };
}

export interface InsightsResponse {
    total_volumes: number;
    avg_price: number;
    num_categories: number;
    books_per_category: { category: string; count: number }[];
    top_rated: Book[];
}

export interface RecommendationRequest {
    budget: number;
    subject: string;
    source: string;
}

export interface RecommendationResponse {
    bundle: Book[];
    total_spent: number;
    budget: number;
}

export interface ActiveFilters {
    search: string;
    categories: string[];
    stores: string[];
    min_rating: number;
    min_price: number | null;
    max_price: number | null;
    sort_by: 'title' | 'author' | 'price' | 'rating';
    sort_dir: 'asc' | 'desc';
}