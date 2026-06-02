/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'sans-serif'],
        display: ['"DM Sans"', 'sans-serif'],
        mono: ['"DM Sans"', 'sans-serif'],
        body: ['"DM Sans"', 'sans-serif'],
      },
      colors: {
        navy: {
          950: '#03060f',
          900: '#060d1f',
          800: '#0a1330',
          700: '#0f1c45',
          600: '#162257',
        },
        cyan: {
          glow: '#00f5ff',
          soft: '#38bdf8',
        },
        electric: '#0ff',
      },
      boxShadow: {
        neon: '0 0 20px rgba(0,245,255,0.3), 0 0 60px rgba(0,245,255,0.1)',
        card: '0 4px 32px rgba(0,0,0,0.5)',
        'card-hover': '0 8px 48px rgba(0,0,0,0.7), 0 0 30px rgba(0,245,255,0.15)',
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgba(0,245,255,0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(0,245,255,0.04) 1px, transparent 1px)',
        'glow-radial': 'radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,245,255,0.15), transparent)',
      },
      backgroundSize: {
        grid: '40px 40px',
      },
      animation: {
        'pulse-slow': 'pulse 4s ease-in-out infinite',
        'shimmer': 'shimmer 2.5s linear infinite',
        'fade-up': 'fadeUp 0.6s ease forwards',
      },
      keyframes: {
        shimmer: {
          '0%': { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
