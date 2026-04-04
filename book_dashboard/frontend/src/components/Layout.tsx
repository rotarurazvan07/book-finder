import { NavLink } from 'react-router-dom';

const LINKS = [
    { to: '/', label: 'Catalog' },
    { to: '/recommendations', label: 'Recommendations' },
    { to: '/insights', label: 'Insights' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
    return (
        <div className="min-h-screen flex flex-col">
            {/* ── Top bar ─────────────────────────────────────────────────────── */}
            <header className="bg-white border-b border-rule sticky top-0 z-50">
                <div className="max-w-[1400px] mx-auto px-6 h-14 flex items-center justify-between">
                    {/* Brand */}
                    <div className="flex items-center gap-2 select-none">
                        <span className="text-wine text-lg leading-none">◈</span>
                        <span className="font-serif italic text-navy text-lg leading-none">Book</span>
                        <span className="font-serif font-bold text-ink text-lg leading-none">Finder</span>
                    </div>

                    {/* Nav */}
                    <nav className="flex items-center gap-8">
                        {LINKS.map(({ to, label }) => (
                            <NavLink
                                key={to}
                                to={to}
                                end={to === '/'}
                                className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                            >
                                {label}
                            </NavLink>
                        ))}
                    </nav>
                </div>
            </header>

            {/* ── Content ─────────────────────────────────────────────────────── */}
            <main className="flex-1 max-w-[1400px] mx-auto w-full px-6 py-8">
                {children}
            </main>

            {/* ── Footer ──────────────────────────────────────────────────────── */}
            <footer className="border-t border-rule bg-white mt-auto">
                <div className="max-w-[1400px] mx-auto px-6 h-10 flex items-center">
                    <span className="text-[11px] text-mist font-mono">
                        Book Finder — Antiquarian Price Tracker
                    </span>
                </div>
            </footer>
        </div>
    );
}