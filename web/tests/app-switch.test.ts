import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'

// 两张卡，B 带一棵可用的树
const projectA = {
  id: 1,
  name: '甲卡集',
  objects: [
    { id: 1, label: 'A甲', note: '' },
    { id: 2, label: 'A乙', note: '' },
    { id: 3, label: 'A丙', note: '' },
    { id: 4, label: 'A丁', note: '' },
  ],
  attributes: [{ id: 1, label: 'A特征一' }],
  cells: { '1:1': 'true' },
  locks: [],
  inputVersion: 1,
  result: null,
  resultVersion: null,
  resultFresh: false,
  createdAt: '',
  updatedAt: '',
}
const projectB = {
  id: 2,
  name: '乙卡集',
  objects: [
    { id: 1, label: 'B松', note: '' },
    { id: 2, label: 'B竹', note: '' },
    { id: 3, label: 'B梅', note: '' },
    { id: 4, label: 'B兰', note: '' },
  ],
  attributes: [
    { id: 1, label: 'B特征一' },
    { id: 2, label: 'B特征二' },
  ],
  cells: { '1:1': 'false', '2:2': 'true' },
  locks: [],
  inputVersion: 1,
  result: null,
  resultVersion: null,
  resultFresh: false,
  createdAt: '',
  updatedAt: '',
}

const apiMock = vi.hoisted(() => ({
  listProjects: vi.fn(),
  getProject: vi.fn(),
  listSnapshots: vi.fn(),
  compute: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
}))

vi.mock('../src/api', () => ({
  api: {
    listProjects: apiMock.listProjects,
    getProject: apiMock.getProject,
    listSnapshots: apiMock.listSnapshots,
    compute: apiMock.compute,
    createProject: apiMock.createProject,
    updateProject: apiMock.updateProject,
    deleteProject: apiMock.deleteProject,
  },
}))

import App from '../src/App.vue'

function raw<T>(v: T): T {
  return JSON.parse(JSON.stringify(v))
}

beforeEach(() => {
  localStorage.clear()
  apiMock.listProjects.mockReset().mockResolvedValue(raw([projectA, projectB]))
  apiMock.getProject.mockReset().mockImplementation(async (id: number) =>
    raw(id === 1 ? projectA : projectB),
  )
  apiMock.listSnapshots.mockReset().mockResolvedValue([])
  apiMock.compute.mockReset().mockResolvedValue({
    result: { status: 'inseparable', subset: [1, 2], reasons: [] },
    savedSnapshot: true,
    snapshotId: 1,
  })
  apiMock.createProject.mockReset()
  apiMock.updateProject.mockReset()
  apiMock.deleteProject.mockReset()
})

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  return wrapper
    .findAll('button')
    .find((b) => b.text().includes(text))
}

describe('刷新后切换已保存的辨认卡', () => {
  it('boot 自动打开最近的卡；点另一张后标题、对象、特征全部切换且不脏', async () => {
    // 模拟上次正在看 A
    localStorage.setItem('leafcards.currentId', '1')
    const wrapper = mount(App)
    await flushPromises()
    await nextTick()

    let text = wrapper.text()
    expect(text).toContain('A甲')
    expect(text).not.toContain('B松')

    // 点 B
    const chips = wrapper.findAll('.project-chip')
    await chips[1].trigger('click')
    await nextTick()

    text = wrapper.text()
    expect(text).toContain('B松')
    expect(text).toContain('B特征二')
    expect(text).not.toContain('A甲')
    // 不应被标记为有未保存修改
    expect(text).not.toContain('有未保存的修改')
  })

  it('切换后「重新算出辨认树」按钮可用并真正请求 B', async () => {
    localStorage.setItem('leafcards.currentId', '1')
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.findAll('.project-chip')[1].trigger('click')
    await nextTick()

    const recompute = findButton(wrapper, '重新算出辨认树')
    expect(recompute).toBeTruthy()
    expect(recompute!.attributes('disabled')).toBeUndefined()
    await recompute!.trigger('click')
    await flushPromises()
    expect(apiMock.compute).toHaveBeenCalledWith(2)
  })
})
