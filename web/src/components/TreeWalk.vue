<script setup lang="ts">
import { computed, ref } from 'vue'
import type {
  LeafCardAttribute,
  LeafCardObject,
  LeafNode,
  TreeNode,
} from '../types'
import { attributeName, leafIds, objectName } from '../util'

const props = defineProps<{
  tree: TreeNode | LeafNode
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
}>()

interface WalkStep {
  attributeId: number
  answer: 'true' | 'false'
}

const steps = ref<WalkStep[]>([])

const currentNode = computed<TreeNode | LeafNode>(() => {
  let node: TreeNode | LeafNode = props.tree
  for (const s of steps.value) {
    if (node.type === 'leaf') break
    node = s.answer === 'true' ? node.true : node.false
  }
  return node
})

const candidates = computed(() => leafIds(currentNode.value))
const candidateNames = computed(() =>
  candidates.value.map((id) => objectName(props.objects, id)),
)

function answer(value: 'true' | 'false') {
  if (currentNode.value.type !== 'question') return
  steps.value = [
    ...steps.value,
    { attributeId: currentNode.value.attributeId, answer: value },
  ]
}

function back() {
  steps.value = steps.value.slice(0, -1)
}

function restart() {
  steps.value = []
}

const stepNumber = computed(() => steps.value.length + 1)
</script>

<template>
  <div class="walk">
    <div v-if="steps.length" class="history">
      <span class="muted">你已经回答：</span>
      <ol class="history-list">
        <li v-for="(s, i) in steps" :key="i">
          <span class="id-badge">{{ s.attributeId }}</span>
          {{ attributeName(attributes, s.attributeId) }} →
          <b :class="s.answer === 'true' ? 'ans-yes' : 'ans-no'">
            {{ s.answer === 'true' ? '是（真）' : '不是（假）' }}
          </b>
        </li>
      </ol>
    </div>

    <div v-if="currentNode.type === 'question'" class="ask">
      <p class="ask-count muted">
        第 {{ stepNumber }} 问 · 还剩 {{ candidates.length }} 张可能的卡片：
        {{ candidateNames.join('、') }}
      </p>
      <p class="ask-q">
        <span class="id-badge">{{ currentNode.attributeId }}</span>
        你手里的叶子，<strong>{{ attributeName(attributes, currentNode.attributeId) }}</strong
        >吗？
      </p>
      <div class="ask-btns">
        <button class="btn-yes" @click="answer('true')">✓ 是 · 真</button>
        <button class="btn-no" @click="answer('false')">✗ 不是 · 假</button>
      </div>
      <p class="muted small">
        观察不确定时先不要走这张卡——每一问都保证能把剩下的卡片分成非空的两边。
      </p>
    </div>

    <div v-else class="finish">
      <p class="finish-emoji">🎉</p>
      <p class="finish-text">
        答案是：<strong>{{ objectName(objects, currentNode.objectId) }}</strong>
        <span class="muted">（卡片 {{ currentNode.objectId }}）</span>
      </p>
    </div>

    <div class="walk-controls">
      <button class="btn-ghost" :disabled="!steps.length" @click="back">
        ↩ 回退一步
      </button>
      <button class="btn-ghost" :disabled="!steps.length" @click="restart">
        ⟲ 重新试走
      </button>
    </div>
  </div>
</template>

<style scoped>
.history {
  margin-bottom: 12px;
  font-size: 14px;
}

.history-list {
  margin: 6px 0 0;
  padding-left: 20px;
}

.history-list li {
  margin-bottom: 4px;
}

.ans-yes {
  color: var(--green-700);
}

.ans-no {
  color: var(--red);
}

.ask {
  background: var(--green-50);
  border: 1px solid var(--green-200);
  border-radius: 14px;
  padding: 14px 16px;
  text-align: center;
}

.ask-count {
  margin: 0 0 8px;
}

.ask-q {
  font-size: 19px;
  margin: 6px 0 14px;
}

.ask-btns {
  display: flex;
  gap: 14px;
  justify-content: center;
}

.small {
  font-size: 12px;
  margin-bottom: 0;
}

.finish {
  text-align: center;
  padding: 18px 0 8px;
}

.finish-emoji {
  font-size: 46px;
  margin: 0;
}

.finish-text {
  font-size: 22px;
  margin: 4px 0;
}

.walk-controls {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 12px;
}
</style>
