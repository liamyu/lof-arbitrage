<template>
  <div>
    <!-- 筛选栏 -->
    <div class="filter-bar">
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
      <div class="filter-item">
        <label>仅可申购</label>
        <input type="checkbox" v-model="purchaseOpen" />
      </div>
      <button class="refresh-btn" @click="load" :disabled="loading">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <!-- 风险提示 -->
    <div class="risk-tip">
      ⚠️ 数据仅供学习交流，不构成投资建议。市场有风险，投资需谨慎。
    </div>

    <!-- 数据时间 -->
    <div v-if="dataStatus" class="data-time">
      数据最新: {{ dataStatus.overall_latest || '未知' }}
      <span v-if="dataStatus.overall_lag_days" class="lag">
        (滞后 {{ dataStatus.overall_lag_days }} 天)
      </span>
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
            {{ f.score }}分
          </div>
        </div>
        <div class="signal-tag" :class="scoreClass(f.score)">{{ f.signal }}</div>
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
        <div v-if="f.reasons?.plus?.length" class="reasons plus">
          <div v-for="r in f.reasons.plus.slice(0,2)" :key="r">+ {{ r }}</div>
        </div>
        <div v-if="f.reasons?.minus?.length" class="reasons minus">
          <div v-for="r in f.reasons.minus.slice(0,2)" :key="r">- {{ r }}</div>
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
  background: white;
  padding: 12px;
  border-radius: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
}

.filter-item select {
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid #ddd;
}

.refresh-btn {
  margin-left: auto;
  background: #667eea;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.refresh-btn:disabled {
  opacity: 0.6;
}

.risk-tip {
  background: #fff3cd;
  color: #856404;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 12px;
  margin-bottom: 12px;
}

.data-time {
  font-size: 12px;
  color: #666;
  margin-bottom: 12px;
  text-align: center;
}

.data-time .lag {
  color: #e74c3c;
}

.loading, .error, .empty {
  text-align: center;
  padding: 40px;
  color: #999;
}

.error {
  color: #e74c3c;
}

.empty-sub {
  font-size: 12px;
  color: #bbb;
  margin-top: 8px;
}

.fund-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.fund-card {
  background: white;
  border-radius: 12px;
  padding: 14px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.code-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.code {
  font-weight: 700;
  font-size: 16px;
}

.name {
  font-size: 13px;
  color: #666;
}

.score-badge {
  padding: 4px 10px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 600;
  color: white;
}

.signal-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  margin-bottom: 10px;
  color: white;
}

.excellent { background: #8B0000; }
.good { background: #CD2626; }
.medium { background: #FF4500; }
.low { background: #A0522D; }
.poor { background: #4F4F4F; }

.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 10px;
}

.metric {
  text-align: center;
}

.metric .label {
  display: block;
  font-size: 11px;
  color: #999;
  margin-bottom: 2px;
}

.metric .value {
  font-size: 13px;
  font-weight: 500;
}

.metric .up { color: #e74c3c; }
.metric .down { color: #27ae60; }

.reasons {
  font-size: 12px;
  line-height: 1.6;
}

.reasons.plus { color: #27ae60; }
.reasons.minus { color: #e74c3c; }
</style>
