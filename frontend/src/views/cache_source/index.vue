<template>
  <section class="page" data-module="cache_source">
    <header class="page-head">
      <div>
        <h2>缓存来源索引</h2>
        <p class="page-desc">
          接收数据服务登记的交付缓存内容（读数、来源批次、取数截面、数据内容、到期时间），按源编号、截面及有效期查询。
          默认只展示当前取数截面未过期的行；过期行按取数截面查询仍可定位。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记来源索引</button>
        <button class="btn" type="button" @click="exportRows">导出缓存来源索引清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>索引/取数编号</span>
        <input v-model="filters.keyword" placeholder="按索引编号或取数编号检索" />
      </label>
      <label class="filter-item">
        <span>源编号</span>
        <input v-model="filters.source" placeholder="按源编号检索" />
      </label>
      <label class="filter-item">
        <span>取数截面</span>
        <input v-model="filters.section" placeholder="定位历史截面（含已过期）" />
      </label>
      <label class="filter-item">
        <span>有效期</span>
        <select v-model="filters.validity">
          <option value="">全部</option>
          <option value="有效中">有效中</option>
          <option value="已过期">已过期</option>
        </select>
      </label>
      <label class="filter-item">
        <span>视图</span>
        <select v-model="filters.view">
          <option value="">当前取数截面</option>
          <option value="all">全部索引行</option>
        </select>
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
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">当前取数截面暂无有效缓存内容，可按取数截面定位历史交付</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条缓存来源索引记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <Teleport to="body">
      <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
        <div class="modal-card">
          <header class="modal-head">
            <h3>登记来源索引</h3>
            <button class="btn ghost" type="button" @click="showCreateModal = false">&times;</button>
          </header>
          <form class="modal-body" @submit.prevent="submitCreate">
            <label v-for="field in createFieldNames" :key="field" class="modal-field">
              <span>{{ field }}</span>
              <input
                v-if="field === '到期时间'"
                v-model="createFields[field]"
                type="datetime-local"
                required
              />
              <input v-else v-model="createFields[field]" :placeholder="`请输入${field}`" required />
            </label>
            <footer class="modal-foot">
              <button class="btn" type="button" @click="showCreateModal = false">取消</button>
              <button class="btn primary" type="submit">提交登记</button>
            </footer>
          </form>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/cache_source'
const columns = ["索引编号", "源编号", "取数编号", "来源批次", "取数截面", "切片编号", "读数", "到期时间", "有效期状态"]
const actions = ["立即到期"]
const createFieldNames = ["源编号", "取数编号", "来源批次", "取数截面", "切片编号", "读数", "数据内容", "到期时间"]
const stats = [
  { label: '有效中索引', value: 0 },
  { label: '已过期索引', value: 0 },
  { label: '补报次数合计', value: 0 },
]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const showCreateModal = ref(false)
const createFields = ref<Record<string, string>>({})

function updateStats() {
  const data = rows.value
  stats[0].value = data.filter((r: Row) => r['有效期状态'] === '有效中').length
  stats[1].value = data.filter((r: Row) => r['有效期状态'] === '已过期').length
  stats[2].value = data.reduce((sum: number, r: Row) => sum + Number(r['补报次数'] ?? 0), 0)
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
  noticeMessage.value = ''
  createFields.value = {}
  showCreateModal.value = true
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const values: Record<string, string> = { ...createFields.value }
    if (values['到期时间']) {
      values['到期时间'] = new Date(values['到期时间']).toISOString()
    }
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const data = await response.json()
    if (!response.ok || !data.ok) {
      throw new Error(data.message || data.detail || '登记失败')
    }
    noticeMessage.value = data.message || '缓存来源索引已登记'
    showCreateModal.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const data = await response.json()
    if (!response.ok || !data.ok) {
      throw new Error(data.message || '缓存来源索引动作未生效，请稍后重试')
    }
    noticeMessage.value = data.message || ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缓存来源索引操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) {
      params.set(key, value)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('缓存来源索引列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    updateStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '缓存来源索引列表读取失败'
  }
}

onMounted(reload)
</script>
