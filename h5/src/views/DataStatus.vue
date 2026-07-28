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
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.status-card h2 {
  font-size: 16px;
  margin-bottom: 14px;
}

.loading, .error {
  text-align: center;
  padding: 20px;
  color: #999;
}
.error { color: #e74c3c; }

.status-badge {
  display: inline-block;
  padding: 6px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  margin-bottom: 14px;
}

.status-badge.healthy { background: #27ae60; }
.status-badge.degraded { background: #f39c12; }
.status-badge.failed { background: #e74c3c; }
.status-badge.unknown { background: #95a5a6; }

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.info-item {
  background: #f8f9fa;
  border-radius: 10px;
  padding: 12px;
}

.info-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.info-value {
  font-size: 15px;
  font-weight: 600;
}

.info-value.lag {
  color: #e74c3c;
}

.schedule-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.schedule-card h3 {
  font-size: 15px;
  margin-bottom: 12px;
}

.schedule-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.schedule-item {
  background: #f0f4ff;
  color: #667eea;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
}

.schedule-note {
  font-size: 12px;
  color: #999;
  margin-top: 10px;
}

.disclaimer {
  background: white;
  border-radius: 12px;
  padding: 16px;
  font-size: 13px;
  color: #666;
  line-height: 1.8;
}

.disclaimer h3 {
  font-size: 15px;
  color: #333;
  margin-bottom: 8px;
}
</style>
