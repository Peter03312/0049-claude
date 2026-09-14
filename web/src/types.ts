// 前后端共享的领域类型

export type Tribool = 'true' | 'false' | 'unknown'

export interface LeafCardObject {
  id: number
  label: string
  note: string
}

export interface LeafCardAttribute {
  id: number
  label: string
}

export interface CellMap {
  [key: string]: Tribool
}

export interface TreeNode {
  type: 'question'
  attributeId: number
  false: TreeNode | LeafNode
  true: TreeNode | LeafNode
}

export interface LeafNode {
  type: 'leaf'
  objectId: number
}

export interface TreeScore {
  maxDepth: number
  sumDepth: number
  preorder: number[]
}

export interface BlockStep {
  attributeId: number
  branch: 'true' | 'false'
}

export interface BlockReason {
  attributeId: number
  reason: 'unknown' | 'same'
  value?: 'true' | 'false'
  objectIds: number[]
}

export type ComputeResult =
  | { status: 'ok'; tree: TreeNode; score: TreeScore }
  | {
      status: 'no_lock'
      blockingPath: BlockStep[]
      terminalObjectIds: number[]
      reasons: BlockReason[]
    }
  | {
      status: 'inseparable'
      subset: number[]
      reasons: BlockReason[]
    }

export interface Project {
  id: number
  name: string
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  cells: CellMap
  inputVersion: number
  result: ComputeResult | null
  resultVersion: number | null
  resultFresh: boolean
  createdAt: string
  updatedAt: string
}

export interface Snapshot {
  id: number
  projectId: number
  inputVersion: number
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  cells: CellMap
  result: ComputeResult
  createdAt: string
}

export interface ProjectInput {
  name: string
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  cells: CellMap
}
