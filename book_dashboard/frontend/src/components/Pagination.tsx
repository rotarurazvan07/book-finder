interface Props {
    page: number;
    totalPages: number;
    onPageChange: (p: number) => void;
}

export default function Pagination({ page, totalPages, onPageChange }: Props) {
    if (totalPages <= 1) return null;

    // Build page window: always show first, last, current ±2
    const pages: (number | '…')[] = [];
    const add = (n: number) => { if (n >= 1 && n <= totalPages && !pages.includes(n)) pages.push(n); };

    add(1);
    for (let i = page - 2; i <= page + 2; i++) add(i);
    add(totalPages);

    // Insert ellipsis
    const withGaps: (number | '…')[] = [];
    pages.sort((a, b) => (a as number) - (b as number));
    for (let i = 0; i < pages.length; i++) {
        if (i > 0 && (pages[i] as number) - (pages[i - 1] as number) > 1) withGaps.push('…');
        withGaps.push(pages[i]);
    }

    return (
        <div className="flex items-center justify-center gap-1 py-6">
            <button
                className="btn-ghost px-3 py-1.5"
                disabled={page === 1}
                onClick={() => onPageChange(page - 1)}
            >
                ‹
            </button>

            {withGaps.map((p, i) =>
                p === '…' ? (
                    <span key={`gap-${i}`} className="px-2 text-mist text-sm select-none">…</span>
                ) : (
                    <button
                        key={p}
                        onClick={() => onPageChange(p as number)}
                        className={
                            p === page
                                ? 'w-8 h-8 rounded text-xs font-semibold font-sans bg-navy text-white'
                                : 'w-8 h-8 rounded text-xs font-sans text-mist hover:text-ink hover:bg-white transition-colors'
                        }
                    >
                        {p}
                    </button>
                )
            )}

            <button
                className="btn-ghost px-3 py-1.5"
                disabled={page === totalPages}
                onClick={() => onPageChange(page + 1)}
            >
                ›
            </button>
        </div>
    );
}