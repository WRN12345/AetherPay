<script setup lang="ts">
import { ref } from 'vue'

const loading = ref(false)
const result = ref('还没有请求')

async function callBackend() {
  loading.value = true
  result.value = '请求中...'

  try {
    const response = await fetch('/api/hello')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    const data = await response.json()
    result.value = `${data.message}（${data.date}）`
  } catch (error) {
    result.value = `请求失败：${String(error)}`
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="container">
    <h1>前后端分离示例</h1>
    <p>前端：Vue | 后端：Python</p>
    <button :disabled="loading" @click="callBackend">
      {{ loading ? '请求中...' : '请求后端 /api/hello' }}
    </button>
    <p class="result">返回结果：{{ result }}</p>
  </main>
</template>

<style scoped>
.container {
  max-width: 680px;
  margin: 80px auto;
  padding: 24px;
  text-align: center;
}

h1 {
  margin-bottom: 12px;
}

button {
  margin-top: 12px;
  padding: 10px 16px;
  border: 1px solid #333;
  border-radius: 8px;
  cursor: pointer;
  background: #fff;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.result {
  margin-top: 18px;
  word-break: break-word;
}
</style>
