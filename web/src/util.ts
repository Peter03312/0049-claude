import type {
  LeafNode,
  LeafCardAttribute,
  LeafCardObject,
  TreeNode,
} from './types'

export const cellKey = (objectId: number, attributeId: number) =>
  `${objectId}:${attributeId}`

export const objectName = (
  objects: LeafCardObject[],
  id: number,
): string => objects.find((o) => o.id === id)?.label ?? `卡片 ${id}`

export const attributeName = (
  attributes: LeafCardAttribute[],
  id: number,
): string => attributes.find((a) => a.id === id)?.label ?? `特征 ${id}`

export const nextId = (items: { id: number }[]): number =>
  items.reduce((m, x) => Math.max(m, x.id), 0) + 1

/** 收集一个节点下面所有叶子（= 走到这里时仍可能的卡片）。 */
export function leafIds(node: TreeNode | LeafNode): number[] {
  if (node.type === 'leaf') return [node.objectId]
  return [...leafIds(node.false), ...leafIds(node.true)]
}
