<template>
  <div>
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <div class="filter-group">
        <div class="filter-item">
          <label>最低评分</label>
          <select v-model="minScore">
            <option :value="0">全部</option>
            <option :value="35">≥35</option>
            <option :value="50">≥50</option>
            <option :value="65">≥65</option>
            <option :value="80">≥80</option>
          </select>
        </div>
        <div class="filter-item filter-check">
          <input type="checkbox" id="purchaseOpen" v-model="purchaseOpen" />
          <label for="purchaseOpen">仅可申购</label>
        </div>
      </div>
      <button class="refresh-btn" @click="load" :disabled="loading">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <!-- 数据时间 -->
    <div v-if="dataStatus" class="data-time">
      数据最新：{{ dataStatus.overall_latest || '未知' }}
      <span v-if="dataStatus.overall_lag_days" class="lag">
        滞后 {{ dataStatus.overall_lag_days }} 天
      </span>
    </div>

    <!-- 风险提示 -->
    <div class="risk-tip">
      <span class="risk-icon">⚠️</span>
      <span>数据仅供学习交流，不构成投资建议。市场有风险，投资需谨慎。</span>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="funds.length === 0" class="empty">
      暂无符合条件的套利机会
      <div class="empty-sub">可尝试降低评分阈值或检查数据同步状态</div>
    </div>
    <div v-else class="fund-list">
      <div
        v-for="f in funds"
        :key="f.code"
        class="fund-card"
        @click="goDetail(f.code)"
      >
        <div class="card-header">
          <div class="code-name">
            <span class="code">{{ f.code }}</span>
            <span class="name">{{ f.purchase_info?.fund_name || '未知' }}</span>
          </div>
          <div class="score-badge" :class="scoreClass(f.score)">
            {{ f.score }}
          </div>
        </div>

        <div class="card-meta">
          <span class="signal-tag" :class="scoreClass(f.score)">{{ f.signal }}</span>
          <span v-if="f.purchase_info?.purchase_status" class="purchase-tag" :class="purchaseClass(f.purchase_info)">
            {{ purchaseText(f.purchase_info) }}
          </span>
        </div>

        <div class="metrics">
          <div class="metric">
            <span class="label">溢价率</span>
            <span class="value" :class="f.current_premium > 0 ? 'up' : 'down'">
              {{ f.current_premium != null ? f.current_premium.toFixed(2) + '%' : '-' }}
            </span>
          </div>
          <div class="metric">
            <span class="label">成交额</span>
            <span class="value">{{ f.current_volume != null ? f.current_volume + '万' : '-' }}</span>
          </div>
          <div class="metric">
            <span class="label">申购状态</span>
            <span class="value">{{ f.purchase_info?.purchase_status || '未知' }}</span>
          </div>
          <div class="metric">
            <span class="label">手续费</span>
            <span class="value">{{ f.purchase_info?.fee_pct != null ? f.purchase_info.fee_pct + '%' : '-' }}</span>
          </div>
        </div>

        <div v-if="f.reasons?.plus?.length || f.reasons?.minus?.length" class="reasons">
          <div v-for="r in f.reasons.plus.slice(0, 2)" :key="'+' + r" class="reason plus">
            <span class="reason-mark">+</span>{{ r }}
          </div>
          <div v-for="r in f.reasons.minus.slice(0, 2)" :key="'-' + r" class="reason minus">
            <span class="reason-mark">−</span>{{ r }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api.js'

const router = useRouter()
const funds = ref([])
const loading = ref(false)
const error = ref('')
const minScore = ref(50)
const purchaseOpen = ref(false)
const dataStatus = ref(null)

function scoreClass(score) {
  if (score >= 80) return 'excellent'
  if (score >= 65) return 'good'
  if (score >= 50) return 'medium'
  if (score >= 35) return 'low'
  return 'poor'
}

function purchaseClass(p) {
  if (!p || !p.purchase_status) return 'blocked'
  const s = p.purchase_status
  if (s.includes('开放申购')) return 'open'
  if (s.includes('暂停') || s.includes('封闭') || s.includes('限购0')) return 'blocked'
  if (s.includes('限购')) return 'limited'
  return 'blocked'
}

function purchaseText(p) {
  if (!p || !p.purchase_status) return '未知'
  const s = p.purchase_status
  if (s.includes('开放申购')) return '可申购'
  if (s.includes('暂停') || s.includes('封闭') || s.includes('限购0')) return '不可申购'
  if (s.includes('限购')) return '限额'
  return '未知'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [oppRes, statusRes] = await Promise.all([
      api.opportunities({ min_score: minScore.value, purchase_open: purchaseOpen.value, limit: 50 }),
      api.dataStatus()
    ])
    funds.value = oppRes.data || []
    dataStatus.value = statusRes
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function goDetail(code) {
  router.push(`/fund/${code}`)
}

watch([minScore, purchaseOpen], load)
onMounted(load)
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  background: var(--surface);
  padding: 12px;
  border-radius: var(--radius);
  margin-bottom: 12px;
  border: 1px solid var(--border);
  flex-wrap: wrap;
}

.filter-group {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text);
}

