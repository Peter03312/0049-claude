<script setup lang="ts">
import type {
  LeafCardAttribute,
  LeafCardObject,
  LeafNode,
  TreeNode,
} from '../types'
import { attributeName, objectName } from '../util'

defineProps<{
  node: TreeNode | LeafNode
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  branchLabel?: '假' | '真' | null
  depth?: number
}>()
</script>

<template>
  <div class="tree-node" :class="{ leaf: node.type === 'leaf' }">
    <div
      v-if="branchLabel"
      class="edge"
      :class="branchLabel === '假' ? 'edge-false' : 'edge-true'"
    >
      {{ branchLabel === '假' ? '✗ 假' : '✓ 真' }}
    </div>

    <div v-if="node.type === 'question'" class="question-box">
      <div class="q-title">
        <span class="q-step">第 {{ (depth ?? 0) + 1 }} 问</span>
        <span class="id-badge">{{ node.attributeId }}</span>
        <strong>{{ attributeName(attributes, node.attributeId) }}？</strong>
      </div>
      <div class="children">
        <TreeView
          :node="node.false"
          :objects="objects"
          :attributes="attributes"
          branch-label="假"
          :depth="(depth ?? 0) + 1"
        />
        <TreeView
          :node="node.true"
          :objects="objects"
          :attributes="attributes"
          branch-label="真"
          :depth="(depth ?? 0) + 1"
        />
      </div>
    </div>

    <div v-else class="leaf-box">
      🍃 <strong>{{ objectName(objects, node.objectId) }}</strong>
      <span class="muted">（卡片 {{ node.objectId }}）</span>
    </div>
  </div>
</template>

<style scoped>
.tree-node {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.edge {
  font-size: 12px;
  font-weight: 800;
  padding: 1px 8px;
  border-radius: 999px;
  margin-bottom: 4px;
}

.edge-false {
  background: #fde8e2;
  color: var(--red);
}

.edge-true {
  background: var(--green-50);
  color: var(--green-700);
  border: 1px solid var(--green-200);
}

.question-box {
  border: 2px solid var(--green-500);
  border-radius: 14px;
  padding: 10px 14px;
  background: #fff;
  min-width: 150px;
  text-align: center;
}

.q-title {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.q-step {
  font-size: 12px;
  background: var(--green-700);
  color: #fff;
  border-radius: 999px;
  padding: 1px 10px;
}

.children {
  display: flex;
  gap: 22px;
  justify-content: center;
  position: relative;
  padding-top: 10px;
}

.children::before {
  content: '';
  position: absolute;
  top: 0;
  left: 25%;
  right: 25%;
  height: 10px;
  border-top: 2px solid var(--green-200);
}

.children > .tree-node::before {
  content: '';
  width: 2px;
  height: 10px;
  background: var(--green-200);
}

.leaf-box {
  background: var(--green-200);
  border-radius: 12px;
  padding: 8px 14px;
  white-space: nowrap;
}

.leaf .edge {
  display: none;
}
</style>
