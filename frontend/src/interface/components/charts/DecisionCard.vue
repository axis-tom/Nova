<template>
  <div class="decision-card-wrapper">
    <div class="decision-card" :class="verdictClass">
      <!-- 顶部：结论 + 置信度 -->
      <div class="card-header">
        <div class="verdict-badge" :class="verdictClass">
          <span class="verdict-icon">{{ verdictIcon }}</span>
          <span class="verdict-text">{{ displayVerdict }}</span>
        </div>
        <div class="confidence-badge" :class="confidenceClass">
          <span class="confidence-dot"></span>
          {{ displayConfidence }}
        </div>
      </div>

      <!-- 决策依据 -->
      <div v-if="reasons.length" class="card-section">
        <div class="section-title">📊 决策依据</div>
        <div class="reason-list">
          <div v-for="(r, i) in reasons" :key="i" class="reason-item">
            <span class="reason-num">{{ i + 1 }}</span>
            <span class="reason-text">{{ r }}</span>
          </div>
        </div>
      </div>

      <!-- 风险清单 -->
      <div v-if="risks.length" class="card-section">
        <div class="section-title">⚠️ 风险清单</div>
        <div class="risk-list">
          <div v-for="(risk, i) in risks" :key="i" class="risk-item">
            <span class="risk-category">{{ risk.category }}</span>
            <span class="risk-detail">{{ risk.detail }}</span>
          </div>
        </div>
      </div>

      <!-- 关键证据（可折叠） -->
      <div v-if="evidenceKeys.length" class="card-section">
        <div class="section-title collapsible" @click="showEvidence = !showEvidence">
          🧪 关键证据
          <span class="collapse-icon">{{ showEvidence ? '▲' : '▼' }}</span>
        </div>
        <div v-show="showEvidence" class="evidence-grid">
          <div v-for="ev in evidenceKeys" :key="ev.label" class="evidence-item">
            <span class="ev-label">{{ ev.label }}</span>
            <span class="ev-value">{{ ev.value }}</span>
          </div>
        </div>
      </div>

      <!-- 建议行动路径 -->
      <div v-if="actions.length" class="card-section">
        <div class="section-title">🧭 建议行动路径</div>
        <div v-for="(a, i) in actions" :key="i" class="action-row">
          <span class="action-bullet">{{ a.icon }}</span>
          <span class="action-text" v-html="a.text"></span>
        </div>
      </div>

      <!-- 一句话判断 -->
      <div v-if="summary" class="card-footer">
        <div class="summary-icon">🧷</div>
        <div class="summary-text">{{ summary }}</div>
      </div>

      <!-- 折叠/展开按钮 -->
      <div class="card-toggle" @click="expanded = !expanded">
        {{ expanded ? '收起详细数据' : '展开详细数据' }}
        <span>{{ expanded ? '▲' : '▼' }}</span>
      </div>
    </div>

    <!-- 详细数据面板（折叠时收起） -->
    <div v-show="expanded" class="detail-panel">
      <div class="detail-title">📋 原始分析数据</div>
      <div class="detail-grid">
        <div v-for="(val, key) in flatDetails" :key="key" class="detail-row">
          <span class="detail-label">{{ key }}</span>
          <span class="detail-value">{{ val }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  data: Record<string, any>
}>()

const expanded = ref(false)
const showEvidence = ref(true)

// ── 结论解析 ──

const verdictClass = computed(() => {
  const rec = props.data?.recommendation || ''
  if (rec === 'strong_buy' || rec === 'buy') return 'verdict-do'
  if (rec === 'hold') return 'verdict-wait'
  if (rec === 'avoid') return 'verdict-dont'
  return 'verdict-wait'
})

const verdictIcon = computed(() => {
  if (verdictClass.value === 'verdict-do') return '✅'
  if (verdictClass.value === 'verdict-dont') return '❌'
  return '⏳'
})

const displayVerdict = computed(() => {
  return props.data?.label || '观望'
})

// ── 置信度 ──

const confidenceClass = computed(() => {
  const c = displayConfidence.value
  if (c === '高') return 'conf-high'
  if (c === '中') return 'conf-mid'
  return 'conf-low'
})

const displayConfidence = computed(() => {
  const score = props.data?.market_entry_score
  if (score == null) return '中'
  if (score >= 70) return '高'
  if (score >= 40) return '中'
  return '低'
})

// ── 理由 ──

const reasons = computed(() => {
  const positives: string[] = props.data?.positives || []
  const negatives: string[] = props.data?.negatives || []
  const combined: string[] = []
  if (positives.length) combined.push('✅ ' + positives.slice(0, 2).join('；'))
  if (negatives.length) combined.push('⚠️ ' + negatives.slice(0, 2).join('；'))
  return combined
})

// ── 风险 ──

const risks = computed(() => {
  const negs: string[] = props.data?.negatives || []
  if (negs.length === 0) return []
  return negs.slice(0, 3).map((n: string) => {
    // 分类：按内容匹配
    let category = '商业风险'
    if (n.includes('评论') || n.includes('壁垒') || n.includes('竞争')) category = '竞争风险'
    else if (n.includes('价格') || n.includes('利润') || n.includes('成本')) category = '价格风险'
    else if (n.includes('钱') || n.includes('资金') || n.includes('回款')) category = '资金风险'
    else if (n.includes('萎缩') || n.includes('下降') || n.includes('趋势')) category = '市场风险'
    return { category, detail: n }
  })
})

