export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {
    fontFamily: { sans: ['"Schibsted Grotesk"', 'system-ui', 'sans-serif'] },
    colors: { bench: '#e7eded', ink: '#10282f', clean: '#1f5fa8', lost: '#c2255c', swap: '#b7791f', ok: '#0e7c6b' },
  } },
}