.filter-item label {
  color: var(--text-muted);
  font-size: 12px;
}

.filter-item select {
  padding: 5px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--input);
  background: var(--surface);
  color: var(--text);
  font-size: 13px;
}

.filter-check input {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
}

.refresh-btn {
  background: var(--primary);
  color: var(--primary-foreground);
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.16s ease;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.data-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
  text-align: center;
}

.data-time .lag {
  color: var(--danger);
  margin-left: 4px;
}

.risk-tip {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  background: var(--warning-subtle);
  color: var(--warning-text);
  padding: 10px 12px;
  border-radius: var(--radius);
  font-size: 12px;
  line-height: 1.5;
  margin-bottom: 12px;
  border: 1px solid var(--warning-border);
}

.risk-icon {
  flex: none;
  line-height: 1.5;
}

.loading,
.error,
.empty {
  text-align: center;
  padding: 48px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.error {
  color: var(--danger);
}

.empty-sub {
  font-size: 12px;
  color: var(--text-subtle);
  margin-top: 8px;
}

.fund-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fund-card {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 14px;
  border: 1px solid var(--border);
  transition: border-color 0.16s ease, background-color 0.16s ease;
  cursor: pointer;
}

.fund-card:active {
  background: var(--surface-muted);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 8px;
  gap: 8px;
}

.code-name {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.code {
  font-weight: 700;
  font-size: 16px;
  letter-spacing: var(--tracking-tight);
}

.name {
  font-size: 13px;
  color: var(--text-muted);
}

.score-badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  color: white;
  flex: none;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.signal-tag {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  color: white;
}

.purchase-tag {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
}

.purchase-tag.open {
  background: var(--success-subtle);
  color: var(--success-text);
}

.purchase-tag.limited {
  background: var(--warning-subtle);
  color: var(--warning-text);
}

.purchase-tag.blocked {
  background: var(--danger-subtle);
  color: var(--danger-text);
}

/* score scale — monochrome depth */
.excellent { background: var(--brand-900); }
.good { background: var(--brand-700); }
.medium { background: var(--brand-500); }
.low { background: var(--brand-400); }
.poor { background: var(--brand-300); color: var(--brand-800); }

.metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.metric {
  background: var(--surface-muted);
  border-radius: var(--radius-sm);
  padding: 10px;
  text-align: center;
}

.metric .label {
  display: block;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.metric .value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.reasons {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
}

.reason {
  display: flex;
  align-items: baseline;
  gap: 6px;
  line-height: 1.5;
}

.reason.plus {
  color: var(--success-text);
}

.reason.minus {
  color: var(--danger-text);
}

.reason-mark {
  font-weight: 700;
  flex: none;
}

@media (max-width: 380px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .filter-group {
    justify-content: space-between;
  }

  .refresh-btn {
    width: 100%;
  }
}
</style>
