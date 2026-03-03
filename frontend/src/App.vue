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
            <label for="model_url"><span class="required">*</span> 模型服务地址</label>
            <input
              id="model_url"
              v-model="form.model_url"
              type="text"
              placeholder="qianfan.baidubce.com"
              required
            />
          </div>
          <div class="field">
            <label for="auth_header">模型服务 API Key</label>
            <input
              id="auth_header"
              v-model="form.auth_header"
              type="text"
              placeholder="选填，如 Bearer xxx"
            />
          </div>
          <div class="field">
            <label for="model"><span class="required">*</span> 模型</label>
            <input
              id="model"
              v-model="form.model"
              type="text"
              placeholder="deepseek-r1-distill-qwen-32b"
              required
            />
          </div>
          <div class="field">
            <label for="test_tool"><span class="required">*</span> 测试工具</label>
            <select id="test_tool" v-model="form.test_tool">
              <option value="aiakperf">aiakperf</option>
            </select>
          </div>
          <div class="row">
            <div class="field">
              <label for="input_tokens"><span class="required">*</span> 输入 Token 长度</label>
              <input
                id="input_tokens"
                v-model.number="form.input_tokens"
                type="number"
                min="1"
                required
              />
            </div>
            <div class="field">
              <label for="output_tokens"><span class="required">*</span> 输出 Token 长度</label>
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
              <label for="n_value"><span class="required">*</span> 发包数量</label>
            <input
              id="n_value"
              v-model.number="form.n_value"
              type="number"
              min="2"
              required
              title="发包数量必须大于等于 2"
            />
            </div>
            <div class="field">
              <label for="qps_value"><span class="required">*</span> 发包 QPS</label>
            <input
              id="qps_value"
              v-model.number="form.qps_value"
              type="number"
              required
            />
            </div>
          </div>
          <div class="field">
            <label for="dataset">数据集</label>
            <input
              id="dataset"
              v-model="form.dataset"
              type="text"
              placeholder="raw_sharegpt"
            />
          </div>
          <div class="field">
            <label for="requestor">发包接口类型</label>
            <select id="requestor" v-model="form.requestor">
              <option value="openai" title="openai 的 /v1/completions 接口">openai（/v1/completions）</option>
              <option value="openai_chat" title="openai 的 /v1/chat/completions 接口">openai_chat（/v1/chat/completions）</option>
              <option value="qianfan_v2" title="千帆 v2 接口">qianfan_v2（千帆 v2）</option>
              <option value="sglang" title="sglang 的原生 /generate 接口">sglang（/generate）</option>
              <option value="vllm" title="vllm 的原生 /generate 接口">vllm（/generate）</option>
            </select>
          </div>
          <div class="actions">
            <button type="submit" class="btn primary" :disabled="loading">
              {{ loading ? '测试中…' : '单次性能测试' }}
            </button>
          </div>
        </form>
      </section>

      <section v-if="streamingOutput !== null || result" class="card result-card">
        <h2>压测报告</h2>
        <div v-if="loading" class="streaming-badge">流式输出中…</div>
        <div v-else-if="result?.success" class="success-badge">测试完成</div>
        <div v-else-if="result && !result.success" class="fail-badge">测试异常</div>

        <div v-if="result?.summary" class="summary">
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

        <div class="report-output">
          <div class="report-header">
            <h3>测试报告</h3>
          </div>
          <pre ref="reportBodyRef" class="raw-pre">{{ displayRawOutput }}</pre>
        </div>

        <div class="actions">
          <button
            type="button"
            class="btn secondary"
            :disabled="saving || loading"
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
import { ref, reactive, computed, watch, nextTick, onMounted } from 'vue'

const form = reactive({
  model_url: 'qianfan.baidubce.com',
  auth_header: '',
  model: 'deepseek-r1-distill-qwen-32b',
  test_tool: 'aiakperf',
  input_tokens: 64,
  output_tokens: 64,
  n_value: 2,
  qps_value: 1,
  dataset: 'raw_sharegpt',
  requestor: 'qianfan_v2',
})

const loading = ref(false)
const saving = ref(false)
const result = ref(null)
const streamingOutput = ref('')
const error = ref(null)
const displayRawOutput = computed(() => {
  if (result.value?.raw_output) return result.value.raw_output
  return streamingOutput.value || ''
})

