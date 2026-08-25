// @vitest-environment happy-dom
//
// R5 deliverable: editable migrated research workspace UIs.
//
// Validates the five new renderer pages can be mounted with the
// contextBridge-style global window.migration / window.workspace
// stubs, and that they surface the expected DOM hooks the manual QA
// (and the eventual production wiring) rely on.
//
// We deliberately *do not* assert on snapshot IDs or fs paths: the
// R4 IPC layer was already covered by mbrp-importer.test.ts.
// These tests only prove the renderer is wired up to the contract
// R4 promised.

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'

interface MigrationApi {
  preflight: ReturnType<typeof vi.fn>
  import: ReturnType<typeof vi.fn>
  runs: ReturnType<typeof vi.fn>
}

interface WorkspaceApi {
  listProjects: ReturnType<typeof vi.fn>
  listTasks: ReturnType<typeof vi.fn>
  updateTaskStatus: ReturnType<typeof vi.fn>
  listMeetings: ReturnType<typeof vi.fn>
  readMeeting: ReturnType<typeof vi.fn>
  saveMeeting: ReturnType<typeof vi.fn>
  listFiles: ReturnType<typeof vi.fn>
  readFile: ReturnType<typeof vi.fn>
  saveFile: ReturnType<typeof vi.fn>
  listConversations: ReturnType<typeof vi.fn>
}

