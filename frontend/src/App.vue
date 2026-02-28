<template>
  <div class="app">
    <header class="header">
      <h1>模型性能与精度压测</h1>
      <p class="subtitle">配置测试条件后执行压测并查看报告</p>
    </header>

    <main class="main">
      <section class="card form-card">
        <h2>测试配置</h2>
        <form @submit.prevent="runTest" class="form">
          <div class="field">
            <label for="model_url">模型服务地址</label>
            <input
              id="model_url"
              v-model="form.model_url"
              type="url"
              placeholder="https://api.example.com/v1"
              required
            />
          </div>
          <div class="field">
            <label for="test_tool">测试工具</label>
            <select id="test_tool" v-model="form.test_tool">
              <option value="aiakperf">aiakperf</option>
            </select>
          </div>
          <div class="row">
            <div class="field">
              <label for="input_tokens">输入 Token 长度</label>
              <input
                id="input_tokens"
                v-model.number="form.input_tokens"
                type="number"
                min="1"
                required
              />
            </div>
            <div class="field">
              <label for="output_tokens">输出 Token 长度</label>
              <input
                id="output_tokens"
                v-model.number="form.output_tokens"
                type="number"
                min="1"
                required
              />
            </div>
          </div>
          <div class="row">
            <div class="field">
              <label for="ttft_ms">TTFT (ms)</label>
              <input
                id="ttft_ms"
                v-model.number="form.ttft_ms"
                type="number"
                min="0"
                step="0.1"
                required
              />
            </div>
            <div class="field">
              <label for="tpot_ms">TPOT (ms)</label>
              <input
                id="tpot_ms"
                v-model.number="form.tpot_ms"
                type="number"
                min="0"
                step="0.01"
                required
              />
            </div>
          </div>
          <div class="actions">
            <button type="submit" class="btn primary" :disabled="loading">
              {{ loading ? '测试中…' : '开始测试' }}
            </button>
          </div>
        </form>
      </section>

      <section v-if="result" class="card result-card">
        <h2>压测报告</h2>
        <div v-if="result.success" class="success-badge">测试完成</div>
        <div v-else class="fail-badge">测试异常</div>

        <div v-if="result.summary" class="summary">
          <h3>关键指标</h3>
          <table class="metrics-table">
            <tbody>
              <tr><td>QPS</td><td>{{ result.summary.qps ?? '—' }}</td></tr>
              <tr><td>Mean TTFT</td><td>{{ result.summary.mean_ttft ?? '—' }}</td></tr>
              <tr><td>Mean TPOT</td><td>{{ result.summary.mean_tpot ?? '—' }}</td></tr>
              <tr><td>Total Time</td><td>{{ result.summary.total_time ?? '—' }}</td></tr>
              <tr><td>Num Requests</td><td>{{ result.summary.num_requests ?? '—' }}</td></tr>
              <tr><td>Num Succeed</td><td>{{ result.summary.num_succeed ?? '—' }}</td></tr>
              <tr><td>Num Failed</td><td>{{ result.summary.num_failed ?? '—' }}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="raw-output">
          <h3>原始输出</h3>
          <pre>{{ result.raw_output }}</pre>
        </div>

        <div class="actions">
          <button
            type="button"
            class="btn secondary"
            :disabled="saving"
            @click="saveResult"
          >
            {{ saving ? '保存中…' : '保存到数据库' }}
          </button>
        </div>
      </section>

      <section v-if="error" class="card error-card">
        <h2>错误</h2>
        <p class="error-msg">{{ error }}</p>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

const form = reactive({
  model_url: '',
  test_tool: 'aiakperf',
  input_tokens: 16384,
  output_tokens: 339,
  ttft_ms: 16.7,
  tpot_ms: 0.055,
})

const loading = ref(false)
const saving = ref(false)
const result = ref(null)
const error = ref(null)

const API_BASE = '/api'

async function runTest() {
  loading.value = true
  error.value = null
  result.value = null
  try {
    const res = await fetch(`${API_BASE}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '请求失败')
    result.value = data
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

async function saveResult() {
  if (!result.value) return
  saving.value = true
  error.value = null
  try {
    const res = await fetch(`${API_BASE}/results`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model_url: form.model_url,
        test_tool: form.test_tool,
        input_tokens: form.input_tokens,
        output_tokens: form.output_tokens,
        ttft_ms: form.ttft_ms,
        tpot_ms: form.tpot_ms,
        raw_output: result.value.raw_output || '',
        ...result.value.summary,
      }),
    })
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || '保存失败')
    alert('已保存到数据库')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}
</script>

<style>
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  font-family: 'Segoe UI', system-ui, sans-serif;
  background: #0f1419;
  color: #e6edf3;
  min-height: 100vh;
}
.app {
  max-width: 720px;
  margin: 0 auto;
  padding: 2rem;
}
.header {
  text-align: center;
  margin-bottom: 2rem;
}
.header h1 {
  font-size: 1.75rem;
  font-weight: 600;
  margin: 0 0 0.5rem;
}
.subtitle {
  color: #8b949e;
  margin: 0;
  font-size: 0.95rem;
}
.main {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 1.5rem;
}
.card h2 {
  font-size: 1.1rem;
  margin: 0 0 1rem;
  color: #58a6ff;
}
.card h3 {
  font-size: 0.95rem;
  margin: 1rem 0 0.5rem;
  color: #8b949e;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
.field label {
  font-size: 0.85rem;
  color: #8b949e;
}
.field input,
.field select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #30363d;
  border-radius: 6px;
  background: #0d1117;
  color: #e6edf3;
  font-size: 0.95rem;
}
.field input:focus,
.field select:focus {
  outline: none;
  border-color: #58a6ff;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}
.actions {
  margin-top: 0.5rem;
}
.btn {
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn.primary {
  background: #238636;
  color: #fff;
}
.btn.primary:hover:not(:disabled) {
  background: #2ea043;
}
.btn.secondary {
  background: #21262d;
  color: #e6edf3;
  border: 1px solid #30363d;
}
.btn.secondary:hover:not(:disabled) {
  background: #30363d;
}
.success-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: #238636;
  color: #fff;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.fail-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: #da3633;
  color: #fff;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 1rem;
}
.summary {
  margin-top: 0.5rem;
}
.metrics-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.metrics-table td {
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid #21262d;
}
.metrics-table td:first-child {
  color: #8b949e;
  width: 40%;
}
.raw-output {
  margin-top: 1rem;
}
.raw-output pre {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 1rem;
  overflow: auto;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 320px;
  margin: 0;
}
.error-card .error-msg {
  color: #f85149;
  margin: 0;
}
</style>
