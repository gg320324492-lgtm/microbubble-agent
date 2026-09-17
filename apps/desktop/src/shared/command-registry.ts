// 命令注册表（M4）— 纯逻辑类，零依赖可离线单测。
// 过滤：标题/关键词/拼音首字母子串匹配（大小写不敏感）；execute 执行回调并回执。
export interface Command {
  id: string
  title: string
  /** 空格分隔的辅助匹配词（可含拼音首字母，如 'sy xiaojiedian'） */
  keywords?: string
  action: () => void
}

export class CommandRegistry {
  private readonly commands = new Map<string, Command>()

  register(cmd: Command): void {
    if (!cmd.id) throw new Error('命令 id 不能为空')
    if (this.commands.has(cmd.id)) throw new Error(`命令已注册: ${cmd.id}`)
    this.commands.set(cmd.id, { ...cmd, title: cmd.title.trim() })
  }

  unregister(id: string): boolean {
    return this.commands.delete(id)
  }

  list(): Command[] {
    return [...this.commands.values()]
  }

  /** 子串过滤：命中标题或 keywords 任一即保留；空查询返回全部（按注册顺序） */
  filter(query: string): Command[] {
    const q = query.trim().toLowerCase()
    if (!q) return this.list()
    return this.list().filter((c) => {
      if (c.title.toLowerCase().includes(q)) return true
      if (c.keywords && c.keywords.toLowerCase().includes(q)) return true
      // 逐词前缀匹配（keywords 空格分隔，任一词以查询开头即命中——拼音首字母场景）
      return (c.keywords ?? '').split(/\s+/).some((k) => k.startsWith(q))
    })
  }

  /** 执行命令；返回 false = 不存在 */
  execute(id: string): boolean {
    const cmd = this.commands.get(id)
    if (!cmd) return false
    cmd.action()
    return true
  }
}
