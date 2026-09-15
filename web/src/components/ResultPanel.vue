<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  BlockReason,
  ComputeResult,
  LeafCardAttribute,
  LeafCardObject,
} from '../types'
import { objectName } from '../util'
import TreeView from './TreeView.vue'
import TreeWalk from './TreeWalk.vue'
import ReasonList from './ReasonList.vue'

const props = defineProps<{
  result: ComputeResult
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  /** false 时表示这是旧输入下保存的结果（快照视图等） */
  fresh: boolean
}>()

const tab = ref<'walk' | 'tree'>('walk')
watch(
  () => props.result,
  () => (tab.value = 'walk'),
)

const names = (ids: number[]) => ids.map((i) => objectName(props.objects, i))

const attrLabel = (id: number) =>
  props.attributes.find((a) => a.id === id)?.label ?? `特征 ${id}`

const pathWords = (path: ('true' | 'false')[]) =>
  path.length
    ? path.map((b, i) => `${i + 1} 答「${b === 'true' ? '是' : '不是'}」`).join('，')
    : '一开始（第一个问题）'

const reasonText = (r: BlockReason) => {
  if (r.reason === 'unknown') {
    return `卡片「${names(r.objectIds).join('、')}」在这个特征上还是「？」（还没观察），不能拿来分组。`
  }
  return `这些卡片在这里全都${
    r.value === 'true' ? '为真（有）' : '为假（没有）'
  }，分不出两边。`
}

const okResult = computed(() =>
  props.result.status === 'ok' ? props.result : null,
)
const noLock = computed(() =>
  props.result.status === 'no_lock' ? props.result : null,
)
const inseparable = computed(() =>
  props.result.status === 'inseparable' ? props.result : null,
)
</script>

<template>
  <div>
    <div v-if="!fresh" class="banner banner-info">
      ⚠️ 这是旧输入下保存的辨认树。卡片或特征后来改过，重新「算出辨认树」才会和现在的观察一致。
    </div>

    <!-- 成功：完整辨认树 -->
    <template v-if="okResult">
      <p class="banner banner-ok">
        ✅ 每一步都能把剩下的卡片分成不空的两边，一直分到只剩一张。
        最坏情况下要问 <b>{{ okResult.score.maxDepth }}</b> 问，
        全部卡片的问题总数 <b>{{ okResult.score.sumDepth }}</b>，已经做到最小。
      </p>
      <p v-if="(okResult.locks?.length ?? 0) > 0" class="banner banner-info">
        🔒 已按你的 {{ okResult.locks!.length }} 条预定步骤固定相应问题（树中带 🔒 标记）。
      </p>

      <div class="tabs">
        <button
          class="tab"
          :class="{ active: tab === 'walk' }"
          @click="tab = 'walk'"
        >
          🚶 逐问试走
        </button>
        <button
          class="tab"
          :class="{ active: tab === 'tree' }"
          @click="tab = 'tree'"
        >
          🌳 整棵树
        </button>
      </div>

      <TreeWalk
        v-if="tab === 'walk'"
        :tree="okResult.tree"
        :objects="objects"
        :attributes="attributes"
      />
      <div v-else class="tree-scroll">
        <TreeView
          :node="okResult.tree"
          :objects="objects"
          :attributes="attributes"
          :depth="0"
        />
      </div>
    </template>

    <!-- 锁定无解：沿假/真路径走进死胡同 -->
    <template v-else-if="noLock">
      <div class="fail-box">
        <p class="fail-emoji">🔒</p>
        <h3>
          {{
            noLock.violatedLock
              ? '预定要问的特征在这里用不了'
              : '按特征一路锁下去，最后有几张叶子分不开'
          }}
        </h3>

        <div v-if="noLock.violatedLock" class="violated">
          你预定：<b>{{ pathWords(noLock.violatedLock.path) }}</b
          >时必须问
          <b>
            <span class="id-badge">{{ noLock.violatedLock.attributeId }}</span>
            {{ attrLabel(noLock.violatedLock.attributeId) }}
          </b>
          ，但这个特征在这里分不出卡片（见下）。
        </div>

        <p v-if="noLock.blockingPath.length">
          从根开始，最短的死路是这样走：
        </p>
        <ol v-if="noLock.blockingPath.length" class="path">
          <li v-for="(step, i) in noLock.blockingPath" :key="i">
            问「<b>{{ attrLabel(step.attributeId) }}</b
            >？」→ 回答
            <b :class="step.branch === 'true' ? 'ans-yes' : 'ans-no'">
              {{ step.branch === 'true' ? '是（真）' : '不是（假）' }}
            </b>
          </li>
        </ol>
        <p>
          走到最后，分不开的卡片是：
          <b>{{ names(noLock.terminalObjectIds).join('、') }}</b>
          （卡片编号 {{ noLock.terminalObjectIds.join('、') }}）。
        </p>
      </div>
      <ReasonList :reasons="noLock.reasons" :reason-text="reasonText" />
    </template>

    <!-- 其他无解：存在无合法二分属性的小组 -->
    <template v-else-if="inseparable">
      <div class="fail-box">
        <p class="fail-emoji">🧐</p>
        <h3>这些卡片观察得还不够，分不出彼此</h3>
        <p>
          最小的一组是：<b>{{ names(inseparable.subset).join('、') }}</b>
          （卡片编号 {{ inseparable.subset.join('、') }}）。
          没有任何一个特征能把这组分出两个非空的组。
        </p>
      </div>
      <ReasonList :reasons="inseparable.reasons" :reason-text="reasonText" />
    </template>
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.tab {
  border-radius: 12px;
  background: #eef4f0;
  color: var(--grey);
  font-weight: 700;
}

.tab.active {
  background: var(--green-700);
  color: #fff;
}

.tree-scroll {
  overflow-x: auto;
  padding: 18px 8px 8px;
}

.fail-box {
  background: #fff8f3;
  border: 1px solid #f3ddb0;
  border-radius: 14px;
  padding: 12px 18px;
}

.fail-emoji {
  font-size: 40px;
  margin: 4px 0;
}

.path {
  background: #fff;
  border-radius: 10px;
  padding: 10px 10px 10px 30px;
  border: 1px dashed var(--line);
}

.path li {
  margin-bottom: 4px;
}

.violated {
  background: #fff;
  border: 1px solid #f3ddb0;
  border-radius: 10px;
  padding: 8px 12px;
  margin: 8px 0;
  font-size: 15px;
}

.ans-yes {
  color: var(--green-700);
}

.ans-no {
  color: var(--red);
}
</style>
