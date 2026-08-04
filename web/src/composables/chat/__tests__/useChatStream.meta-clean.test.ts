import { describe, expect, it } from 'vitest'
import { stripMetaSuffix } from '../useChatStream'

describe('W100 +58 meta clean (useChatStream.stripMetaSuffix)', () => {
  it('删除 "数据来源: query_members 工具返回的成员信息 [1]" 整段', () => {
    const input = '课题组有 1 名博一学生: 张三 (研究方向: 黑臭水体)。\n数据来源: query_members 工具返回的成员信息 [1]'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('数据来源')
    expect(out).not.toContain('query_members')
    expect(out).toContain('张三')
  })

  it('删除 "[1] xxx (query_xxx)" 引用列表中括号内 tool 名', () => {
    const input = '一些回答内容 [1] [2]\n\n[1] 课题组成员信息 (query_members)\n[2] 气泡成核过程调控 (search_knowledge)'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('(query_members)')
    expect(out).not.toContain('(search_knowledge)')
    expect(out).toContain('[1] 课题组成员信息')
    expect(out).toContain('[2] 气泡成核过程调控')
  })

  it('删除 "**数据来源: ...**" 整行 (加粗 meta 段)', () => {
    const input = '一些正文内容。\n**数据来源: query_members 工具返回的成员信息 [1]**\n更多内容'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('数据来源')
    expect(out).not.toContain('query_members')
    expect(out).toContain('一些正文内容')
    expect(out).toContain('更多内容')
  })

  it('正常内容不被误删 (无 meta 段时原文不动)', () => {
    const input = '课题组有 1 名博一学生: 张三 (研究方向: 黑臭水体)。\n\n[1] 微纳米气泡技术综述'
    const out = stripMetaSuffix(input)
    expect(out).toBe(input)
  })

  it('删除 "来源: 知识库检索 [3][4]" 段', () => {
    const input = '正文最后一句。\n来源: 知识库检索 [3][4]'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('来源: 知识库')
    expect(out).not.toContain('[3][4]')
    expect(out).toContain('正文最后一句')
  })

  it('删除 "**来源: XXX**" 加粗段', () => {
    const input = '一些内容。\n**来源: 知识库检索 [3][4]**'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('**来源')
    expect(out).toContain('一些内容')
  })

  it('连续多个 meta 段全部清除', () => {
    const input = '正文。\n数据来源: query_members 工具 [1]\n**数据来源: 成员角色字段 [1]**\n**来源: 知识库检索 [3][4]**'
    const out = stripMetaSuffix(input)
    expect(out).not.toContain('数据来源')
    expect(out).not.toContain('**来源')
    expect(out).toContain('正文')
  })

  it('空字符串 / undefined 等价空字符串处理', () => {
    expect(stripMetaSuffix('')).toBe('')
  })
})
