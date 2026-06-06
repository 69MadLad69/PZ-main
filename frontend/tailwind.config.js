/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html','./src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT:'#2E75B6', 50:'#EAF2FA', 500:'#2E75B6', 700:'#1D5490' },
        solar:   { DEFAULT:'#F39C12', light:'#FDEBD0' },
        battery: { DEFAULT:'#8E44AD', light:'#F5EEF8' },
        grid:    { DEFAULT:'#27AE60', light:'#EAFAF1' },
        danger:  { DEFAULT:'#E74C3C' },
        warning: { DEFAULT:'#E67E22' },
      },
    },
  },
  plugins: [],
};
