export default {
  content: ["./index.html","./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: { sans: ['Inter','system-ui','-apple-system','sans-serif'] },
      colors: {
        primary: "#6366f1",
        sofia: { 50:"#eef2ff", 500:"#6366f1", 600:"#4f46e5", 900:"#312e81" },
        brand: { 50:'#f5f3ff', 100:'#ede9fe', 200:'#ddd6fe', 500:'#7c3aed', 600:'#6d28d9', 700:'#5b21b6', 900:'#3b0764' }
      },
      borderRadius: { '2xl': '1rem' }
    }
  },
  plugins: []
}
