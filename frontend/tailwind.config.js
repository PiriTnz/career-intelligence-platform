/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
          950: '#1e1b4b',
        },
        violet: {
          400: '#a78bfa',
          500: '#8b5cf6',
          600: '#7c3aed',
        },
        score: {
          excellent: '#10b981',
          strong:    '#60a5fa',
          moderate:  '#fbbf24',
          weak:      '#f87171',
        },
      },
      backgroundImage: {
        'gradient-module':   'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%)',
        'gradient-card':     'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.06) 100%)',
        'gradient-glass':    'linear-gradient(135deg, rgba(255,255,255,0.12) 0%, rgba(255,255,255,0.04) 100%)',
        'gradient-hero':     'linear-gradient(160deg, #1e1b4b 0%, #312e81 40%, #4c1d95 100%)',
      },
      boxShadow: {
        'glass':      '0 8px 32px rgba(31, 38, 135, 0.15)',
        'glass-sm':   '0 4px 16px rgba(31, 38, 135, 0.10)',
        'glass-lg':   '0 16px 64px rgba(31, 38, 135, 0.20)',
        'card':       '0 1px 3px rgba(0,0,0,0.05), 0 8px 24px rgba(0,0,0,0.06)',
        'card-hover': '0 4px 6px rgba(0,0,0,0.04), 0 16px 40px rgba(0,0,0,0.10)',
        'drawer':     '-4px 0 40px rgba(0,0,0,0.12)',
      },
      animation: {
        'skeleton':     'skeleton 1.6s ease-in-out infinite',
        'fade-in':      'fadeIn 0.25s ease-out',
        'slide-up':     'slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-right':  'slideRight 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in':     'scaleIn 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        'spin-slow':    'spin 3s linear infinite',
      },
      keyframes: {
        skeleton: {
          '0%, 100%': { opacity: '0.55' },
          '50%':      { opacity: '1' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        slideRight: {
          from: { opacity: '0', transform: 'translateX(100%)' },
          to:   { opacity: '1', transform: 'translateX(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to:   { opacity: '1', transform: 'scale(1)' },
        },
      },
      fontFamily: {
        sans: [
          'Inter', '-apple-system', 'BlinkMacSystemFont',
          'Segoe UI', 'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.25rem',
        '4xl': '1.5rem',
      },
    },
  },
  plugins: [],
}
