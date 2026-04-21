/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        accent: '#1D4ED8',          // blue-700  — single accent
        'accent-hover': '#1E40AF', // blue-800
      },
      lineHeight: {
        body: '1.6',
      },
    },
  },
  plugins: [],
}
