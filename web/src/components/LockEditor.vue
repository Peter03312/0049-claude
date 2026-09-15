<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LeafCardAttribute, PathLock } from '../types'

const props = defineProps<{
  attributes: LeafCardAttribute[]
}>()

const locks = defineModel<PathLock[]>('locks', { required: true })

const localError = ref('')

const pathText = (path: ('true' | 'false')[]) =>
  path.length
    ? path.map((b, i) => `${i + 1}.${b === 'true' ? '是' : '不是'}`).join(' → ')
    : '一开始（根问题）'

function addLock() {
  if (locks.value.length >= 40) return
  locks.value = [
    ...locks.value,
    { path: [], attributeId: props.attributes[0]?.id ?? 0 },
  ]
}

function removeLock(index: number) {
  locks.value = locks.value.filter((_, i) => i !== index)
}

function update(index: number, patch: Partial<PathLock>) {
  locks.value = locks.value.map((l, i) =>
    i === index ? { ...l, ...patch } : l,
  )
}

function setAttr(index: number, value: string) {
  update(index, { attributeId: Number(value) })
}

function addStep(index: number, branch: 'true' | 'false') {
  const lk = locks.value[index]
  if (lk.path.length >= 19) return
  update(index, { path: [...lk.path, branch] })
}

function popStep(index: number) {
  const lk = locks.value[index]
  update(index, { path: lk.path.slice(0, -1) })
}

const validationError = computed<string>(() => {
  const byPath = new Map<string, number>()
  for (const lk of locks.value) {
    if (!lk.attributeId) return '每条预定步骤都要选一个「必须询问」的特征。'
    const key = JSON.stringify(lk.path)
    const prev = byPath.get(key)
    if (prev !== undefined && prev !== lk.attributeId) {
      return '同一条回答路线被锁到了两个不同特征，请删掉其中一条。'
    }
    byPath.set(key, lk.attributeId)
  }
  return ''
})

/** 保存/计算前由父组件调用；返回 false 时已把提示显示在本组件内。 */
function validateOrWarn(): boolean {
  localError.value = validationError.value
  return !localError.value
}

defineExpose({ validateOrWarn })
</script>

<template>
  <details class="locks">
    <summary>
      🔒 预定步骤：指定某条回答路线上「必须先问哪个特征」
      <span v-if="locks.length" class="lock-count">（{{ locks.length }} 条）</span>
    </summary>

    <p class="muted">
      按计划的制作步骤，从第一个问题起用「是 / 不是」走出一条回答路线，
      再选走到那一步时<b>必须询问</b>的特征。没指定的步骤仍由系统自动挑最优问法。
      小技巧：可以先自由算一次，照着树来加预定步骤。
    </p>

    <div v-for="(lk, i) in locks" :key="i" class="lock-row">
      <div class="lock-path">
        <span class="lock-path-text">路线：{{ pathText(lk.path) }}</span>
        <div class="path-btns">
          <button class="mini btn-yes" :disabled="lk.path.length >= 19" @click="addStep(i, 'true')">
            ＋回答「是」
          </button>
          <button class="mini btn-no" :disabled="lk.path.length >= 19" @click="addStep(i, 'false')">
            ＋回答「不是」
          </button>
          <button class="mini btn-ghost" :disabled="!lk.path.length" @click="popStep(i)">
            退一步
          </button>
        </div>
      </div>

      <div class="lock-attr">
        <span>必须问：</span>
        <select
          :value="lk.attributeId"
          @change="setAttr(i, ($event.target as HTMLSelectElement).value)"
        >
          <option v-for="a in attributes" :key="a.id" :value="a.id">
            {{ a.id }}. {{ a.label }}
          </option>
        </select>
      </div>

      <button class="btn-danger mini" @click="removeLock(i)">删</button>
    </div>

    <div v-if="localError" class="banner banner-error">{{ localError }}</div>

    <button class="btn-light" :disabled="locks.length >= 40" @click="addLock">
      ＋ 加一条预定步骤
    </button>
  </details>
</template>

<style scoped>
summary {
  cursor: pointer;
  font-weight: 700;
  color: var(--green-900);
  padding: 6px 0;
}

.lock-count {
  font-weight: 400;
  color: var(--grey);
}

.lock-row {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  flex-wrap: wrap;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px 12px;
  margin: 10px 0;
}

.lock-path {
  flex: 2 1 260px;
}

.lock-path-text {
  font-size: 14px;
  font-weight: 600;
  display: block;
  margin-bottom: 6px;
}

.path-btns {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.lock-attr {
  flex: 1 1 200px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.lock-attr select {
  flex: 1;
  min-width: 0;
  padding: 7px 10px;
  border-radius: 10px;
  border: 1.5px solid var(--line);
  font-family: inherit;
  font-size: 14px;
}

.mini {
  font-size: 13px;
  padding: 5px 12px;
}
</style>
