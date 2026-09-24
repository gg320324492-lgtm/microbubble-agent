// DL-2 缺陷回放 —— 网盘文件列表缺失（只列文件夹，文件夹内文件不显示）
//
// 病根（用户 F12 实测确认）：桌面用 `parent_id` 调 /drive/files，而服务端契约是 **`folder_id`**
//   → 参数不识别 → 永远返回根视图 → **文件夹内文件不显示**；
//   目录树另走 /folders 自造树 → 与网页端 /drive/tree?scope=team 不一致。
//
// 本文件锁定「对齐实测契约」这一事实，防复发。
import { describe, expect, it } from 'vitest'
import { normalizeTree, normalizeDrivePage } from '@main/services/cloud/drive'

// ---------------------------------------------------------------- 1 树契约（≥1）

describe('DL-2 文件夹树契约', () => {
  it('★ 递归展开 children 为扁平列表（带 parentId，供建树/面包屑）', () => {
    const raw = {
      items: [
        { id: 10, name: '组会PPT', parent_id: null, children: [{ id: 336, name: '艾琳琳', parent_id: 10 }] },
        { id: 20, name: '实验数据', parent_id: null, children: [] },
        { id: 30, name: '项目资料', parent_id: null }
      ]
    }
    const flat = normalizeTree(raw)
    expect(flat.map((f) => f.name)).toEqual(['组会PPT', '艾琳琳', '实验数据', '项目资料'])
    expect(flat.find((f) => f.id === 336)?.parentId).toBe(10)
    expect(flat.find((f) => f.id === 10)?.parentId).toBeNull()
  })

  it('★ 容忍多种形状：裸数组 / {tree} / {nodes} / 节点用 nodes|subfolders 装子级', () => {
    expect(normalizeTree([{ id: 1, name: 'A' }]).map((f) => f.name)).toEqual(['A'])
    expect(normalizeTree({ tree: [{ id: 2, name: 'B' }] }).map((f) => f.name)).toEqual(['B'])
    expect(normalizeTree({ nodes: [{ id: 3, name: 'C', nodes: [{ id: 4, name: 'C1' }] }] }).map((f) => f.name)).toEqual(['C', 'C1'])
    expect(normalizeTree({ data: [{ id: 5, name: 'D', subfolders: [{ id: 6, name: 'D1' }] }] }).map((f) => f.name)).toEqual(['D', 'D1'])
    // 畸形：缺 id/name 的节点被丢弃，不产生空条目
    expect(normalizeTree({ items: [{ name: '无id' }, { id: 7 }] })).toEqual([])
    expect(normalizeTree(null)).toEqual([])
  })

  it('子级未带 parent_id 时，用遍历上下文补 parentId（实测树可能不返该字段）', () => {
    const flat = normalizeTree({ items: [{ id: 10, name: '父', children: [{ id: 11, name: '子' }] }] })
    expect(flat.find((f) => f.id === 11)?.parentId).toBe(10)
  })
})

// ---------------------------------------------------------------- 2 files 契约（≥1）

describe('DL-2 文件列表契约（归一化）', () => {
  it('★ 实测 item 形状完整映射（含上传者与时间，供 web 列呈现）', () => {
    const page = normalizeDrivePage({
      items: [
        {
          id: 501,
          title: '2026.3.23 大二-艾琳琳.pptx',
          file_name: '2026.3.23 大二-艾琳琳.pptx',
          file_type: 'pptx',
          file_size: 115610891,
          storage_mode: 'oss',
          visibility: 'team',
          folder_id: 336,
          folder_name: '艾琳琳',
          owner_name: '杜同贺',
          owner_username: 'dutonghe',
          created_at: '2026-03-23T10:00:00',
          updated_at: '2026-03-23T10:05:00',
          is_team_shared: true
        }
      ],
      total: 2,
      page: 1,
      page_size: 20
    })
    expect(page.total).toBe(2)
    const it0 = page.items[0]!
    expect(it0.id).toBe(501)
    expect(it0.fileName).toBe('2026.3.23 大二-艾琳琳.pptx')
    expect(it0.fileSize).toBe(115610891) // 真实字节（UI 格式化为 110.3 MB）
    expect(it0.folderId).toBe(336)
    expect(it0.ownerName).toBe('杜同贺')
    expect(it0.createdAt).toBe('2026-03-23T10:00:00')
  })

  it('★ 根视图（total=0, items=[]）与子目录（有文件）两态都能解析', () => {
    const root = normalizeDrivePage({ items: [], total: 0, page: 1, page_size: 20 })
    expect(root.total).toBe(0)
    expect(root.items).toEqual([])
    const sub = normalizeDrivePage({ items: [{ id: 1, file_name: 'a.pptx', file_size: 100 }], total: 1 })
    expect(sub.items).toHaveLength(1)
    expect(sub.total).toBe(1)
  })

  it('容忍裸数组与缺字段（不因缺 title 丢条目）', () => {
    const p = normalizeDrivePage([{ id: 2, file_name: 'b.pdf', file_size: 10 }])
    expect(p.items).toHaveLength(1)
    expect(p.items[0]!.title).toBe('b.pdf') // title 缺失时回退 file_name
    // 缺 file_name/title 的条目被丢弃（无法呈现）
    expect(normalizeDrivePage([{ id: 3 }]).items).toEqual([])
  })
})
