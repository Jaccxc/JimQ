import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Inter variable(self-host woff2),fallback -apple-system/system-ui 由 theme.css 的 --font-sans 控。
import '@fontsource-variable/inter'
// 設計系統底座:Tailwind v4 + 玻璃 token(改版 S1)。必須在 App 掛載前載入。
import './styles/theme.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
