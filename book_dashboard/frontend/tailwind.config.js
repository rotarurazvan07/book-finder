/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{ts,tsx}'],
    theme: {
        extend: {
            colors: {
                ink: '#0D1117',
                page: '#F6F1E9',
                navy: '#1B3A6B',
                wine: '#6B1F38',
                gold: '#B8963E',
                mist: '#8A9BB0',
                rule: '#DDD5C8',
                surface: '#FFFFFF',
            },
            fontFamily: {
                serif: ['"Lora"', 'Georgia', 'serif'],
                sans: ['"Outfit"', 'system-ui', 'sans-serif'],
                mono: ['"IBM Plex Mono"', 'monospace'],
            },
        },
    },
    plugins: [],
};