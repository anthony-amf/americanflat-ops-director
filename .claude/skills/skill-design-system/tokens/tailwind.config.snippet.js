// Paste this `theme.extend` block into your tailwind.config.js
// Americanflat Design System — Tailwind extension
// Last updated: 2026-05-22

module.exports = {
  theme: {
    extend: {
      colors: {
        af: {
          black:   '#0F0F0F',
          white:   '#FFFFFF',
          grey: {
            4: '#1A1A1A',
            3: '#666666',
            2: '#B3B3B3',
            1: '#E6E6E6',
          },
          red:    '#CE0E2D',
          blue:   '#003595',
        },
      },
      fontFamily: {
        af:    ['"Glacial Indifference"', '"DM Sans"', 'Inter', 'system-ui', 'sans-serif'],
        'af-jp': ['"Hiragino Kaku Gothic Pron"', '"Noto Sans JP"', 'sans-serif'],
      },
      fontSize: {
        // pt-equivalent rem values, with [size, lineHeight]
        'af-h1':         ['3rem',      { lineHeight: '1.15', fontWeight: '700' }],
        'af-h2':         ['1.875rem',  { lineHeight: '1.15', fontWeight: '700' }],
        'af-subhead':    ['1.5rem',    { lineHeight: '1.5',  fontWeight: '400' }],
        'af-descriptor': ['1.5rem',    { lineHeight: '1.5',  fontWeight: '400' }],
        'af-body':       ['1.3125rem', { lineHeight: '1.5',  fontWeight: '400' }],
        'af-footer':     ['0.75rem',   { lineHeight: '1.5',  fontWeight: '400' }],
      },
      borderRadius: {
        'af-sm': '4px',
        'af-md': '8px',
        'af-lg': '16px',
      },
      boxShadow: {
        'af-sm': '0 1px 2px rgba(15, 15, 15, 0.04)',
        'af-md': '0 4px 12px rgba(15, 15, 15, 0.06)',
      },
      maxWidth: {
        'af-page': '1200px',
      },
    },
  },
};

// Usage example:
//   <h1 className="text-af-h1 text-af-black">Walls that welcome you home</h1>
//   <button className="bg-af-black text-af-white px-6 py-3 rounded-af-sm font-bold">
//     Run report
//   </button>
