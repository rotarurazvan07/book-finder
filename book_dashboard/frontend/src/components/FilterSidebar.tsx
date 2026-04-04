import { useEffect, useState } from 'react';
import { fetchFilters } from '../api/books';
import type { ActiveFilters, FiltersResponse } from '../types';

interface Props {
    filters: ActiveFilters;
    onChange: (f: ActiveFilters) => void;
}

export default function FilterSidebar({ filters, onChange }: Props) {
    const [meta, setMeta] = useState<FiltersResponse | null>(null);

    useEffect(() => {
        fetchFilters().then(setMeta).catch(console.error);
    }, []);

    function set(patch: Partial<ActiveFilters>) {
        onChange({ ...filters, ...patch });
    }

    function toggleCat(cat: string) {
        const next = filters.categories.includes(cat)
            ? filters.categories.filter(c => c !== cat)
            : [...filters.categories, cat];
        set({ categories: next });
    }

    function toggleStore(store: string) {
        const next = filters.stores.includes(store)
            ? filters.stores.filter(s => s !== store)
            : [...filters.stores, store];
        set({ stores: next });
    }

    function reset() {
        onChange({
            search: '',
            categories: [],
            stores: [],
            min_rating: 0,
            min_price: null,
            max_price: null,
            sort_by: 'title',
            sort_dir: 'asc',
        });
    }

    return (
        <aside className="w-56 shrink-0 space-y-6">
            {/* Search */}
            <div>
                <label className="filter-label">Search</label>
                <input
                    className="field"
                    placeholder="Title or author…"
                    value={filters.search}
                    onChange={e => set({ search: e.target.value })}
                />
            </div>

            {/* Sort */}
            <div>
                <label className="filter-label">Sort by</label>
                <select
                    className="field"
                    value={`${filters.sort_by}:${filters.sort_dir}`}
                    onChange={e => {
                        const [by, dir] = e.target.value.split(':') as [ActiveFilters['sort_by'], 'asc' | 'desc'];
                        set({ sort_by: by, sort_dir: dir });
                    }}
                >
                    <option value="title:asc">Title A→Z</option>
                    <option value="title:desc">Title Z→A</option>
                    <option value="author:asc">Author A→Z</option>
                    <option value="price:asc">Price low→high</option>
                    <option value="price:desc">Price high→low</option>
                    <option value="rating:desc">Most popular</option>
                </select>
            </div>

            {/* Price range */}
            <div>
                <label className="filter-label">Price (RON)</label>
                <div className="flex gap-2">
                    <input
                        className="field"
                        type="number"
                        placeholder="Min"
                        min={0}
                        value={filters.min_price ?? ''}
                        onChange={e => set({ min_price: e.target.value ? +e.target.value : null })}
                    />
                    <input
                        className="field"
                        type="number"
                        placeholder="Max"
                        min={0}
                        value={filters.max_price ?? ''}
                        onChange={e => set({ max_price: e.target.value ? +e.target.value : null })}
                    />
                </div>
            </div>

            {/* Categories */}
            {meta && meta.categories.length > 0 && (
                <div>
                    <label className="filter-label">Category</label>
                    <div className="space-y-1 max-h-60 overflow-y-auto pr-1">
                        {meta.categories.map(cat => (
                            <label key={cat} className="flex items-center gap-2 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={filters.categories.includes(cat)}
                                    onChange={() => toggleCat(cat)}
                                    className="accent-navy"
                                />
                                <span className="text-sm font-sans text-ink group-hover:text-navy
                                 transition-colors line-clamp-1">
                                    {cat}
                                </span>
                            </label>
                        ))}
                    </div>
                </div>
            )}

            {/* Stores */}
            {meta && meta.stores.length > 0 && (
                <div>
                    <label className="filter-label">Store</label>
                    <div className="space-y-1">
                        {meta.stores.map(store => (
                            <label key={store} className="flex items-center gap-2 cursor-pointer group">
                                <input
                                    type="checkbox"
                                    checked={filters.stores.includes(store)}
                                    onChange={() => toggleStore(store)}
                                    className="accent-navy"
                                />
                                <span className="text-sm font-sans text-ink group-hover:text-navy transition-colors">
                                    {store}
                                </span>
                            </label>
                        ))}
                    </div>
                </div>
            )}

            {/* Reset */}
            <button className="btn-ghost w-full" onClick={reset}>
                Reset filters
            </button>
        </aside>
    );
}