/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          975: '#08090F',
          950: '#0B0D14',
          900: '#11141D',
          850: '#161A26',
          800: '#1C2030',
          750: '#232839',
          700: '#2A3045',
          600: '#363D54',
          500: '#4A5168',
          400: '#7C8497',
          300: '#A1A8BB',
          200: '#C9CFDC',
          100: '#E6EAF2',
          50: '#F4F6FA',
        },
        brand: {
          blue: '#3D7BFF',
          blueDark: '#2D5FE0',
          indigo: '#6366F1',
          violet: '#8B5CF6',
          fuchsia: '#D946EF',
          teal: '#14D9B0',
          tealDark: '#0FB897',
          amber: '#FBB13B',
          orange: '#FF8A4C',
          red: '#FF4D6D',
          purple: '#8B5CF6',
        },
      },
      borderRadius: {
        'xl2': '14px',
      },
      boxShadow: {
        soft: '0 1px 0 rgba(255,255,255,0.04) inset, 0 8px 24px rgba(0,0,0,0.30)',
        glow: '0 0 0 1px rgba(61,123,255,0.30), 0 12px 36px -8px rgba(61,123,255,0.45)',
        sherpa: '0 16px 56px -16px rgba(0,0,0,0.65), 0 0 0 1px rgba(255,255,255,0.04)',
        chip: '0 1px 0 rgba(255,255,255,0.06) inset, 0 4px 16px rgba(0,0,0,0.25)',
      },
      backgroundImage: {
        'sherpa-gradient': 'linear-gradient(135deg,#3D7BFF 0%,#8B5CF6 60%,#D946EF 100%)',
        'cta-gradient': 'linear-gradient(135deg,#3D7BFF 0%,#6366F1 100%)',
        'cta-gradient-hover': 'linear-gradient(135deg,#2D5FE0 0%,#5457E0 100%)',
        'panel-gradient': 'linear-gradient(180deg,#1C2030 0%,#161A26 100%)',
        'hero-gradient':
          'radial-gradient(1200px 320px at 0% -20%, rgba(61,123,255,0.18), transparent 60%), radial-gradient(800px 240px at 100% 0%, rgba(139,92,246,0.12), transparent 60%)',
        'dot-grid': 'radial-gradient(circle, #2A3045 1px, transparent 1px)',
      },
      backgroundSize: {
        'dot-22': '22px 22px',
      },
      fontFamily: {
        sans: [
          'Pretendard',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'system-ui',
          'sans-serif',
        ],
        mono: [
          'Fira Code',
          'JetBrains Mono',
          'Menlo',
          'Consolas',
          'monospace',
        ],
      },
      fontSize: {
        'display': ['38px', { lineHeight: '1.15', letterSpacing: '-0.02em', fontWeight: '800' }],
        'h1': ['28px', { lineHeight: '1.2', letterSpacing: '-0.015em', fontWeight: '800' }],
        'h2': ['20px', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '700' }],
        'h3': ['15px', { lineHeight: '1.4', fontWeight: '700' }],
      },
      animation: {
        'fade-up': 'fadeUp 0.35s ease-out both',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
