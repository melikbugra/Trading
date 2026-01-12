/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                'terminal-dark': '#0d1117',
                'terminal-green': '#2ea043',
                'terminal-red': '#da3633',
            }
        },
    },
    plugins: [],
}
