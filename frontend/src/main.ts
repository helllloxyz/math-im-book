import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'katex/dist/katex.min.css'
import 'katex/dist/contrib/copy-tex'
import './style.css'
import App from './App.vue'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