const reportBodyRef = ref(null)
watch(streamingOutput, () => {
  nextTick(() => {
    reportBodyRef.value?.scrollTo?.({ top: reportBodyRef.value.scrollHeight, behavior: 'smooth' })
  })
})

const API_BASE = '/api'

onMounted(async () => {
  try {
    const res = await fetch('/config.json')
    if (res.ok) {
      const data = await res.json()
      if (data.defaultApiKey != null && data.defaultApiKey !== '') {
        form.auth_header = String(data.defaultApiKey)
      }
    }
  } catch {
    // 无 config.json 或解析失败时保持空
  }
})

async function runTest() {
  if (form.n_value < 2) {
    error.value = '发包数量必须大于等于 2'
    return
  }
  loading.value = true
  error.value = null
  result.value = null
  streamingOutput.value = ''
  try {
    const body = {
      tool: form.test_tool,
      model: form.model || undefined,
      api_address: form.model_url || undefined,
      auth_header: form.auth_header || undefined,
      if_value: String(form.input_tokens),
      of_value: String(form.output_tokens),
      n_value: String(form.n_value),
      qps_value: String(form.qps_value),
      dataset: form.dataset || undefined,
      requestor: form.requestor || undefined,
    }
    const res = await fetch(`${API_BASE}/test/shell`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const text = await res.text()
    if (!text) {
      throw new Error('服务器未返回数据，可能请求超时或服务异常，请检查后端是否正常运行')
    }
    let data
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error('响应格式错误: ' + text.slice(0, 200))
    }
    if (!res.ok) throw new Error(data.detail || data.message || `请求失败: ${res.status}`)
    result.value = data
  } catch (e) {
    error.value = e.message || String(e)
    result.value = { success: false, raw_output: '', summary: null }
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
        ttft_ms: result.value.summary?.mean_ttft ?? 0,
        tpot_ms: result.value.summary?.mean_tpot ?? 0,
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
  max-width: 960px;
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
.card-desc {
  color: #8b949e;
  font-size: 0.9rem;
  margin: -0.5rem 0 1rem 0;
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
.field label .required {
  color: #f85149;
  margin-right: 0.15em;
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
.streaming-badge {
  display: inline-block;
  padding: 0.25rem 0.6rem;
  background: #1f6feb;
  color: #fff;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 1rem;
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
.report-output {
  margin-top: 1rem;
}
.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
.view-toggle {
  display: flex;
  gap: 0.25rem;
}
.toggle-btn {
  padding: 0.3rem 0.6rem;
  font-size: 0.8rem;
  background: #21262d;
  color: #8b949e;
  border: 1px solid #30363d;
  border-radius: 4px;
  cursor: pointer;
}
.toggle-btn:hover {
  color: #e6edf3;
  border-color: #8b949e;
}
.toggle-btn.active {
  background: #238636;
  color: #fff;
  border-color: #238636;
}
.markdown-body {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 1rem;
  overflow: auto;
  font-size: 0.9rem;
  line-height: 1.6;
  max-height: 70vh;
  margin: 0;
}
.markdown-body h1,
.markdown-body h2,
.markdown-body h3 {
  margin: 1rem 0 0.5rem;
  color: #58a6ff;
}
.markdown-body h1 { font-size: 1.25rem; }
.markdown-body h2 { font-size: 1.1rem; }
.markdown-body h3 { font-size: 1rem; }
.markdown-body p { margin: 0.5rem 0; }
.markdown-body ul, .markdown-body ol { margin: 0.5rem 0; padding-left: 1.5rem; }
.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.5rem 0;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid #30363d;
  padding: 0.4rem 0.6rem;
  text-align: left;
}
.markdown-body th {
  background: #21262d;
  color: #8b949e;
  font-weight: 600;
}
.markdown-body tr:nth-child(even) { background: rgba(255,255,255,0.03); }
.markdown-body hr { border: none; border-top: 1px solid #30363d; margin: 1rem 0; }
.markdown-body code {
  background: #21262d;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.85em;
}
.markdown-body strong { color: #e6edf3; }
.raw-pre {
  background: #0d1117;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 1rem;
  overflow: auto;
  font-size: 0.8rem;
  line-height: 1.5;
  max-height: 70vh;
  margin: 0;
}
.error-card .error-msg {
  color: #f85149;
  margin: 0;
}
</style>
