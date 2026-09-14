import type {
  ComputeResult,
  Project,
  ProjectInput,
  Snapshot,
} from './types'

const BASE = '/api'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `请求失败（${res.status}）`
    try {
      const data = await res.json()
      if (data?.detail) {
        detail =
          typeof data.detail === 'string'
            ? data.detail
            : data.detail.map((d: { msg?: string }) => d.msg).join('；')
      }
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<{ status: string }>(`${BASE}/health`),

  listProjects: () => request<Project[]>(`${BASE}/projects`),

  getProject: (id: number) =>
    request<Project>(`${BASE}/projects/${id}`),

  createProject: (input: ProjectInput) =>
    request<Project>(`${BASE}/projects`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  updateProject: (id: number, input: ProjectInput) =>
    request<Project>(`${BASE}/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(input),
    }),

  deleteProject: (id: number) =>
    request<void>(`${BASE}/projects/${id}`, { method: 'DELETE' }),

  compute: (id: number) =>
    request<{
      result: ComputeResult
      savedSnapshot: boolean
      snapshotId: number
    }>(`${BASE}/projects/${id}/compute`, { method: 'POST' }),

  listSnapshots: (id: number) =>
    request<Snapshot[]>(`${BASE}/projects/${id}/snapshots`),

  getSnapshot: (id: number) =>
    request<Snapshot>(`${BASE}/snapshots/${id}`),
}
