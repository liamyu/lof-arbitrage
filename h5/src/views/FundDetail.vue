<template>
  <div>
    <div class="back-bar">
      <button class="back-btn" @click="$router.back()">← 返回</button>
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
          <div class="metric-value">{{ fund.key_metrics?.premium_3d != null ? fund.key_metrics.premium_3d.toFixed(2) + '%' : '-' }}</div>
        </div>
        <div class="metric-box">
          <div class="metric-label">5日平均溢价</div>
          <div class="metric-value">{{ fund.key_metrics?.premium_5d != null ? fund.key_metrics.premium_5d.toFixed(2) + '%' : '-' }}</div>
        </div>
      </div>

      <!-- 申购信息 -->
      <div class="section">
        <h3>申购信息</h3>
        <div class="info-row">
          <span>申购状态</span>
          <span>{{ fund.purchase_info?.purchase_status || '未知' }}</span>
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
        <div v-if="fund.reasons.plus?.length" class="reason-list plus">
          <div v-for="r in fund.reasons.plus" :key="r" class="reason-item">+ {{ r }}</div>
        </div>
        <div v-if="fund.reasons.minus?.length" class="reason-list minus">
          <div v-for="r in fund.reasons.minus" :key="r" class="reason-item">- {{ r }}</div>
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
        <h4>⚠️ 风险提示</h4>
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
  background: white;
  border: none;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 14px;
  color: #667eea;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  color: #999;
}
.error { color: #e74c3c; }

.detail-header {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.title-row h2 {
  font-size: 20px;
}

.title-row .name {
  color: #666;
  font-size: 14px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.big-score {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: white;
}

.signal {
  padding: 6px 14px;
  border-radius: 16px;
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
  background: white;
  border-radius: 12px;
  padding: 14px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 18px;
  font-weight: 600;
}

.metric-value.up { color: #e74c3c; }
.metric-value.down { color: #27ae60; }

.section {
  background: white;
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 12px;
}

.section h3 {
  font-size: 15px;
  margin-bottom: 10px;
  color: #333;
}

.info-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
}

.info-row:last-child {
  border-bottom: none;
}

.reason-list {
  font-size: 13px;
  line-height: 1.8;
}

.reason-list.plus { color: #27ae60; }
.reason-list.minus { color: #e74c3c; }

.reason-item {
  padding: 4px 0;
}

.risk-box {
  background: #fff3cd;
  border-radius: 12px;
  padding: 14px;
  color: #856404;
  font-size: 13px;
}

.risk-box h4 {
  margin-bottom: 6px;
}

.excellent { background: #8B0000; }
.good { background: #CD2626; }
.medium { background: #FF4500; }
.low { background: #A0522D; }
.poor { background: #4F4F4F; }
</style>
