/** @type {import('tailwindcss').Config} */
// 2026-05-22: 블룸버그 단말기 스타일 리디자인 — 순흑 배경·플랫 패널·각진 모서리·
// 앰버 주색·기능색(녹/적/시안)·고밀도. 그라데이션·글로우·라운드 제거.
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    // borderRadius 전역 0 — 단말기 특유의 각진 패널. (rounded-full 만 점·게이지용 유지)
    borderRadius: {
      none: '0',
      sm: '0',
      DEFAULT: '0',
      md: '0',
      lg: '0',
      xl: '0',
      '2xl': '0',
      '3xl': '0',
      xl2: '0',
      full: '9999px',
    },
    extend: {
      colors: {
        // 흑 기반 그레이 스케일 — 950 본문 배경, 900 패널, 700 보더
        ink: {
          975: '#000000',
          950: '#050506',
          900: '#0C0C0F',
          850: '#121216',
          800: '#17171C',
          750: '#1E1E24',
          700: '#2A2A31',
          600: '#3A3A43',
          500: '#55555F',
          400: '#7B7B86',
          300: '#9A9AA4',
          200: '#C2C2C9',
          100: '#E6E6EA',
          50: '#F4F4F6',
        },
        brand: {
          // 시안 — 링크·네비 활성·정보 (블룸버그 보조색)
          blue: '#36A3D9',
          blueDark: '#2A86B5',
          indigo: '#5B8FB0',
          violet: '#9B7BD4',
          fuchsia: '#C065C8',
          // 녹 — 긍정·상승·정상
          teal: '#26C281',
          tealDark: '#1FA66C',
          // 앰버 — 주색 (블룸버그 시그니처)
          amber: '#FF9500',
          orange: '#FF7A1A',
          // 적 — 경보·하락·위험
          red: '#F5414F',
          purple: '#9B7BD4',
        },
      },
      boxShadow: {
        // 단말기 — 그림자·글로우 없음. 클래스 호환 위해 이름만 유지하고 평탄화.
        soft: '0 0 0 1px rgba(255,255,255,0.02)',
        glow: '0 0 0 1px rgba(255,149,0,0.35)',
        sherpa: '0 0 0 1px rgba(255,255,255,0.06)',
        chip: 'none',
      },
      backgroundImage: {
        // 그라데이션 제거 — 전부 플랫 단색.
        'sherpa-gradient': 'linear-gradient(0deg,#FF9500,#FF9500)',
        'cta-gradient': 'linear-gradient(0deg,#FF9500,#FF9500)',
        'cta-gradient-hover': 'linear-gradient(0deg,#FF7A1A,#FF7A1A)',
        'panel-gradient': 'linear-gradient(0deg,#0C0C0F,#0C0C0F)',
        'hero-gradient': 'none',
        'dot-grid': 'radial-gradient(circle, #1E1E24 1px, transparent 1px)',
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
          'JetBrains Mono',
          'Fira Code',
          'Consolas',
          'Menlo',
          'monospace',
        ],
      },
      fontSize: {
        // 단말기 — 큰 디스플레이 헤드 축소, 밀도 우선
        'display': ['24px', { lineHeight: '1.2', letterSpacing: '0', fontWeight: '700' }],
        'h1': ['18px', { lineHeight: '1.25', letterSpacing: '0', fontWeight: '700' }],
        'h2': ['15px', { lineHeight: '1.3', letterSpacing: '0', fontWeight: '700' }],
        'h3': ['13px', { lineHeight: '1.35', fontWeight: '700' }],
      },
      animation: {
        'fade-up': 'fadeUp 0.18s ease-out both',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(3px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
