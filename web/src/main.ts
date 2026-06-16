import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Inter variable(self-host woff2),fallback -apple-system/system-ui 由 theme.css 的 --font-sans 控。
import '@fontsource-variable/inter'
// 設計系統底座:Tailwind v4 + 玻璃 token(改版 S1)。必須在 App 掛載前載入。
import './styles/theme.css'
// 可切換 app 背景(改版:讓 glassmorphism 顯現)。由 stores/appearance + data-bg 命中。
import './styles/backgrounds.css'
import App from './App.vue'
import router from './router'
import { useAppearanceStore } from './stores/appearance'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
// 在掛載前套用已 persist 的背景到根元素,避免首屏閃預設背景。
useAppearanceStore(pinia).applyToDocument()
app.mount('#app')
