import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#10b981',
          dark: '#34d399',
          foreground: '#ffffff',
        },
        danger: {
          DEFAULT: '#dc2626',
          dark: '#ef4444',
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#f59e0b',
          dark: '#fbbf24',
          foreground: '#ffffff',
        },
      },
      fontFamily: {
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
export default config
