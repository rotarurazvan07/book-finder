import { useEffect, useState } from 'react';
import {
    BarChart, Bar, XAxis, YAxis, Tooltip,
    ResponsiveContainer, Cell,
} from 'recharts';
import { fetchInsights } from '../api/data';
import type { InsightsResponse } from '../types';

// Same log-normalised popularity as BookRow
const LOG_MAX = Math.log10(5_000_000 + 1);
function popularityLabel(rating: number | null): string {
    if (!rating || rating <= 0) return '—';
    if (rating >= 1_000_000) return `${(rating / 1_000_000).toFixed(1)}M`;
    if (rating >= 1_000) return `${(rating / 1_000).toFixed(0)}K`;
    return String(Math.round(rating));
}
function popularityPct(rating: number | null) {
    if (!rating || rating <= 0) return 0;
    return Math.min(100, (Math.log10(rating + 1) / LOG_MAX) * 100);
}

function StatCard({ label, value }: { label: string; value: string }) {
    return (
        <div className="stat-card fade-in">
            <p className="text-[10px] font-mono tracking-widest uppercase text-mist mb-2">{label}</p>
            <p className="font-serif text-3xl text-navy">{value}</p>
        </div>
    );
}

export default function Insights() {
    const [data, setData] = useState<InsightsResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchInsights().then(setData).catch(e => setError(e.message));
    }, []);

    if (error) return (
        <p className="text-wine text-sm font-sans mt-8">{error}</p>
    );

    if (!data) return (
        <p className="text-mist text-sm font-mono animate-pulse mt-8">Loading insights…</p>
    );

    return (
        <div className="space-y-8 fade-in">
            <div>
                <h1 className="font-serif text-2xl text-ink">Archive Insights</h1>
                <p className="text-sm text-mist mt-1 font-sans">
                    Statistical overview of the current collection
                </p>
            </div>

            {/* ── Stat cards ───────────────────────────────────────────────────── */}
            <div className="grid grid-cols-3 gap-4">
                <StatCard
                    label="Total volumes"
                    value={data.total_volumes.toLocaleString()}
                />
                <StatCard
                    label="Average price"
                    value={`${data.avg_price.toFixed(2)} RON`}
                />
                <StatCard
                    label="Categories"
                    value={String(data.num_categories)}
                />
            </div>

            {/* ── Chart + Top-rated ────────────────────────────────────────────── */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

                {/* Bar chart */}
                <div className="bg-white border border-rule rounded p-6">
                    <h2 className="font-serif text-lg text-ink mb-4">Volumes by Category</h2>
                    <ResponsiveContainer width="100%" height={280}>
                        <BarChart
                            data={data.books_per_category}
                            margin={{ top: 0, right: 0, left: -20, bottom: 40 }}
                        >
                            <XAxis
                                dataKey="category"
                                tick={{ fontSize: 10, fontFamily: 'Outfit', fill: '#8A9BB0' }}
                                angle={-35}
                                textAnchor="end"
                                interval={0}
                            />
                            <YAxis
                                tick={{ fontSize: 10, fontFamily: 'IBM Plex Mono', fill: '#8A9BB0' }}
                            />
                            <Tooltip
                                contentStyle={{
                                    fontFamily: 'Outfit',
                                    fontSize: 12,
                                    border: '1px solid #DDD5C8',
                                    borderRadius: 4,
                                }}
                                cursor={{ fill: '#F6F1E9' }}
                            />
                            <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                                {data.books_per_category.map((_, i) => (
                                    <Cell
                                        key={i}
                                        fill={i % 2 === 0 ? '#1B3A6B' : '#6B1F38'}
                                    />
                                ))}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                {/* Top rated */}
                <div className="bg-white border border-rule rounded p-6">
                    <h2 className="font-serif text-lg text-ink mb-4">Most Popular Volumes</h2>
                    <div className="space-y-3">
                        {data.top_rated.map((book, i) => (
                            <div key={book.rowid ?? i} className="flex items-start gap-3">
                                {/* Rank */}
                                <span className="text-[11px] font-mono text-mist w-5 pt-0.5 shrink-0">
                                    {i + 1}
                                </span>

                                {/* Title + author */}
                                <div className="flex-1 min-w-0">
                                    <p className="font-serif text-[13px] text-ink line-clamp-1">
                                        {book.title}
                                    </p>
                                    {book.author && (
                                        <p className="text-[11px] text-mist font-sans mt-0.5">{book.author}</p>
                                    )}
                                </div>

                                {/* Popularity score + bar */}
                                <div className="flex flex-col items-end gap-1 w-20 shrink-0 pt-0.5">
                                    <span className="text-[10px] font-mono text-gold">
                                        {popularityLabel(book.rating)}
                                    </span>
                                    <div className="w-full h-1 bg-rule rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gold/70 rounded-full"
                                            style={{ width: `${popularityPct(book.rating)}%` }}
                                        />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}