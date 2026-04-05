/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ['./src/opentrend/templates/**/*.html'],
  theme: {
    extend: {
      fontFamily: { mono: ['IBM Plex Mono', 'monospace'] },
      colors: {
        bg: { DEFAULT: '#111116', raised: '#1c1c24' },
        border: { DEFAULT: '#363642', subtle: '#2a2a36' },
        fg: { DEFAULT: '#d4d4dc', bright: '#f0f0f4', dim: '#9090a0', faint: '#6a6a7a' },
        accent: { teal: '#5eead4' },
      },
    },
  },
  plugins: [],
}
