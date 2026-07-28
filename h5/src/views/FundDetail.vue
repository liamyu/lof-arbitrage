<template>
  <div>
    <div class="back-bar">
      <button class="back-btn" @click="$router.back()">
        <span class="back-icon">←</span>
        <span>返回</span>
      </button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="fund" class="detail">
      <!-- 头部信息 -->
      <div class="detail-header">
        <div class="title-row">
          <h2>{{ fund.code }}</h2>
          <span class="name">{{ fund.purchase_info?.fund_name || '未知' }}</span>
        </div>
        <div class="score-row">
          <div class="big-score" :class="scoreClass(fund.score)">{{ fund.score }}</div>
          <div class="signal" :class="scoreClass(fund.score)">{{ fund.signal }}</div>
        </div>
      </div>

      <!-- 核心指标 -->
      <div class="metric-grid">
        <div class="metric-box">
          <div class="metric-label">当前溢价率</div>
          <div class="metric-value" :class="fund.current_premium > 0 ? 'up' : 'down'">
            {{ fund.current_premium != null ? fund.current_premium.toFixed(2) + '%' : '-' }}
          </div>
        </div>
        <div class="metric-box">
          <div class="metric-label">最新成交额</div>
          <div class="metric-value">{{ fund.current_volume != null ? fund.current_volume + '万' : '-' }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">3日平均溢价</div>
          <div class="metric-value" :class="fund.key_metrics?.premium_3d > 0 ? 'up' : 'down'">
            {{ fund.key_metrics?.premium_3d != null ? fund.key_metrics.premium_3d.toFixed(2) + '%' : '-' }}
          </div>
        </div>
        <div class="metric-box">
          <div class="metric-label">5日平均溢价</div>
          <div class="metric-value" :class="fund.key_metrics?.premium_5d > 0 ? 'up' : 'down'">
            {{ fund.key_metrics?.premium_5d != null ? fund.key_metrics.premium_5d.toFixed(2) + '%' : '-' }}
          </div>
        </div>
      </div>

      <!-- 申购信息 -->
      <div class="section">
        <h3>申购信息</h3>
        <div class="info-row">
          <span>申购状态</span>
          <span class="info-value">
            {{ fund.purchase_info?.purchase_status || '未知' }}
            <span v-if="fund.purchase_info?.purchase_status" class="purchase-tag" :class="purchaseClass(fund.purchase_info)">
              {{ purchaseText(fund.purchase_info) }}
            </span>
          </span>
        </div>
        <div class="info-row">
          <span>赎回状态</span>
          <span>{{ fund.purchase_info?.redeem_status || '未知' }}</span>
        </div>
        <div class="info-row">
          <span>日限额</span>
          <span>{{ fund.purchase_info?.purchase_limit != null ? fund.purchase_info.purchase_limit : '-' }}</span>
        </div>
        <div class="info-row">
          <span>手续费</span>
          <span>{{ fund.purchase_info?.fee_pct != null ? fund.purchase_info.fee_pct + '%' : '-' }}</span>
        </div>
      </div>

      <!-- 评分理由 -->
      <div class="section" v-if="fund.reasons">
        <h3>评分理由</h3>
        <div v-if="fund.reasons.plus?.length" class="reason-list">
          <div v-for="r in fund.reasons.plus" :key="r" class="reason-item plus">
            <span class="reason-mark">+</span>{{ r }}
          </div>
        </div>
        <div v-if="fund.reasons.minus?.length" class="reason-list">
          <div v-for="r in fund.reasons.minus" :key="r" class="reason-item minus">
            <span class="reason-mark">−</span>{{ r }}
          </div>
        </div>
      </div>

      <!-- 历史数据摘要 -->
      <div class="section" v-if="fund.history_summary">
        <h3>数据概览</h3>
        <div class="info-row">
          <span>记录数</span>
          <span>{{ fund.history_summary.record_count }} 条</span>
        </div>
        <div class="info-row">
          <span>数据范围</span>
          <span>{{ fund.history_summary.date_range?.start }} ~ {{ fund.history_summary.date_range?.end }}</span>
        </div>
        <div class="info-row">
          <span>最新价格</span>
          <span>{{ fund.history_summary.latest_price }}</span>
        </div>
      </div>

      <!-- 风险提示 -->
      <div class="risk-box">
        <h4><span class="risk-icon">⚠️</span>风险提示</h4>
        <p>估值非净值，盘中溢价可能快速变化；申购后到账前溢价可能消失；手续费和限额以实际交易为准。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api.js'

const route = useRoute()
const fund = ref(null)
const loading = ref(false)
const error = ref('')

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
    const code = route.params.code
    fund.value = await api.fundDetail(code)
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.back-bar {
  margin-bottom: 12px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 7px 12px;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
  cursor: pointer;
  transition: background-color 0.16s ease;
}

.back-btn:active {
  background: var(--surface-muted);
}

.back-icon {
  color: var(--text-muted);
}

.loading,
.error {
  text-align: center;
  padding: 48px 20px;
  color: var(--text-muted);
  font-size: 14px;
}

.error {
  color: var(--danger);
}

.detail-header {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.title-row h2 {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
}

.title-row .name {
  color: var(--text-muted);
  font-size: 14px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.big-score {
  width: 58px;
  height: 58px;
  border-radius: var(--radius);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: white;
}

.signal {
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 600;
  color: white;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.metric-box {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 14px;
  text-align: center;
  border: 1px solid var(--border);
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}

.metric-value {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text);
}

.section {
  background: var(--surface);
  border-radius: var(--radius);
  padding: 14px;
  margin-bottom: 12px;
  border: 1px solid var(--border);
}

.section h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
  font-size: 14px;
  color: var(--text-muted);
  gap: 8px;
}

.info-row:last-child {
  border-bottom: none;
}

.info-row span:last-child {
  color: var(--text);
  font-weight: 500;
  text-align: right;
}

.info-value {
  display: inline-flex;
  align-items: center;
  gap: 8px;
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

.reason-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.reason-item {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  line-height: 1.6;
}

.reason-item.plus {
  color: var(--success-text);
}

.reason-item.minus {
  color: var(--danger-text);
}

.reason-mark {
  font-weight: 700;
  flex: none;
}

.risk-box {
  background: var(--warning-subtle);
  border-radius: var(--radius);
  padding: 14px;
  color: var(--warning-text);
  font-size: 13px;
  line-height: 1.6;
  border: 1px solid var(--warning-border);
}

.risk-box h4 {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
}

.risk-icon {
  line-height: 1;
}

/* score scale — monochrome depth */
.excellent { background: var(--brand-900); }
.good { background: var(--brand-700); }
.medium { background: var(--brand-500); }
.low { background: var(--brand-400); }
.poor { background: var(--brand-300); color: var(--brand-800); }
</style>
