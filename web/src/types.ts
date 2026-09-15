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
  /** 该节点是否由用户的预定步骤（路径锁定）指定 */
  locked?: boolean
  lockPath?: ('true' | 'false')[]
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

/** 路径锁定：path 为从根起的假/真回答（空数组=根节点），
 *  attributeId 为走到该节点时必须询问的特征。 */
export interface PathLock {
  path: ('true' | 'false')[]
  attributeId: number
}

export type ComputeResult =
  | { status: 'ok'; tree: TreeNode; score: TreeScore; locks?: PathLock[] }
  | {
      status: 'no_lock'
      blockingPath: BlockStep[]
      terminalObjectIds: number[]
      reasons: BlockReason[]
      locks?: PathLock[]
      violatedLock?: PathLock
      /** true：沿预定路线在必问题之前就只剩一张卡（答案提前到达） */
      earlyAnswer?: boolean
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
  locks: PathLock[]
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
  locks: PathLock[]
  result: ComputeResult
  createdAt: string
}

export interface ProjectInput {
  name: string
  objects: LeafCardObject[]
  attributes: LeafCardAttribute[]
  cells: CellMap
  locks: PathLock[]
}
