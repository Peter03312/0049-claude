<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from './api'
import type {
  CellMap,
  ComputeResult,
  LeafCardAttribute,
  LeafCardObject,
  Project,
  Snapshot,
} from './types'
import MatrixEditor from './components/MatrixEditor.vue'
import ResultPanel from './components/ResultPanel.vue'

/* ---------- 全局状态 ---------- */
const projects = ref<Project[]>([])
const current = ref<Project | null>(null)
const loading = ref(true)
const saving = ref(false)
const computing = ref(false)
const errorMsg = ref('')
const infoMsg = ref('')
const snapshots = ref<Snapshot[]>([])
const openSnapshot = ref<Snapshot | null>(null)

/* ---------- 编辑态（与已保存内容分离） ---------- */
const name = ref('')
const objects = ref<LeafCardObject[]>([])
const attributes = ref<LeafCardAttribute[]>([])
const cells = ref<CellMap>({})

const dirty = computed(() => {
  if (!current.value) return false
  return (
    name.value !== current.value.name ||
    JSON.stringify(objects.value) !== JSON.stringify(current.value.objects) ||
    JSON.stringify(attributes.value) !==
      JSON.stringify(current.value.attributes) ||
    JSON.stringify(cells.value) !== JSON.stringify(current.value.cells)
  )
})

const showResult = computed(
  () => current.value?.resultFresh && current.value.result,
)

/* ---------- 示例数据（4–20 张卡，便于上手，不含任何预置树） ---------- */
function buildSample() {
  name.value = '秋天的四种树叶'
  objects.value = [
    { id: 1, label: '枫叶', note: '掌状裂片' },
    { id: 2, label: '橡树叶', note: '边缘圆裂' },
    { id: 3, label: '松针', note: '成束细针' },
    { id: 4, label: '银杏叶', note: '扇形' },
  ]
  attributes.value = [
    { id: 1, label: '有裂片' },
    { id: 2, label: '扁平宽大' },
    { id: 3, label: '针形' },
    { id: 4, label: '边缘光滑' },
  ]
  cells.value = {
    '1:1': 'true', '1:2': 'true', '1:3': 'false', '1:4': 'false',
    '2:1': 'true', '2:2': 'true', '2:3': 'false', '2:4': 'true',
    '3:1': 'false', '3:2': 'false', '3:3': 'true', '3:4': 'false',
    '4:1': 'false', '4:2': 'true', '4:3': 'false', '4:4': 'true',
  }
}

function buildBlank() {
  name.value = '我的辨认卡'
  objects.value = [
    { id: 1, label: '卡片 1', note: '' },
    { id: 2, label: '卡片 2', note: '' },
    { id: 3, label: '卡片 3', note: '' },
    { id: 4, label: '卡片 4', note: '' },
  ]
  attributes.value = [{ id: 1, label: '特征 1' }]
  cells.value = {}
}