// ── 关键证据 ──

const evidenceKeys = computed(() => {
  const det = props.data?._deterministic_summary || {}
  const items: { label: string; value: string }[] = []
  if (det.total_monthly_units != null) items.push({ label: '月销量', value: `${Number(det.total_monthly_units).toLocaleString()} 件` })
  if (det.estimated_monthly_revenue != null) items.push({ label: '月营收', value: `$${Number(det.estimated_monthly_revenue).toLocaleString()}` })
  if (det.market_direction) items.push({ label: '趋势方向', value: det.market_direction })
  if (det.top3_share != null) items.push({ label: 'Top3 份额', value: `${det.top3_share}%` })
  if (det.review_barrier) items.push({ label: '评论壁垒', value: det.review_barrier })
  if (det.avg_review_count != null) items.push({ label: '平均评论', value: `${Number(det.avg_review_count).toLocaleString()} 条` })
  if (det.avg_rating != null) items.push({ label: '平均评分', value: `${det.avg_rating}` })
  if (det.rating_health_score != null) items.push({ label: '健康分', value: `${det.rating_health_score}/100` })
  if (det.avg_price != null) items.push({ label: '均价', value: `$${det.avg_price}` })
  if (det.fba_pct != null) items.push({ label: 'FBA 占比', value: `${det.fba_pct}%` })
  if (det.product_count != null) items.push({ label: '分析商品数', value: `${det.product_count}` })
  return items
})

// ── 建议路径 ──

const actions = computed(() => {
  const entryRoutes: any[] = props.data?.entry_routes || []
  if (entryRoutes.length === 0) return []
  const items: { icon: string; text: string }[] = []
  entryRoutes.slice(0, 2).forEach((r: any) => {
    items.push({ icon: '📌', text: `<strong>${r.route || ''}</strong> — ${r.rationale || ''}` })
  })
  return items
})

// ── 一句话总结 ──

const summary = computed(() => {
  return props.data?.summary || ''
})

// ── 详细数据（折叠面板） ──

const flatDetails = computed(() => {
  const det = props.data?._deterministic_summary || {}
  const result: Record<string, string> = {}
  for (const [k, v] of Object.entries(det)) {
    if (k === 'price_bands') continue
    result[k] = String(v ?? '-')
  }
  return result
})
</script>

<style scoped>
.decision-card-wrapper {
  margin: 16px 0;
}

.decision-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  transition: box-shadow 0.2s;
}
.decision-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

/* ── 顶部 ── */

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.verdict-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 24px;
  font-size: 16px;
  font-weight: 700;
}
.verdict-do { background: #ecfdf5; color: #059669; }
.verdict-wait { background: #fffbeb; color: #d97706; }
.verdict-dont { background: #fef2f2; color: #dc2626; }

.verdict-icon { font-size: 20px; }
.verdict-text { letter-spacing: 0.5px; }

.confidence-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 500;
}
.confidence-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.conf-high { background: #ecfdf5; color: #059669; }
.conf-high .confidence-dot { background: #059669; }
.conf-mid { background: #fffbeb; color: #d97706; }
.conf-mid .confidence-dot { background: #d97706; }
.conf-low { background: #fef2f2; color: #dc2626; }
.conf-low .confidence-dot { background: #dc2626; }

/* ── 章节 ── */

.card-section {
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #f1f5f9;
}
.card-section:last-of-type {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 8px;
}
.section-title.collapsible {
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  user-select: none;
}
.collapse-icon {
  font-size: 11px;
  color: #64748b;
}

/* ── 依据列表 ── */

.reason-list { display: flex; flex-direction: column; gap: 8px; }
.reason-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
}
.reason-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}
.reason-text { flex: 1; }

/* ── 风险 ── */

.risk-list { display: flex; flex-direction: column; gap: 6px; }
.risk-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.4;
}
.risk-category {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 8px;
  background: #fef3c7;
  color: #92400e;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}
.risk-detail { color: #475569; }

/* ── 证据 ── */

.evidence-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 16px;
}
.evidence-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
  font-size: 13px;
  border-bottom: 1px solid #f8fafc;
}
.ev-label { color: #64748b; }
.ev-value { font-weight: 600; color: #1e293b; }

/* ── 行动路径 ── */

.action-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
}
.action-bullet { flex-shrink: 0; font-size: 14px; }
.action-text { flex: 1; }

/* ── 底部 ── */

.card-footer {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 14px;
  margin-top: 12px;
  background: #f8fafc;
  border-radius: 8px;
}
.summary-icon { flex-shrink: 0; font-size: 16px; }
.summary-text {
  font-size: 14px;
  font-weight: 500;
  color: #1e293b;
  line-height: 1.5;
}

/* ── 折叠按钮 ── */

.card-toggle {
  margin-top: 14px;
  text-align: center;
  font-size: 12px;
  color: #3b82f6;
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: background 0.15s;
  user-select: none;
}
.card-toggle:hover {
  background: #eff6ff;
}

/* ── 详细数据面板 ── */

.detail-panel {
  margin-top: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
}
.detail-title {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 10px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px 12px;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 3px 0;
  border-bottom: 1px solid #f1f5f9;
}
.detail-label { color: #94a3b8; }
.detail-value { font-weight: 500; color: #334155; }
</style>