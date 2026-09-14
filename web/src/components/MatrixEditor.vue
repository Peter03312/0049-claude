<script setup lang="ts">
import { computed } from 'vue'
import type {
  CellMap,
  LeafCardAttribute,
  LeafCardObject,
  Tribool,
} from '../types'
import { cellKey, nextId } from '../util'

const objects = defineModel<LeafCardObject[]>('objects', { required: true })
const attributes = defineModel<LeafCardAttribute[]>('attributes', {
  required: true,
})
const cells = defineModel<CellMap>('cells', { required: true })

const VALUE_CYCLE: Record<Tribool, Tribool> = {
  true: 'false',
  false: 'unknown',
  unknown: 'true',
}
const VALUE_TEXT: Record<Tribool, string> = {
  true: '真',
  false: '假',
  unknown: '？',
}

const cellValue = (o: number, a: number): Tribool =>
  cells.value[cellKey(o, a)] ?? 'unknown'

function cycleCell(o: number, a: number) {
  const key = cellKey(o, a)
  const next = VALUE_CYCLE[cellValue(o, a)]
  cells.value = { ...cells.value, [key]: next }
}

function addObject() {
  if (objects.value.length >= 20) return
  objects.value = [
    ...objects.value,
    { id: nextId(objects.value), label: `卡片 ${nextId(objects.value)}`, note: '' },
  ]
}

function removeObject(id: number) {
  if (objects.value.length <= 4) return
  objects.value = objects.value.filter((o) => o.id !== id)
  const kept: CellMap = {}
  for (const [key, v] of Object.entries(cells.value)) {
    const [oid] = key.split(':')
    if (Number(oid) !== id) kept[key] = v
  }
  cells.value = kept
}

function updateObject(id: number, patch: Partial<LeafCardObject>) {
  objects.value = objects.value.map((o) =>
    o.id === id ? { ...o, ...patch } : o,
  )
}

function addAttribute() {
  if (attributes.value.length >= 20) return
  const id = nextId(attributes.value)
  attributes.value = [...attributes.value, { id, label: `特征 ${id}` }]
}

function removeAttribute(id: number) {
  if (attributes.value.length <= 1) return
  attributes.value = attributes.value.filter((a) => a.id !== id)
  const kept: CellMap = {}
  for (const [key, v] of Object.entries(cells.value)) {
    const [, aid] = key.split(':')
    if (Number(aid) !== id) kept[key] = v
  }
  cells.value = kept
}

function updateAttribute(id: number, label: string) {
  attributes.value = attributes.value.map((a) =>
    a.id === id ? { ...a, label } : a,
  )
}

const canAddObject = computed(() => objects.value.length < 20)
const canAddAttr = computed(() => attributes.value.length < 20)
</script>

<template>
  <div class="editor">
    <div class="editor-cols">
      <section class="editor-block">
        <h3>🍂 对象卡（{{ objects.length }}/20）</h3>
        <p class="muted">每张卡片是一种树叶；编号自动分配，不能重复。</p>
        <div v-for="o in objects" :key="o.id" class="item-row">
          <span class="id-badge">{{ o.id }}</span>
          <input
            :value="o.label"
            placeholder="树叶名字"
            @input="updateObject(o.id, { label: ($event.target as HTMLInputElement).value })"
          />
          <input
            :value="o.note"
            class="note-input"
            placeholder="小备注（可不填）"
            @input="updateObject(o.id, { note: ($event.target as HTMLInputElement).value })"
          />
          <button
            class="btn-ghost icon-btn"
            :disabled="objects.length <= 4"
            title="至少要保留 4 张卡"
            @click="removeObject(o.id)"
          >
            删
          </button>
        </div>
        <button class="btn-light" :disabled="!canAddObject" @click="addObject">
          ＋ 加一张对象卡
        </button>
      </section>

      <section class="editor-block">
        <h3>🔍 观察特征（{{ attributes.length }}/20）</h3>
        <p class="muted">例如：有裂片、针形、边缘光滑。</p>
        <div v-for="a in attributes" :key="a.id" class="item-row">
          <span class="id-badge">{{ a.id }}</span>
          <input
            :value="a.label"
            placeholder="特征名字"
            @input="updateAttribute(a.id, ($event.target as HTMLInputElement).value)"
          />
          <button
            class="btn-ghost icon-btn"
            :disabled="attributes.length <= 1"
            title="至少保留 1 个特征"
            @click="removeAttribute(a.id)"
          >
            删
          </button>
        </div>
        <button class="btn-light" :disabled="!canAddAttr" @click="addAttribute">
          ＋ 加一个特征
        </button>
      </section>
    </div>

    <h3>🧮 三值观察矩阵</h3>
    <p class="muted">
      点格子切换：<span class="cell-demo cell-true">真</span> 确定有、
      <span class="cell-demo cell-false">假</span> 确定没有、
      <span class="cell-demo cell-unknown">？</span> 还没观察。
      <b>「？」不会被当成「假」</b>，因为那可能认错叶子。
    </p>
    <div class="matrix-scroll">
      <table class="matrix">
        <thead>
          <tr>
            <th class="corner">卡片 ＠ 特征</th>
            <th v-for="a in attributes" :key="a.id">
              <span class="id-badge">{{ a.id }}</span>
              <div class="attr-label">{{ a.label }}</div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in objects" :key="o.id">
            <th class="row-head">
              <span class="id-badge">{{ o.id }}</span> {{ o.label }}
            </th>
            <td v-for="a in attributes" :key="a.id">
              <button
                class="cell"
                :class="`cell-${cellValue(o.id, a.id)}`"
                :title="`卡片 ${o.id} · 特征 ${a.id}：${
                  { true: '真', false: '假', unknown: '未知' }[cellValue(o.id, a.id)]
                }`"
                @click="cycleCell(o.id, a.id)"
              >
                {{ VALUE_TEXT[cellValue(o.id, a.id)] }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.editor-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

@media (max-width: 820px) {
  .editor-cols {
    grid-template-columns: 1fr;
  }
}

.editor-block {
  background: var(--green-50);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
}

.item-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.item-row input {
  min-width: 0;
  flex: 1;
}

.note-input {
  flex: 1.2;
}

.icon-btn {
  padding: 6px 12px;
  font-size: 13px;
}

.matrix-scroll {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 12px;
}

.matrix {
  border-collapse: collapse;
  width: 100%;
  font-size: 14px;
}

.matrix th,
.matrix td {
  border: 1px solid var(--line);
  text-align: center;
  padding: 6px 8px;
  min-width: 86px;
}

.corner {
  background: var(--green-50);
  position: sticky;
  left: 0;
  z-index: 2;
  min-width: 150px !important;
  text-align: left !important;
  padding-left: 12px !important;
}

.row-head {
  background: var(--green-50);
  text-align: left !important;
  font-weight: 600;
  white-space: nowrap;
  position: sticky;
  left: 0;
}

.attr-label {
  margin-top: 4px;
  font-weight: 600;
}

.cell {
  width: 44px;
  height: 40px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 800;
  padding: 0;
}

.cell-true {
  background: var(--green-500);
  color: #fff;
}

.cell-false {
  background: var(--red);
  color: #fff;
}

.cell-unknown {
  background: #eceff1;
  color: #607068;
}

.cell-demo {
  display: inline-block;
  width: 22px;
  height: 22px;
  line-height: 22px;
  border-radius: 6px;
  text-align: center;
  font-size: 13px;
  font-weight: 800;
}
</style>
