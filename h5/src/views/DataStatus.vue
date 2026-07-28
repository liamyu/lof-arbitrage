<template>
  <div>
    <div class="status-card">
      <h2>数据同步状态</h2>
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-else-if="status" class="status-body">
        <div class="status-badge" :class="status.status">
          {{ statusText(status.status) }}
        </div>

        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">最后同步</div>
            <div class="info-value">{{ status.sync_time || '未记录' }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">最新数据</div>
            <div class="info-value">{{ status.overall_latest || '未知' }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">滞后天数</div>
            <div class="info-value" :class="status.overall_lag_days > 2 ? 'lag' : ''">
              {{ status.overall_lag_days != null ? status.overall_lag_days + ' 天' : '未知' }}
            </div>
          </div>
          <div class="info-item">
            <div class="info-label">LOF 总数</div>
            <div class="info-value">{{ status.total_lofs }} 只</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 更新时点说明 -->
    <div class="schedule-card">
      <h3>盘中更新时点</h3>
      <div class="schedule-list">
        <div class="schedule-item">09:30 开盘</div>
        <div class="schedule-item">10:30</div>
        <div class="schedule-item">11:30</div>
        <div class="schedule-item">13:30</div>
        <div class="schedule-item">14:00</div>
        <div class="schedule-item">14:15</div>
        <div class="schedule-item">14:30</div>
        <div class="schedule-item">14:45</div>
        <div class="schedule-item">15:00 收盘</div>
        <div class="schedule-item">21:00 晚间</div>
      </div>
      <p class="schedule-note">仅交易日自动执行，周末和节假日跳过</p>
    </div>

    <!-- 免责声明 -->
    <div class="disclaimer">
      <h3>免责声明</h3>
      <p>本工具仅供投资者学习交流，所选产品仅供参考，不构成任何投资建议。</p>
      <p>市场有风险，投资需谨慎。数据来源：集思录、东方财富。</p>
      <p>实时数据请见官网，本平台可能存在延迟。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api.js'

const status = ref(null)
const loading = ref(false)
const error = ref('')

function statusText(s) {
  const map = { healthy: '健康', degraded: '降级', failed: '异常', unknown: '未知' }
  return map[s] || s
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    status.value = await api.dataStatus()
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.status-card {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
}

.status-card h2 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
  color: var(--text);
}

.loading,
.error {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: 14px;
}

.error {
  color: var(--danger);
}

.status-badge {
  display: inline-flex;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  color: white;
  margin-bottom: 14px;
}

.status-badge.healthy {
  background: var(--success);
}

.status-badge.degraded {
  background: var(--warning);
}

.status-badge.failed {
  background: var(--danger);
}

.status-badge.unknown {
  background: var(--text-subtle);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.info-item {
  background: var(--surface-muted);
  border-radius: var(--radius-sm);
  padding: 12px;
  border: 1px solid var(--border);
}

.info-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 5px;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}

.info-value.lag {
  color: var(--danger);
}

.schedule-card {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
}

.schedule-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.schedule-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.schedule-item {
  background: var(--surface-muted);
  color: var(--text);
  padding: 6px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--border);
}

.schedule-note {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 10px;
}

.disclaimer {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.8;
  border: 1px solid var(--border);
}

.disclaimer h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 8px;
}
</style>
