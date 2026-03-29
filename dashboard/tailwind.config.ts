import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Primary accent — violet/purple
        primary: {
          DEFAULT: '#10b981', // emerald-500
          dark: '#34d399',    // emerald-400
          foreground: '#ffffff',
        },
        // Danger — safety veto, errors
        danger: {
          DEFAULT: '#dc2626',
          dark: '#ef4444',
          foreground: '#ffffff',
        },
        // Warning — divergent agents, moderate confidence
        warning: {
          DEFAULT: '#f59e0b',
          dark: '#fbbf24',
          foreground: '#ffffff',
        },
        // Confidence bars (high)
        confidence: {
          high: '#10b981',   // emerald-500 — high confidence
          mid: '#f59e0b',    // amber
          low: '#94a3b8',    // slate-400
        },
      },
      borderRadius: {
        card: '1rem',        // rounded-[1rem] for main cards
      },
      boxShadow: {
        card: '0 1px 3px 0 rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
        'card-hover': '0 4px 12px 0 rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.06)',
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
export default config