/* ---------- 载入与保存 ---------- */
async function loadProjects() {
  loading.value = true
  try {
    projects.value = await api.listProjects()
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

function editFrom(p: Project) {
  current.value = p
  name.value = p.name
  objects.value = structuredClone(p.objects)
  attributes.value = structuredClone(p.attributes)
  cells.value = structuredClone(p.cells)
  errorMsg.value = ''
  infoMsg.value = ''
  loadSnapshots()
}

function newProject(useSample: boolean) {
  current.value = null
  snapshots.value = []
  if (useSample) buildSample()
  else buildBlank()
}

async function save(andCompute = false) {
  errorMsg.value = ''
  infoMsg.value = ''
  if (!name.value.trim()) {
    errorMsg.value = '请先给辨认卡起个名字。'
    return
  }
  if (objects.value.some((o) => !o.label.trim())) {
    errorMsg.value = '每张对象卡都要有名字。'
    return
  }
  if (attributes.value.some((a) => !a.label.trim())) {
    errorMsg.value = '每个特征都要有名字。'
    return
  }
  const input = {
    name: name.value.trim(),
    objects: objects.value.map((o) => ({
      ...o,
      label: o.label.trim(),
      note: o.note.trim(),
    })),
    attributes: attributes.value.map((a) => ({
      ...a,
      label: a.label.trim(),
    })),
    cells: cells.value,
  }
  saving.value = true
  try {
    let changed = true
    if (current.value) {
      changed =
        name.value.trim() !== current.value.name ||
        JSON.stringify(objects.value) !== JSON.stringify(current.value.objects) ||
        JSON.stringify(attributes.value) !==
          JSON.stringify(current.value.attributes) ||
        JSON.stringify(cells.value) !== JSON.stringify(current.value.cells)
      if (changed) {
        current.value = await api.updateProject(current.value.id, input)
        infoMsg.value = '已保存。输入有改动，旧的辨认树已标记过期。'
      } else {
        infoMsg.value = '没有需要保存的改动。'
      }
    } else {
      current.value = await api.createProject(input)
      infoMsg.value = '已保存辨认卡。'
    }
    await loadProjects()
    if (andCompute && changed) {
      await runCompute()
    }
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    saving.value = false
  }
}

async function runCompute() {
  if (!current.value) return
  errorMsg.value = ''
  computing.value = true
  try {
    const { result } = await api.compute(current.value.id)
    current.value = await api.getProject(current.value.id)
    projects.value = projects.value.map((p) =>
      p.id === current.value!.id ? current.value! : p,
    )
    infoMsg.value =
      result.status === 'ok'
        ? '辨认树算好啦，来逐问试走吧！'
        : '这组观察暂时分不开，看看下面的说明。'
    await loadSnapshots()
  } catch (e) {
    errorMsg.value = (e as Error).message
  } finally {
    computing.value = false
  }
}

async function loadSnapshots() {
  if (!current.value) {
    snapshots.value = []
    return
  }
  snapshots.value = await api.listSnapshots(current.value.id)
}

async function viewSnapshot(s: Snapshot) {
  openSnapshot.value = await api.getSnapshot(s.id)
}

async function removeProject() {
  if (!current.value) return
  if (!window.confirm(`确定删除「${current.value.name}」吗？快照也会一起删除。`)) {
    return
  }
  try {
    await api.deleteProject(current.value.id)
    current.value = null
    snapshots.value = []
    buildBlank()
    await loadProjects()
  } catch (e) {
    errorMsg.value = (e as Error).message
  }
}

const resultForPanel = computed<ComputeResult | null>(() =>
  current.value?.result ?? null,
)

onMounted(loadProjects)
</script>

<template>
  <header>
    <h1>🍃 树叶辨认卡</h1>
    <p class="muted">
      录入 4–20 张树叶卡和你观察到的特征，算出一棵「每一步都能把叶子分开」的辨认树。
    </p>
  </header>

  <div v-if="errorMsg" class="banner banner-error">❌ {{ errorMsg }}</div>

  <!-- 已保存的辨认卡 -->
  <section class="card" v-if="projects.length">
    <h2>📚 已保存的辨认卡</h2>
    <div class="project-list">
      <button
        v-for="p in projects"
        :key="p.id"
        class="project-chip"
        :class="{ active: current?.id === p.id }"
        @click="editFrom(p)"
      >
        {{ p.name }}
        <span class="chip-state" :class="p.resultFresh ? 'fresh' : 'stale'">
          {{ p.resultFresh ? '有树' : '待计算' }}
        </span>
      </button>
    </div>
  </section>

  <div v-if="loading" class="muted">正在打开观察本…</div>

  <!-- 编辑区 -->
  <section v-if="objects.length" class="card">
    <div class="editor-head">
      <input v-model="name" class="name-input" placeholder="辨认卡名字" />
      <span v-if="dirty" class="dirty-tag">有未保存的修改</span>
    </div>

    <MatrixEditor
      v-model:objects="objects"
      v-model:attributes="attributes"
      v-model:cells="cells"
    />

    <div v-if="infoMsg" class="banner banner-info">{{ infoMsg }}</div>

    <div class="action-row">
      <button class="btn-primary" :disabled="saving" @click="save(false)">
        <span v-if="saving" class="spinner"></span>💾 保存
      </button>
      <button
        class="btn-light"
        :disabled="saving || computing"
        @click="save(true)"
      >
        <span v-if="computing" class="spinner"></span>🌳 保存并算出辨认树
      </button>
      <button
        v-if="current"
        class="btn-ghost"
        :disabled="computing || dirty"
        :title="dirty ? '先保存修改' : '按当前已保存的输入重算'"
        @click="runCompute"
      >
        🔄 重新算出辨认树
      </button>
      <button v-if="current" class="btn-danger" @click="removeProject">
        🗑 删除
      </button>
      <button class="btn-ghost" @click="newProject(false)">＋ 空白新卡</button>
      <button
        v-if="!current"
        class="btn-ghost"
        @click="newProject(true)"
      >
        🍂 用示例开始
      </button>
    </div>
    <p v-if="current && dirty" class="muted small">
      修改卡片或特征后，旧辨认树会过期；保存后请重新计算。
    </p>
  </section>

  <section v-else-if="!loading" class="card empty-actions">
    <p>这是一本空观察本，先建一张辨认卡吧。</p>
    <div class="stack-row">
      <button class="btn-primary" @click="newProject(true)">🍂 用示例开始</button>
      <button class="btn-light" @click="newProject(false)">＋ 空白新卡</button>
    </div>
  </section>

  <!-- 结果区 -->
  <section v-if="current && showResult && resultForPanel" class="card">
    <h2>🌳 {{ current.name }} · 辨认树</h2>
    <ResultPanel
      :result="resultForPanel"
      :objects="current.objects"
      :attributes="current.attributes"
      :fresh="current.resultFresh"
    />
  </section>

  <section
    v-else-if="current && !current.resultFresh"
    class="card"
  >
    <h2>🌳 辨认树</h2>
    <p class="banner banner-info">
      还没有和当前输入一致的辨认树。点上面的「保存并算出辨认树」，就能看到每一步怎么分开叶子。
    </p>
  </section>

  <!-- 快照 -->
  <section v-if="snapshots.length" class="card">
    <h2>📸 保存过的计算快照（{{ snapshots.length }}）</h2>
    <p class="muted">
      每次「算出辨认树」都会同时保存当时的矩阵和结果，方便回看。编辑不会删掉旧快照。
    </p>
    <ul class="snap-list">
      <li v-for="s in snapshots" :key="s.id">
        <button class="btn-ghost snap-btn" @click="viewSnapshot(s)">
          #{{ s.id }} · 第 {{ s.inputVersion }} 版输入 ·
          {{ new Date(s.createdAt).toLocaleString('zh-CN') }} ·
          <b :class="s.result.status === 'ok' ? 'ans-yes' : 'ans-no'">
            {{ s.result.status === 'ok' ? '完整树' : '无解说明' }}
          </b>
        </button>
      </li>
    </ul>
  </section>

  <!-- 快照查看弹层 -->
  <div v-if="openSnapshot" class="modal-mask" @click.self="openSnapshot = null">
    <div class="modal card">
      <div class="modal-head">
        <h2 style="margin: 0">📸 快照 #{{ openSnapshot.id }}</h2>
        <button class="btn-ghost" @click="openSnapshot = null">关闭</button>
      </div>
      <p class="muted">
        第 {{ openSnapshot.inputVersion }} 版输入 ·
        {{ new Date(openSnapshot.createdAt).toLocaleString('zh-CN') }}
      </p>
      <ResultPanel
        :result="openSnapshot.result"
        :objects="openSnapshot.objects"
        :attributes="openSnapshot.attributes"
        :fresh="true"
      />
    </div>
  </div>
</template>

<style scoped>
.project-list {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.project-chip {
  border-radius: 12px;
  background: #eef4f0;
  color: var(--ink);
  padding: 8px 14px;
  font-weight: 600;
}

.project-chip.active {
  background: var(--green-700);
  color: #fff;
}

.chip-state {
  font-size: 11px;
  border-radius: 999px;
  padding: 1px 8px;
  margin-left: 6px;
}

.chip-state.fresh {
  background: var(--green-200);
  color: var(--green-900);
}

.chip-state.stale {
  background: #fde8e2;
  color: var(--red);
}

.project-chip.active .chip-state.fresh {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
}

.editor-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.name-input {
  max-width: 340px;
  font-size: 18px;
  font-weight: 700;
}

.dirty-tag {
  font-size: 12px;
  color: #7a4e12;
  background: #fff7e8;
  border: 1px solid #f3ddb0;
  border-radius: 999px;
  padding: 2px 10px;
}

.action-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
  align-items: center;
}

.small {
  font-size: 12px;
}

.empty-actions {
  text-align: center;
}

.snap-list {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}

.snap-btn {
  width: 100%;
  text-align: left;
  border-radius: 10px;
  margin-bottom: 6px;
  font-size: 14px;
}

.ans-yes {
  color: var(--green-700);
}

.ans-no {
  color: var(--red);
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(20, 40, 28, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 16px;
}

.modal {
  max-width: 820px;
  width: 100%;
  max-height: 88vh;
  overflow-y: auto;
  margin: 0;
}

.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
</style>
