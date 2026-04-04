import type { Book } from '../types';

// ── Category colours (deterministic by first char) ──────────────────────────
const CAT_COLORS: Record<string, string> = {
    History: 'bg-amber-100  text-amber-800',
    Literature: 'bg-violet-100 text-violet-800',
    Science: 'bg-teal-100   text-teal-800',
    Arts: 'bg-pink-100   text-pink-800',
    Spirituality: 'bg-indigo-100 text-indigo-800',
    Hobbies: 'bg-green-100  text-green-800',
    Business: 'bg-blue-100   text-blue-800',
    'Personal Development': 'bg-orange-100 text-orange-700',
    'Kids & Young Adult': 'bg-lime-100  text-lime-800',
    Other: 'bg-gray-100   text-gray-600',
};

function catColor(cat: string): string {
    return CAT_COLORS[cat] ?? 'bg-gray-100 text-gray-500';
}

// ── Popularity bar (log-normalised, 0-100) ───────────────────────────────────
// rating field = rating_val × ratings_count (e.g. 4.5 × 50 000 = 225 000)
// Reference ceiling: ~5 000 000 = 5.0 × 1 000 000 (top global bestsellers)
const LOG_MAX = Math.log10(5_000_000 + 1);

function popularityPct(rating: number | null): number {
    if (!rating || rating <= 0) return 0;
    return Math.min(100, (Math.log10(rating + 1) / LOG_MAX) * 100);
}

function popularityLabel(rating: number | null): string {
    if (!rating || rating <= 0) return '—';
    if (rating >= 1_000_000) return `${(rating / 1_000_000).toFixed(1)}M`;
    if (rating >= 1_000) return `${(rating / 1_000).toFixed(0)}K`;
    return String(Math.round(rating));
}

// ── Component ────────────────────────────────────────────────────────────────
interface Props { book: Book; index: number; }

export default function BookRow({ book, index }: Props) {
    const pct = popularityPct(book.rating);
    const label = popularityLabel(book.rating);
    const cats = Array.isArray(book.category) ? book.category.slice(0, 2) : [];

    return (
        <div className="group flex items-start gap-4 py-3.5 px-4 border-b border-rule
                    hover:bg-white transition-colors duration-100 fade-in">

            {/* Index */}
            <span className="w-7 shrink-0 text-right text-[11px] font-mono text-rule
                       group-hover:text-mist pt-0.5 transition-colors">
                {index}
            </span>

            {/* Title + Author */}
            <div className="flex-1 min-w-0">
                <p className="font-serif text-[15px] leading-snug text-ink line-clamp-1">
                    {book.title}
                </p>
                {book.author && (
                    <p className="text-[12px] text-mist font-sans mt-0.5 line-clamp-1">
                        {book.author}
                    </p>
                )}
            </div>

            {/* Categories */}
            <div className="hidden md:flex gap-1 items-start pt-0.5 w-52 shrink-0 flex-wrap">
                {cats.map(c => (
                    <span key={c} className={`cat-pill ${catColor(c)}`}>{c}</span>
                ))}
            </div>

            {/* Popularity */}
            <div className="hidden lg:flex flex-col items-end gap-1 w-24 shrink-0 pt-1">
                <span className="text-[10px] font-mono text-mist">{label}</span>
                <div className="w-full h-1 bg-rule rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gold rounded-full transition-all duration-300"
                        style={{ width: `${pct}%` }}
                    />
                </div>
            </div>

            {/* Price */}
            <div className="w-20 shrink-0 text-right">
                {book.price != null ? (
                    <span className="text-[13px] font-mono font-medium text-ink">
                        {book.price.toFixed(2)} <span className="text-[10px] text-mist">RON</span>
                    </span>
                ) : (
                    <span className="text-mist text-xs">—</span>
                )}
            </div>

            {/* Actions */}
            <div className="flex gap-2 shrink-0 items-center pt-0.5">
                {book.url && (
                    <a
                        href={book.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] font-sans font-semibold tracking-widest uppercase
                       text-navy border border-navy/30 px-2 py-1 rounded
                       hover:bg-navy hover:text-white transition-colors duration-100"
                    >
                        Buy
                    </a>
                )}
                {book.goodreads_url && (
                    <a
                        href={book.goodreads_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[10px] font-sans font-semibold tracking-widest uppercase
                       text-wine border border-wine/30 px-2 py-1 rounded
                       hover:bg-wine hover:text-white transition-colors duration-100"
                    >
                        GR
                    </a>
                )}
            </div>
        </div>
    );
}