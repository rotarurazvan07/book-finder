import { useEffect, useRef, useState } from 'react';
import { fetchBooks } from '../api/books';
import BookRow from '../components/BookRow';
import FilterSidebar from '../components/FilterSidebar';
import Pagination from '../components/Pagination';
import type { ActiveFilters, BooksResponse } from '../types';

const DEFAULT_FILTERS: ActiveFilters = {
    search: '',
    categories: [],
    stores: [],
    min_rating: 0,
    min_price: null,
    max_price: null,
    sort_by: 'title',
    sort_dir: 'asc',
};

const PAGE_SIZE = 40;

export default function Catalog() {
    const [filters, setFilters] = useState<ActiveFilters>(DEFAULT_FILTERS);
    const [page, setPage] = useState(1);
    const [data, setData] = useState<BooksResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const topRef = useRef<HTMLDivElement>(null);

    // Reset to page 1 when filters change
    function applyFilters(f: ActiveFilters) {
        setFilters(f);
        setPage(1);
    }

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);

        fetchBooks(page, PAGE_SIZE, filters)
            .then(d => { if (!cancelled) setData(d); })
            .catch(e => { if (!cancelled) setError(e.message); })
            .finally(() => { if (!cancelled) setLoading(false); });

        return () => { cancelled = true; };
    }, [page, filters]);

    function handlePageChange(p: number) {
        setPage(p);
        topRef.current?.scrollIntoView({ behavior: 'smooth' });
    }

    return (
        <div className="flex gap-8">
            <FilterSidebar filters={filters} onChange={applyFilters} />

            {/* ── Main content ──────────────────────────────────────────────── */}
            <div className="flex-1 min-w-0">

                {/* Header row */}
                <div ref={topRef} className="flex items-baseline justify-between mb-4">
                    <div>
                        <h1 className="font-serif text-2xl text-ink">Catalog</h1>
                        {data && (
                            <p className="text-[12px] text-mist mt-0.5 font-mono">
                                {data.total.toLocaleString()} volumes
                                {filters.search && ` matching "${filters.search}"`}
                            </p>
                        )}
                    </div>

                    {/* Quick sort shortcut for mobile-like env */}
                    <span className="text-[11px] font-mono text-mist hidden sm:block">
                        Page {page} of {data?.total_pages ?? '…'}
                    </span>
                </div>

                {/* Column headers */}
                <div className="flex items-center gap-4 px-4 py-2 border-b border-rule
                        text-[10px] font-mono tracking-widest uppercase text-mist select-none">
                    <span className="w-7 text-right">#</span>
                    <span className="flex-1">Title / Author</span>
                    <span className="hidden md:block w-52">Category</span>
                    <span className="hidden lg:block w-24 text-right">Popularity</span>
                    <span className="w-20 text-right">Price</span>
                    <span className="w-16 text-right">Links</span>
                </div>

                {/* States */}
                {error && (
                    <div className="mt-8 text-center text-wine text-sm font-sans">
                        Failed to load: {error}
                    </div>
                )}

                {loading && !data && (
                    <div className="mt-16 text-center text-mist text-sm font-mono animate-pulse">
                        Loading…
                    </div>
                )}

                {/* Book list */}
                {data && (
                    <div className={loading ? 'opacity-60 pointer-events-none' : ''}>
                        {data.books.length === 0 ? (
                            <div className="mt-16 text-center text-mist text-sm font-sans">
                                No volumes match your filters.
                            </div>
                        ) : (
                            data.books.map((book, i) => (
                                <BookRow
                                    key={book.rowid ?? `${book.title}-${i}`}
                                    book={book}
                                    index={(page - 1) * PAGE_SIZE + i + 1}
                                />
                            ))
                        )}

                        <Pagination
                            page={page}
                            totalPages={data.total_pages}
                            onPageChange={handlePageChange}
                        />
                    </div>
                )}
            </div>
        </div>
    );
}