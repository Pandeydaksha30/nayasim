/** @type {import('tailwindcss').Config} */
// Colours point at the CSS variables in app/globals.css so the palette
// is defined in one place.
module.exports = {
  content: ['./app/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        studio: {
          'bg-dark': 'var(--studio-bg-dark)',
          'bg-cream': 'var(--studio-bg-cream)',
          coral: 'var(--studio-coral)',
          'cream-white': 'var(--studio-cream-white)',
          'dark-text': 'var(--studio-dark-text)',
          gray: 'var(--studio-gray)',
        },
        coral: 'var(--studio-coral)',
        'cream-white': 'var(--studio-cream-white)',
        'dark-text': 'var(--studio-dark-text)',
      },
    },
  },
  plugins: [],
};
