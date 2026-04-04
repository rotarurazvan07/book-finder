import { useEffect, useState } from 'react';
import { fetchRecommendations } from '../api/data';
import { fetchFilters } from '../api/books';
import type { FiltersResponse, RecommendationResponse } from '../types';

export default function Recommendations() {
    const [meta, setMeta] = useState<FiltersResponse | null>(null);
    const [budget, setBudget] = useState<number>(100);
    const [subject, setSubject] = useState('Any');
    const [source, setSource] = useState('Any Available');
    const [result, setResult] = useState<RecommendationResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchFilters().then(setMeta).catch(console.error);
    }, []);

    async function retrieve() {
        setLoading(true);
        setError(null);
        try {
            const res = await fetchRecommendations({ budget, subject, source });
            setResult(res);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    }

    const budgetPct = result
        ? Math.min(100, (result.total_spent / result.budget) * 100)
        : 0;

    return (
        <div className="max-w-2xl mx-auto fade-in">
            <div className="mb-8">
                <h1 className="font-serif text-2xl text-ink">Consult the Librarian</h1>
                <p className="text-sm text-mist mt-1 font-sans">
                    Set your constraints and we'll assemble a curated reading bundle from
                    the archive.
                </p>
            </div>

            {/* ── Form ──────────────────────────────────────────────────────────── */}
            <div className="bg-white border border-rule rounded p-6 space-y-5">
                {/* Budget */}
                <div>
                    <label className="filter-label">Total budget (RON)</label>
                    <div className="relative">
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-mist
                             font-mono text-sm select-none">₲</span>
                        <input
                            className="field pl-7"
                            type="number"
                            min={1}
                            value={budget}
                            onChange={e => setBudget(+e.target.value)}
                        />
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                    {/* Subject */}
                    <div>
                        <label className="filter-label">Preferred subject</label>
                        <select className="field" value={subject} onChange={e => setSubject(e.target.value)}>
                            <option value="Any">Any subject</option>
                            {meta?.categories.map(c => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </select>
                    </div>

                    {/* Source */}
                    <div>
                        <label className="filter-label">Archive source</label>
                        <select className="field" value={source} onChange={e => setSource(e.target.value)}>
                            <option value="Any Available">Any Available</option>
                            {meta?.stores.map(s => (
                                <option key={s} value={s}>{s}</option>
                            ))}
                        </select>
                    </div>
                </div>

                <button
                    className="btn-primary w-full"
                    onClick={retrieve}
                    disabled={loading}
                >
                    {loading ? 'Retrieving…' : '✦  Retrieve volumes'}
                </button>
            </div>

            {/* ── Error ─────────────────────────────────────────────────────────── */}
            {error && (
                <p className="mt-4 text-wine text-sm font-sans">{error}</p>
            )}

            {/* ── Results ───────────────────────────────────────────────────────── */}
            {result && result.bundle.length === 0 && (
                <p className="mt-8 text-center text-mist text-sm font-sans">
                    No volumes found within these constraints.
                </p>
            )}

            {result && result.bundle.length > 0 && (
                <div className="mt-8 fade-in">
                    {/* Bundle header */}
                    <div className="flex items-center justify-between mb-1">
                        <h2 className="font-serif text-lg text-ink">Curated Bundle</h2>
                        <span className="text-sm font-mono">
                            <span className="text-navy font-semibold">
                                {result.total_spent.toFixed(2)}
                            </span>
                            <span className="text-mist"> / {result.budget.toFixed(2)} RON</span>
                        </span>
                    </div>

                    {/* Budget bar */}
                    <div className="h-1 bg-rule rounded-full mb-4 overflow-hidden">
                        <div
                            className="h-full bg-navy rounded-full transition-all duration-500"
                            style={{ width: `${budgetPct}%` }}
                        />
                    </div>

                    {/* Bundle list */}
                    <div className="bg-white border border-rule rounded divide-y divide-rule">
                        {result.bundle.map((book, i) => (
                            <div key={book.rowid ?? i} className="flex items-start gap-4 px-5 py-4
                                                    hover:bg-page transition-colors">
                                <div className="flex-1 min-w-0">
                                    <p className="font-serif text-[15px] text-ink line-clamp-1">
                                        {book.title}
                                    </p>
                                    {book.author && (
                                        <p className="text-xs text-mist font-sans mt-0.5">{book.author}</p>
                                    )}
                                    {book.store && (
                                        <p className="text-[10px] font-mono text-mist mt-1 uppercase tracking-wide">
                                            {book.store}
                                        </p>
                                    )}
                                </div>

                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="font-mono font-semibold text-navy text-sm">
                                        {book.price?.toFixed(2)} RON
                                    </span>
                                    {book.url && (
                                        <a
                                            href={book.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="text-[10px] font-semibold tracking-widest uppercase
                                 text-navy border border-navy/30 px-2 py-1 rounded
                                 hover:bg-navy hover:text-white transition-colors"
                                        >
                                            Buy
                                        </a>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    <p className="text-[11px] font-mono text-mist mt-3 text-right">
                        {result.bundle.length} volumes · {(result.budget - result.total_spent).toFixed(2)} RON remaining
                    </p>
                </div>
            )}
        </div>
    );
}