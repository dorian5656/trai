// 文件名：frontend/src/main.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：Vue 应用入口脚本

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
