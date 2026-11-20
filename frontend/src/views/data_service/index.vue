<template>
  <section class="page" data-module="data_service">
    <header class="page-head">
      <div>
        <h2>数据API发布管理</h2>
        <p class="page-desc">维护数据服务，围绕服务编号、服务名称、输出数据集、查询参数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记数据服务</button>
        <button class="btn" type="button" @click="exportRows">导出数据API发布清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="assessCache(row)">缓存评估</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无数据API发布数据，可先登记数据服务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条数据API发布记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <Teleport to="body">
      <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
        <div class="modal-card">
          <header class="modal-head">
            <h3>登记数据服务</h3>
            <button class="btn ghost" type="button" @click="showCreateModal = false">&times;</button>
          </header>
          <form class="modal-body" @submit.prevent="submitCreate">
            <label v-for="field in columns.slice(0, 3)" :key="field" class="modal-field">
              <span>{{ field }}</span>
              <input v-model="createFields[field]" :placeholder="`请输入${field}`" required />
            </label>
            <footer class="modal-foot">
              <button class="btn" type="button" @click="showCreateModal = false">取消</button>
              <button class="btn primary" type="submit">提交登记</button>
            </footer>
          </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="assessment" class="modal-overlay" @click.self="assessment = null">
        <div class="modal-card">
          <header class="modal-head">
            <h3>缓存来源评估 · {{ assessment['服务编号'] }}</h3>
            <button class="btn ghost" type="button" @click="assessment = null">&times;</button>
          </header>
          <div class="modal-body">
            <p>交付策略：{{ assessment['交付策略'] }}</p>
            <p>当前截面：{{ assessment['当前截面'] ?? '—' }}　上一截面：{{ assessment['上一截面'] ?? '—' }}</p>
            <p>可服务截面：{{ (assessment['可服务截面'] || []).join('、') || '—' }}</p>
            <p>有效切片 {{ assessment['有效切片数'] }} 片 · 命中 {{ assessment['命中数'] }} · 缺批 {{ assessment['缺批数'] }}</p>
            <div v-if="assessment['缺批明细'] && assessment['缺批明细'].length">
              <h4>缺批明细</h4>
              <ul>
                <li v-for="item in assessment['缺批明细']" :key="item['切片编号']">
                  {{ item['切片编号'] }}：{{ item['原因'] }}（最近来源批次 {{ item['最近来源批次'] ?? '—' }}）
                </li>
              </ul>
            </div>
            <div v-if="assessment['上一页末行来源']">
              <h4>上一页末行来源</h4>
              <p>
                取数编号 {{ assessment['上一页末行来源']['取数编号'] }} · 批次 {{ assessment['上一页末行来源']['来源批次'] }}
                · 截面 {{ assessment['上一页末行来源']['取数截面'] }} · 切片 {{ assessment['上一页末行来源']['切片编号'] }}
              </p>
              <p>当时结果：读数 {{ assessment['上一页末行来源']['当时结果']['读数'] }}（{{ assessment['上一页末行来源']['当时结果']['登记时间'] }}）</p>
            </div>
            <p v-else>{{ assessment['定位说明'] }}</p>
          </div>
          <footer class="modal-foot">
            <button class="btn primary" type="button" @click="assessment = null">关闭</button>
          </footer>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/data_service'
const columns = ["服务编号", "服务名称", "输出数据集", "查询参数", "响应字段", "缓存秒数", "分页上限", "服务状态"]
const actions = ["保存配置", "发布服务", "停用服务"]
const statuses = ["草稿", "已配置", "已发布", "已停用"]
const stats = [{"label": "已发布服务", "value": 0}, {"label": "草稿服务", "value": 0}, {"label": "停用服务", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const showCreateModal = ref(false)
const createFields = ref<Record<string, string>>({})
const assessment = ref<Record<string, any> | null>(null)

async function assessCache(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/cache_sections`)
    const data = await response.json()
    if (!response.ok) {
      throw new Error(data.detail || '缓存来源评估读取失败')
    }
    assessment.value = data
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缓存来源评估读取失败'
  }
}

function updateStats() {
  const data = rows.value
  stats.length > 0 && (stats[0].value = data.filter((r: Row) => r.status === statuses[1] || r.pending).length)
  stats.length > 1 && (stats[1].value = data.filter((r: Row) => r.status && !r.pending && !r.abnormal).length)
  stats.length > 2 && (stats[2].value = data.filter((r: Row) => r.abnormal).length)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = ''
  createFields.value = {}
  showCreateModal.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createFields.value }),
    })
    if (!response.ok) {
      const data = await response.json()
      throw new Error(data.message || '登记失败')
    }
    showCreateModal.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('数据API发布动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '数据API发布操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('数据服务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    updateStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '数据API发布列表读取失败'
  }
}

onMounted(reload)
</script>