function installMigrationStub(overrides: Partial<MigrationApi> = {}): MigrationApi {
  const api: MigrationApi = {
    preflight: vi.fn().mockResolvedValue({ ok: true }),
    import: vi.fn().mockResolvedValue({ ok: true, runId: 'run-stub', filesWritten: 4 }),
    runs: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
  ;(globalThis as unknown as { window: { migration: MigrationApi } }).window.migration = api
  return api
}

function installWorkspaceStub(overrides: Partial<WorkspaceApi> = {}): WorkspaceApi {
  const api: WorkspaceApi = {
    listProjects: vi.fn().mockResolvedValue([{ id: 'p-1', name: 'P1' }]),
    listTasks: vi
      .fn()
      .mockResolvedValue([
        { id: 't-1', title: 'Run experiment A', status: 'in_progress' },
        { id: 't-2', title: 'Write summary', status: 'done' },
      ]),
    updateTaskStatus: vi.fn().mockResolvedValue({ ok: true }),
    listMeetings: vi.fn().mockResolvedValue([{ id: 'm-1', title: 'Weekly sync' }]),
    readMeeting: vi.fn().mockResolvedValue('# Weekly sync\n\nNotes...'),
    saveMeeting: vi.fn().mockResolvedValue({ ok: true }),
    listFiles: vi.fn().mockResolvedValue([{ path: 'projects/p-1/overview.md', name: 'overview.md' }]),
    readFile: vi.fn().mockResolvedValue({ content: '# Overview', version: 1 }),
    saveFile: vi.fn().mockResolvedValue({ ok: true, version: 2 }),
    listConversations: vi.fn().mockResolvedValue([
      {
        id: 's-1',
        messages: [
          { id: 'msg-1', role: 'user', content: 'zeta potential next week?' },
          { id: 'msg-2', role: 'assistant', content: 'we should sample on Tuesday' },
        ],
      },
    ]),
    ...overrides,
  }
  ;(globalThis as unknown as { window: { workspace: WorkspaceApi } }).window.workspace = api
  return api
}

describe('MigrationCenter (R5)', () => {
  beforeEach(() => {
    installMigrationStub()
  })

  it('renders preflight + import controls calling window.migration', async () => {
    const { default: MigrationCenter } = await import('@/pages/migration/MigrationCenter.vue')
    const wrapper = mount(MigrationCenter)
    await flushPromises()

    expect(wrapper.text()).toMatch(/Preflight|Pre-flight|i?预检/i)
    expect(wrapper.text()).toMatch(/Import|i?导入/i)
    expect(wrapper.find('[data-testid="preflight-btn"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="import-btn"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('runs preflight through the IPC bridge', async () => {
    const api = installMigrationStub({
      preflight: vi.fn().mockResolvedValue({ ok: false, code: 'NOT_FOUND', message: 'missing' }),
    })
    const { default: MigrationCenter } = await import('@/pages/migration/MigrationCenter.vue')
    const wrapper = mount(MigrationCenter)
    await flushPromises()

    const vm = wrapper.vm as unknown as { runPreflight: () => Promise<void>; packagePath: string }
    vm.packagePath = 'C:/sample.mbrp'
    await vm.runPreflight()
    await flushPromises()

    expect(api.preflight).toHaveBeenCalledWith('C:/sample.mbrp')
    expect(wrapper.text()).toMatch(/NOT_FOUND|missing/)
    wrapper.unmount()
  })
})

describe('WorkItemsWorkspace (R5)', () => {
  beforeEach(() => {
    installWorkspaceStub()
  })

  it('lists imported tasks and toggles status', async () => {
    const api = installWorkspaceStub({
      updateTaskStatus: vi.fn().mockResolvedValue({ ok: true }),
    })
    const { default: WorkItemsWorkspace } = await import('@/pages/workspace/WorkItemsWorkspace.vue')
    const wrapper = mount(WorkItemsWorkspace)
    await flushPromises()

    expect(wrapper.text()).toContain('Run experiment A')
    expect(wrapper.text()).toContain('Write summary')

    const first = wrapper.find('[data-testid="task-status"]')
    expect(first.exists()).toBe(true)
    await first.trigger('click')
    await flushPromises()

    expect(api.updateTaskStatus).toHaveBeenCalledWith('t-1', 'done')
    wrapper.unmount()
  })

  it('shows empty state when no tasks are imported', async () => {
    installWorkspaceStub({
      listTasks: vi.fn().mockResolvedValue([]),
    })
    const { default: WorkItemsWorkspace } = await import('@/pages/workspace/WorkItemsWorkspace.vue')
    const wrapper = mount(WorkItemsWorkspace)
    await flushPromises()

    expect(wrapper.text()).toMatch(/Empty|No tasks|暂无/i)
    wrapper.unmount()
  })
})

describe('MeetingArchiveWorkspace (R5)', () => {
  beforeEach(() => {
    installWorkspaceStub()
  })

  it('loads meeting markdown and saves edits through IPC', async () => {
    const api = installWorkspaceStub()
    const { default: MeetingArchiveWorkspace } = await import(
      '@/pages/workspace/MeetingArchiveWorkspace.vue'
    )
    const wrapper = mount(MeetingArchiveWorkspace)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      meetings: Array<{ id: string; title: string }>
      selectedMeeting: string
      loadMeeting: () => Promise<void>
      content: string
      save: () => Promise<void>
    }
    expect(vm.meetings.length).toBeGreaterThan(0)
    vm.selectedMeeting = vm.meetings[0].id
    await vm.loadMeeting()
    await flushPromises()

    expect(vm.content).toContain('Weekly sync')
    expect(api.readMeeting).toHaveBeenCalled()

    vm.content = '# Weekly sync\n\nEdited body'
    await vm.save()
    await flushPromises()
    expect(api.saveMeeting).toHaveBeenCalledWith(
      vm.meetings[0].id,
      '# Weekly sync\n\nEdited body',
    )

    wrapper.unmount()
  })
})

describe('FileLibraryWorkspace (R5)', () => {
  beforeEach(() => {
    installWorkspaceStub()
  })

  it('shows version counter and saves into a new version', async () => {
    const api = installWorkspaceStub()
    const { default: FileLibraryWorkspace } = await import(
      '@/pages/workspace/FileLibraryWorkspace.vue'
    )
    const wrapper = mount(FileLibraryWorkspace)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      files: Array<{ path: string; name: string }>
      selectedFile: string
      loadFile: () => Promise<void>
      content: string
      save: () => Promise<void>
      version: number
    }
    expect(vm.files.length).toBeGreaterThan(0)
    vm.selectedFile = vm.files[0].path
    await vm.loadFile()
    await flushPromises()

    expect(vm.version).toBe(1)
    vm.content = '# Overview\n\nUpdated content'
    await vm.save()
    await flushPromises()
    expect(api.saveFile).toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('ConversationArchiveWorkspace (R5)', () => {
  beforeEach(() => {
    installWorkspaceStub()
  })

  it('returns matching messages on keyword search', async () => {
    const { default: ConversationArchiveWorkspace } = await import(
      '@/pages/workspace/ConversationArchiveWorkspace.vue'
    )
    const wrapper = mount(ConversationArchiveWorkspace)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      query: string
      search: () => void
      results: Array<{ id: string; role: string; content: string }>
    }
    vm.query = 'zeta'
    vm.search()
    await flushPromises()
    expect(vm.results.some((r) => r.content.includes('zeta'))).toBe(true)

    vm.query = 'sample'
    vm.search()
    await flushPromises()
    expect(vm.results.every((r) => r.content.toLowerCase().includes('sample'))).toBe(true)

    wrapper.unmount()
  })

  it('clears results when query is empty', async () => {
    const { default: ConversationArchiveWorkspace } = await import(
      '@/pages/workspace/ConversationArchiveWorkspace.vue'
    )
    const wrapper = mount(ConversationArchiveWorkspace)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      query: string
      search: () => void
      results: Array<unknown>
    }
    vm.query = 'zeta'
    vm.search()
    await flushPromises()
    expect(vm.results.length).toBeGreaterThan(0)

    vm.query = ''
    vm.search()
    await flushPromises()
    expect(vm.results.length).toBe(0)

    wrapper.unmount()
  })
})
