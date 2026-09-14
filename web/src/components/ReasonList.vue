<script setup lang="ts">
import type { BlockReason } from '../types'

defineProps<{
  reasons: BlockReason[]
  reasonText: (r: BlockReason) => string
}>()
</script>

<template>
  <div class="reasons">
    <h4 class="reasons-title">为什么每个特征都用不了？</h4>
    <ul class="reason-list">
      <li
        v-for="r in reasons"
        :key="r.attributeId"
        class="reason"
        :class="`reason-${r.reason}`"
      >
        <span class="id-badge">{{ r.attributeId }}</span>
        <span class="reason-text">{{ reasonText(r) }}</span>
      </li>
    </ul>
    <p class="hint">
      💡 可以再去观察这些叶子，把「？」补成真或假；或者加一个新特征，让它们在某个特征上不一样。
    </p>
  </div>
</template>

<style scoped>
.reasons-title {
  margin: 14px 0 8px;
}

.reason-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
}

.reason {
  background: var(--green-50);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 6px;
  font-size: 14px;
  display: flex;
  gap: 8px;
  align-items: center;
}

.reason-text {
  flex: 1;
}

.reason-unknown {
  border-left: 4px solid var(--amber);
}

.reason-same {
  border-left: 4px solid var(--red);
}

.hint {
  font-size: 14px;
}
</style>
