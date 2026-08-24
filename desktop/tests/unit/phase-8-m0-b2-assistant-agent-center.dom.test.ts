// @vitest-environment happy-dom
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parse as parseSfc } from '@vue/compiler-sfc'
import { describe, expect, it } from 'vitest'

/**
 * Phase 8-M0-B2 is intentionally red before the presentation components and
 * page compositions exist. Missing shared components have one explicit file
 * assertion each; all of their source assertions short-circuit to avoid an
 * ENOENT failure flood that would hide the actionable red signal.
 */
const desktopRoot = resolve(__dirname, '../..')
const rendererRoot = resolve(desktopRoot, 'src/renderer/src')
const researchComponentRoot = resolve(rendererRoot, 'components/research')
const researchPageRoot = resolve(rendererRoot, 'pages/research')

const withoutComments = (source: string): string =>
  source.replace(/<!--[\s\S]*?-->|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g, '')

const sourceAt = (path: string): string =>
  existsSync(path) ? withoutComments(readFileSync(path, 'utf8')) : ''

const componentPath = (fileName: string): string => resolve(researchComponentRoot, fileName)
const componentSource = (fileName: string): string => sourceAt(componentPath(fileName))
const pagePath = (fileName: string): string => resolve(researchPageRoot, fileName)
const pageSource = (fileName: string): string => sourceAt(pagePath(fileName))

type SourceRule = readonly [label: string, predicate: (source: string) => boolean]

const isMissingOr = (source: string, predicate: (source: string) => boolean): boolean =>
  source === '' || predicate(source)

const importsComponent = (source: string, symbol: string, fileName: string): boolean =>
  new RegExp(`import[\\s\\S]{0,240}\\b${symbol}\\b[\\s\\S]{0,240}from\\s+['"][^'"]*${fileName}['"]`).test(source)

const rendersComponent = (source: string, component: string): boolean =>
  new RegExp(`<${component}(?:\\s|/|>)`).test(source)

const toolExecutionLoopUsesUniqueIndexKey = (source: string): boolean => {
  const template = parseSfc(source).descriptor.template?.content ?? ''
  return [...template.matchAll(/<li\b[\s\S]{0,1200}?>/g)].some(match => {
    const tag = match[0]
    const loop = tag.match(/v-for\s*=\s*['"]\s*\(\s*([A-Za-z_$]\w*)\s*,\s*([A-Za-z_$]\w*)\s*\)\s+(?:in|of)\s+(?:props\.)?executions\s*['"]/)
    if (!loop) return false

    const index = loop[2]
    return new RegExp(`:key\\s*=\\s*['"][^'"]*\\b${index}\\b[^'"]*['"]`).test(tag)
  })
}

const detailTemplateForSummary = (source: string, label: string): string => {
  const template = parseSfc(source).descriptor.template?.content ?? ''
  const escapedLabel = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return template.match(new RegExp(`<details\\b[^>]*>[\\s\\S]*?<summary[^>]*>\\s*${escapedLabel}\\s*</summary>([\\s\\S]*?)</details>`))?.[0] ?? ''
}

const detailRendersDataNames = (source: string, label: string, names: readonly string[]): boolean => {
  const detail = detailTemplateForSummary(source, label)
  const usesBoundData = names.some(name => new RegExp(`(?:\\{\\{[^}]*\\b${name}\\b|(?:v-for|v-if|v-else-if|:[\\w-]+)\\s*=\\s*['"][^'"]*\\b${name}\\b)`).test(detail))
  return usesBoundData
    && /当前会话/.test(detail)
    && !/(?:请在右侧|当前会话未提供|未提供可展示的)/.test(detail)
}

const nextActionNamesDerivedFromEvents = (source: string): string[] =>
  [...source.matchAll(/const\s+([A-Za-z_$]\w*(?:next|action)\w*)\s*(?:\:\s*[^=;\r\n]+)?=\s*computed/gi)]
    .map(match => match[1])
    .filter(name => declarationFor(source, name).includes('agentStore.events'))

const assistantKeepsThreeColumnsAt1440 = (source: string): boolean => {
  const breakpoint = source.match(/@media\s*\(max-width:\s*1480px\)[\s\S]{0,900}?\.assistant\s*\{[^}]*grid-template-columns\s*:\s*([^;}]+)[;}]/)?.[1] ?? ''
  const hasThreeTracks = /repeat\(\s*3\s*,/.test(breakpoint) || (breakpoint.match(/minmax\(/g) ?? []).length === 3
  const narrowCollapse = [...source.matchAll(/@media\s*\(max-width:\s*(\d+)px\)\s*\{\s*\.assistant\s*\{[^}]*grid-template-columns\s*:\s*(?:1fr|minmax\(0,\s*1fr\))/g)]
    .some(([, width]) => Number(width) < 1480)
  return hasThreeTracks && narrowCollapse
}

const agentCenterUsesLatestRealRoleEvents = (source: string): boolean => {
  const exactEventName = /(?:event|item)\.(?:label|detail)\.includes\(\s*(?:definition|role)\.name\s*\)/.test(source)
  const messageName = /(?:message|item)\.content\.includes\(\s*(?:definition|role)\.name\s*\)/.test(source)
  const latestEvent = /(?:\[\.\.\.agentStore\.events\]|agentStore\.events\.filter)[\s\S]{0,1200}(?:\.reverse\(\)\s*\.find|\.toReversed\(\)\s*\.find|\.sort\([\s\S]{0,320}timestamp[\s\S]{0,320}\)\s*\[\s*0\s*\]|Math\.max[\s\S]{0,320}timestamp)/.test(source)
  return exactEventName && messageName && latestEvent
}

const agentCenterLeavesMissingRoleStatusUnknown = (source: string): boolean =>
  !/\bstatus\s*:\s*['"](?:idle|pending|running|completed|error)['"]/.test(source)
  && /\bstatus\s*:\s*[A-Za-z_$]\w*\?\.status/.test(source)
  && /\bdataAvailable\s*:\s*Boolean\(\s*[A-Za-z_$]\w*(?:\s*\|\|\s*[A-Za-z_$]\w*)?\s*\)/.test(source)

const componentOpeningTag = (source: string, component: string): string =>
  source.match(new RegExp(`<${component}\\b[\\s\\S]{0,1200}?>`))?.[0] ?? ''

const componentBindsProp = (source: string, component: string, prop: string): boolean => {
  const tag = componentOpeningTag(source, component)
  return new RegExp(`(?::${prop}|v-bind:${prop})\\s*=`).test(tag)
    || new RegExp(`v-bind\\s*=\\s*['"][^'"]*\\b${prop}\\b`).test(tag)
}

const componentDoesNotBindEmptyArray = (source: string, component: string, prop: string): boolean => {
  const tag = componentOpeningTag(source, component)
  return !new RegExp(`(?::${prop}|v-bind:${prop})\\s*=\\s*['"]\\[\\]`).test(tag)
}

const componentOpeningTags = (source: string, component: string): string[] =>
  [...source.matchAll(new RegExp(`<${component}\\b[\\s\\S]{0,1200}?(?:/>|>)`, 'g'))].map(match => match[0])

const computedNamesDerivedFrom = (source: string, storeField: string): string[] => {
  const declarations = [...source.matchAll(/const\s+([A-Za-z_$]\w*)\s*(?:\:\s*[^=;\r\n]+)?=\s*computed(?:<[^>]{0,240}>)?\s*\(([\s\S]*?)\)\s*;?\s*(?=\r?\n\s*(?:const|let|function|async|onMounted|<\/script)|$)/g)]
  return declarations
    .filter(([, , expression]) => expression.includes(`agentStore.${storeField}`))
    .map(([, name]) => name)
}

const tagBindsNamedProp = (tag: string, prop: string, names: readonly string[]): boolean =>
  names.some(name =>
    new RegExp(`(?::${prop}|v-bind:${prop})\\s*=\\s*['"]${name}['"]`).test(tag)
    || new RegExp(`v-bind\\s*=\\s*['"][^'"]*\\b${prop}\\s*:\\s*${name}\\b`).test(tag)
  )

const componentBindsComputedStoreField = (
  source: string,
  component: string,
  prop: string,
  storeField: string
): boolean => {
  const names = computedNamesDerivedFrom(source, storeField)
  return names.length > 0 && componentOpeningTags(source, component).some(tag => tagBindsNamedProp(tag, prop, names))
}

interface AgentCardLoop {
  tag: string
  item: string
  collection: string
}

const agentCardLoops = (source: string): AgentCardLoop[] =>
  componentOpeningTags(source, 'AgentWorkspaceCard').flatMap(tag => {
    const match = tag.match(/v-for\s*=\s*['"]\s*([A-Za-z_$]\w*)\s+(?:in|of)\s+([A-Za-z_$]\w*)\s*['"]/)
    return match ? [{ tag, item: match[1], collection: match[2] }] : []
  })

const declarationFor = (source: string, name: string): string =>
  source.match(new RegExp(`const\\s+${name}\\s*(?:\\:\\s*[^=;\\r\\n]+)?=\\s*[\\s\\S]{0,5000}?(?=\\r?\\n\\s*(?:const|let|function|async|onMounted|<\\/script)|$)`))?.[0] ?? ''

const nameValuesIn = (source: string): string[] =>
  [...source.matchAll(/\bname\s*:\s*['"]([^'"]*智能体)['"]/g)].map(match => match[1])

const fixedRoleValuesIn = (source: string): string[] =>
  [...source.matchAll(/['"](文献智能体|实验智能体|分析智能体|写作智能体|审稿智能体)['"]/g)]
    .map(match => match[1])

const hasExactlyFiveFixedRoleValues = (values: readonly string[]): boolean =>
  values.length === FIXED_AGENT_ROLES.length
  && new Set(values).size === FIXED_AGENT_ROLES.length
  && FIXED_AGENT_ROLES.every(role => values.includes(role))

const isDirectFixedRoleDefinition = (definition: string): boolean =>
  hasExactlyFiveFixedRoleValues(nameValuesIn(definition))
  || hasExactlyFiveFixedRoleValues(fixedRoleValuesIn(definition))

const fixedRoleDefinitionNames = (source: string): string[] =>
  [...source.matchAll(/const\s+([A-Za-z_$]\w*)\s*(?:\:\s*[^=;\r\n]+)?=\s*[\s\S]{0,5000}?(?=\r?\n\s*(?:const|let|function|async|onMounted|<\/script)|$)/g)]
    .map(match => match[1])
    .filter(name => isDirectFixedRoleDefinition(declarationFor(source, name)))

const loopConnectsToExactlyFiveFixedRoles = (source: string): boolean =>
  agentCardLoops(source).some(({ collection }) => {
    const declaration = declarationFor(source, collection)
    const directMatch = isDirectFixedRoleDefinition(declaration)
    const transitiveMatch = fixedRoleDefinitionNames(source)
      .some(name => new RegExp(`\\b${name}\\b`).test(declaration))
    const objectNames = nameValuesIn(source)
    return (directMatch || transitiveMatch)
      && (objectNames.length === 0 || hasExactlyFiveFixedRoleValues(objectNames))
  })

const loopForwardsRoleCardFields = (source: string): boolean =>
  agentCardLoops(source).some(({ tag, item, collection }) => {
    const declaration = declarationFor(source, collection)
    const fields = ['name', 'role', 'status', 'currentTask', 'queue', 'dataAvailable']
    const forwardsExplicitly = fields.every(prop =>
      new RegExp(`(?::${prop}|v-bind:${prop})\\s*=\\s*['"]${item}\\.${prop}['"]`).test(tag)
    )
    const forwardsWholeCard = new RegExp(`v-bind\\s*=\\s*['"]${item}['"]`).test(tag)
      && fields.every(field => new RegExp(`\\b${field}\\s*:`).test(declaration))
    const nameRoleFromCurrentItem = ['name', 'role'].every(prop =>
      new RegExp(`(?::${prop}|v-bind:${prop})\\s*=\\s*['"]${item}['"]`).test(tag)
    )
    const explicitlyUnavailable = /(?::dataAvailable|:data-available|v-bind:dataAvailable)\s*=\s*['"]false['"]/.test(tag)
    const dataAvailableFromCurrentItem = new RegExp(`(?::dataAvailable|:data-available|v-bind:dataAvailable)\\s*=\\s*['"]${item}\\.dataAvailable['"]`).test(tag)
    const spreadsCurrentItem = new RegExp(`v-bind\\s*=\\s*['"]${item}['"]`).test(tag)
    const itemIsExplicitlyUnavailable = explicitlyUnavailable
      || ((dataAvailableFromCurrentItem || spreadsCurrentItem) && /\bdataAvailable\s*:\s*false\b/.test(declaration))
    const hasStaticUnavailableDetail = ['status', 'currentTask', 'current-task', 'queue'].some(prop =>
      new RegExp(`(?::${prop}|v-bind:${prop})\\s*=\\s*['"]\\s*(?:['"][^'"]+['"]|\\d+|true|false)`).test(tag)
    )
    const unavailableNameRoleForwarding = (nameRoleFromCurrentItem && (explicitlyUnavailable || dataAvailableFromCurrentItem))
      || (spreadsCurrentItem && ['name', 'role', 'dataAvailable'].every(field => new RegExp(`\\b${field}\\s*:`).test(declaration)))
    const forwardsUnavailableRole = itemIsExplicitlyUnavailable
      && unavailableNameRoleForwarding
      && !hasStaticUnavailableDetail
    return forwardsExplicitly || forwardsWholeCard || forwardsUnavailableRole
  })

const hasTemplateText = (source: string, text: string): boolean =>
  parseSfc(source).descriptor.template?.content.includes(text) ?? false

const templateElement = (source: string): HTMLElement => {
  const template = parseSfc(source).descriptor.template?.content ?? ''
  const host = document.createElement('section')
  host.innerHTML = template
  return host
}

const assistantTemplateElement = (): HTMLElement => templateElement(pageSource('Assistant.vue'))
const agentWorkspaceCardTemplateElement = (): HTMLElement => templateElement(componentSource('AgentWorkspaceCard.vue'))

const detailForSummary = (host: HTMLElement, label: string): HTMLDetailsElement | null =>
  [...host.querySelectorAll<HTMLDetailsElement>('details')]
    .find(detail => detail.querySelector('summary')?.textContent?.trim().includes(label)) ?? null

const interpolationLeafElements = (host: HTMLElement, field: string): HTMLElement[] => {
  const binding = new RegExp(`\\{\\{\\s*(?:props\\.)?${field}\\b`)
  return [...host.querySelectorAll<HTMLElement>('*')].filter(element =>
    binding.test(element.innerHTML)
    && ![...element.children].some(child => binding.test(child.innerHTML))
  )
}

const templateAncestors = (element: HTMLElement): HTMLElement[] => {
  const ancestors: HTMLElement[] = []
  for (let current: HTMLElement | null = element; current; current = current.parentElement) {
    ancestors.push(current)
  }
  return ancestors
}

const isDataAvailableTrueBranch = (expression: string | null): boolean =>
  expression !== null && /^\s*(?:props\.)?dataAvailable\s*(?:&&|$)/.test(expression)

const isVisibleWhenDataUnavailable = (element: HTMLElement): boolean =>
  templateAncestors(element).every(ancestor =>
    !['v-if', 'v-show', 'v-else-if'].some(attribute =>
      isDataAvailableTrueBranch(ancestor.getAttribute(attribute))
    )
  )

const hasFieldScopeLabel = (element: HTMLElement, label: string): boolean =>
  templateAncestors(element).some(scope =>
    [...scope.children].some(child => child.textContent?.trim() === label)
  )

const hasUnavailableFallbackForField = (host: HTMLElement, field: string, label: string): boolean =>
  interpolationLeafElements(host, field).some(element => {
    const inlineFallback = /待接入数据/.test(element.innerHTML)
      && /(?:props\.)?dataAvailable/.test(element.innerHTML)
    const availableBranch = templateAncestors(element).find(ancestor =>
      isDataAvailableTrueBranch(ancestor.getAttribute('v-if'))
    )
    const pairedFallback = availableBranch?.nextElementSibling
    return (inlineFallback && isVisibleWhenDataUnavailable(element) && hasFieldScopeLabel(element, label))
      || (pairedFallback?.hasAttribute('v-else') === true
        && /待接入数据/.test(pairedFallback.textContent)
        && isVisibleWhenDataUnavailable(pairedFallback)
        && hasFieldScopeLabel(pairedFallback, label))
  })

const FIXED_AGENT_ROLES = ['文献智能体', '实验智能体', '分析智能体', '写作智能体', '审稿智能体'] as const

const hasExactlyFiveUniqueFixedRoles = (source: string): boolean => {
  const objectRoleNames = nameValuesIn(source)
  return objectRoleNames.length > 0
    ? hasExactlyFiveFixedRoleValues(objectRoleNames)
    : fixedRoleDefinitionNames(source).length > 0
}

const importsNoStoreOrService = (source: string): boolean =>
  !/(?:stores|store)\//.test(source)
  && !/(?:services|service)\//.test(source)
  && !/\buse[A-Z]\w*Store\b/.test(source)
  && !/\b(?:defineStore|researchAgentService)\b/.test(source)

const agentWorkspaceStatusUnion = (source: string): string =>
  source.match(/type\s+AgentWorkspaceStatus\s*=\s*([\s\S]*?)(?=\r?\n\s*\r?\n|\r?\n\s*(?:const|interface|type|function)\b|$)/)?.[1] ?? ''

const agentWorkspaceCardRules: readonly SourceRule[] = [
  ['使用 defineProps 声明展示契约', source => source.includes('defineProps')],
  ['使用语义卡片根节点', source => /<article\b/.test(source)],
  ['声明 name prop', source => /\bname\s*:/.test(source)],
  ['声明 role prop', source => /\brole\s*:/.test(source)],
  ['声明 status prop', source => /\bstatus\s*:/.test(source)],
  ['声明 currentTask prop', source => /\bcurrentTask\s*\??\s*:/.test(source)],
  ['声明 queue prop', source => /\bqueue\s*\??\s*:/.test(source)],
  ['声明 dataAvailable prop', source => /\bdataAvailable\s*\??\s*:/.test(source)],
  ['name 为 string 展示字段', source => /\bname\s*:\s*string/.test(source)],
  ['role 为 string 展示字段', source => /\brole\s*:\s*string/.test(source)],
  ['status 为受限状态字段', source => /\bstatus\s*:\s*[^;\r\n]*(?:idle|pending|running|completed|error)/.test(source)],
  ['currentTask 保持可选，允许真实数据缺失', source => /\bcurrentTask\s*\?\s*:/.test(source)],
  ['queue 保持可选，允许真实数据缺失', source => /\bqueue\s*\?\s*:/.test(source)],
  ['dataAvailable 保持可选布尔字段', source => /\bdataAvailable\s*\?\s*:\s*boolean/.test(source)],
  ['dataAvailable 默认值为 false', source => /dataAvailable\s*:\s*false|withDefaults[\s\S]{0,240}dataAvailable[\s\S]{0,80}false/.test(source)],
  ['显示 Agent 标签', source => source.includes('Agent')],
  ['渲染 name', source => /\{\{\s*(?:props\.)?name\s*\}\}/.test(source)],
  ['显示角色标签', source => source.includes('角色')],
  ['渲染 role', source => /\{\{\s*(?:props\.)?role\s*\}\}/.test(source)],
  ['显示状态标签', source => source.includes('状态')],
  ['渲染 status', source => /\{\{\s*(?:props\.)?status\s*\}\}/.test(source)],
  ['显示当前任务标签', source => source.includes('当前任务')],
  ['渲染 currentTask', source => /\{\{\s*(?:props\.)?currentTask/.test(source)],
  ['显示队列标签', source => source.includes('队列')],
  ['渲染 queue', source => /\{\{\s*(?:props\.)?queue/.test(source)],
  ['以 dataAvailable 控制数据可用分支', source => /v-if\s*=\s*"(?:props\.)?dataAvailable"|v-if\s*=\s*"!(?:props\.)?dataAvailable"/.test(source)],
  ['dataAvailable=false 显示待接入数据', source => /dataAvailable[\s\S]{0,480}待接入数据|待接入数据[\s\S]{0,480}dataAvailable/.test(source)],
  ['待接入数据使用中文文案', source => source.includes('待接入数据')],
  ['数据缺失时不把队列伪造为数字', source => !/queue\s*:\s*\d+/.test(source)],
  ['状态样式由 status 真实字段驱动', source => /(?:props\.)?status/.test(source) && /:class/.test(source)],
  ['状态 union 精确为 pending/running/completed/error，且不含 idle', source => {
    const union = agentWorkspaceStatusUnion(source)
    const values = [...union.matchAll(/['"]([^'"]+)['"]/g)].map(match => match[1])
    return values.length === 4
      && new Set(values).size === 4
      && ['pending', 'running', 'completed', 'error'].every(status => values.includes(status))
      && !values.includes('idle')
  }],
  ['name 在语义标题中展示', source => /<h[2-4]\b[^>]*>[\s\S]{0,160}\{\{\s*(?:props\.)?name\s*\}\}/.test(source)],
  ['角色在语义 definition-list 字段中展示', source => /<dt>\s*角色\s*<\/dt>[\s\S]{0,240}<dd\b[^>]*>[\s\S]{0,160}\{\{\s*(?:props\.)?role\s*\}\}/.test(source)],
  ['当前任务在语义 definition-list 字段中展示', source => /<dt>\s*当前任务\s*<\/dt>[\s\S]{0,240}<dd\b/.test(source)],
  ['队列在语义 definition-list 字段中展示', source => /<dt>\s*队列\s*<\/dt>[\s\S]{0,240}<dd\b/.test(source)],
  ['不导入 Pinia', source => !/from\s+['"]pinia['"]/.test(source)],
  ['不声明 Pinia Store', source => !/\bdefineStore\b/.test(source)],
  ['不导入任何 Store 路径', source => !/(?:stores|store)\//.test(source)],
  ['不调用 useXxxStore', source => !/\buse[A-Z]\w*Store\b/.test(source)],
  ['不导入任何 service 路径', source => !/(?:services|service)\//.test(source)],
  ['不直接调用 researchAgentService', source => !/\bresearchAgentService\b/.test(source)],
  ['全部展示依赖只来自 props', importsNoStoreOrService],
  ['使用语义 article 容器', source => /<article\b/.test(source)],
  ['根节点提供 aria-label', source => /<article\b[^>]*aria-label=/.test(source)],
  ['数据不可用状态有 status 语义', source => source.includes('role="status"')],
  ['数据不可用状态使用 polite live region', source => source.includes('aria-live="polite"')],
  ['状态装饰不重复播报', source => source.includes('aria-hidden="true"')],
  ['可交互元素提供 focus-visible', source => source.includes(':focus-visible')],
  ['焦点使用研究系统 focus token', source => source.includes('--research-shadow-focus')],
  ['动效支持 prefers-reduced-motion', source => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['reduced-motion 下关闭动画', source => /prefers-reduced-motion:\s*reduce[\s\S]{0,320}animation:\s*none/.test(source)],
  ['卡片布局有 min-width: 0', source => /min-width:\s*0/.test(source)],
  ['信息行可收缩以免横向溢出', source => /min-width:\s*0/.test(source)],
  ['长任务文本允许断词', source => /overflow-wrap:\s*anywhere|word-break:\s*break-word/.test(source)],
  ['布局网格轨道允许收缩', source => source.includes('minmax(0,')],
  ['不以固定 1440 宽度实现布局', source => !/width:\s*1440px/.test(source)],
  ['不以固定 1920 宽度实现布局', source => !/width:\s*1920px/.test(source)],
  ['卡片标题使用 heading', source => /<h[2-4]\b/.test(source)],
  ['队列值有可访问名称', source => /queue[\s\S]{0,220}aria-label|aria-label[\s\S]{0,220}queue/.test(source)],
  ['状态值有可访问名称', source => /status[\s\S]{0,220}aria-label|aria-label[\s\S]{0,220}status/.test(source)],
  ['当前任务为空时呈现真实缺失态', source => /currentTask[\s\S]{0,220}(?:暂无|待接入数据|—)/.test(source)],
  ['队列为空时呈现真实缺失态', source => /queue[\s\S]{0,220}(?:暂无|待接入数据|—)/.test(source)],
  ['不内置假任务文本', source => !/currentTask\s*:\s*['"]/.test(source)],
  ['不内置假角色文本', source => !/role\s*:\s*['"]/.test(source)],
  ['不内置假状态文本', source => !/status\s*:\s*['"](?:运行中|已完成|空闲)/.test(source)],
  ['卡片使用研究设计令牌', source => source.includes('var(--research-')],
  ['保持角色与状态的分离字段', source => /\brole\b/.test(source) && /\bstatus\b/.test(source)],
  ['保持当前任务与队列的分离字段', source => /\bcurrentTask\b/.test(source) && /\bqueue\b/.test(source)],
  ['不依赖全局窗口数据', source => !/\bwindow\.(?:agent|research)/.test(source)],
  ['不通过网络请求构造展示数据', source => !/\b(?:fetch|axios)\s*\(/.test(source)],
  ['状态显示不依赖事件类型推断', source => !/\bevent\.type\b/.test(source)],
  ['角色显示不依赖事件类型推断', source => !/\bevent\.type\b/.test(source)],
  ['组件保留 scoped 样式隔离', source => /<style\s+scoped/.test(source)]
]

const toolExecutionPanelRules: readonly SourceRule[] = [
  ['使用 defineProps 声明展示契约', source => source.includes('defineProps')],
  ['使用语义面板根节点', source => /<(?:section|article)\b/.test(source)],
  ['声明 executions prop', source => /\bexecutions\s*\??\s*:/.test(source)],
  ['executions 是可选列表并默认空数组', source => /\bexecutions\s*\?\s*:\s*[^;\r\n]*\[\]/.test(source)
    && /withDefaults[\s\S]{0,480}\bexecutions\s*:\s*\(\s*\)\s*=>\s*\[\]/.test(source)],
  ['定义工具执行条目接口', source => /interface\s+\w*(?:Execution|Tool)/.test(source)],
  ['执行条目包含必填 id 与可选 agent 字段', source => /\bid\s*:\s*(?:string|number)/.test(source) && /\bagent\s*\?\s*:/.test(source)],
  ['执行条目包含必填 tool 字段', source => /\btool\s*:\s*string/.test(source)],
  ['执行条目包含 stage 字段且不残留 phase', source => /\bstage\s*\??\s*:/.test(source) && !/\bphase\b/.test(source)],
  ['执行条目包含 duration 字段', source => /\bduration\s*\??\s*:/.test(source)],
  ['执行条目包含既有真实状态 union', source => /\bstatus\s*:\s*['"]running['"]\s*\|\s*['"]completed['"]\s*\|\s*['"]error['"]/.test(source)],
  ['执行条目包含 output 字段', source => /\boutput\s*\??\s*:/.test(source)],
  ['agent 为可展示文本', source => /\bagent\s*\??\s*:\s*string/.test(source)],
  ['tool 为必填展示文本', source => /\btool\s*:\s*string/.test(source)],
  ['stage 为可展示文本', source => /\bstage\s*\??\s*:\s*string/.test(source)],
  ['duration 保持可选以避免伪造', source => /\bduration\s*\?\s*:/.test(source)],
  ['status 为必填真实状态 union', source => /\bstatus\s*:\s*['"]running['"]\s*\|\s*['"]completed['"]\s*\|\s*['"]error['"]/.test(source)],
  ['output 保持可选以表达未返回输出', source => /\boutput\s*\?\s*:/.test(source)],
  ['显示 Agent 标签', source => source.includes('Agent')],
  ['渲染 agent', source => /\{\{\s*execution\.agent/.test(source)],
  ['显示工具标签', source => source.includes('工具')],
  ['渲染 tool', source => /\{\{\s*execution\.tool/.test(source)],
  ['显示阶段标签', source => source.includes('阶段')],
  ['渲染 stage', source => /\{\{\s*execution\.stage/.test(source)],
  ['显示耗时标签', source => source.includes('耗时')],
  ['渲染 duration', source => /\{\{\s*execution\.duration/.test(source)],
  ['缺失 duration 显示暂无耗时数据', source => /duration[\s\S]{0,220}暂无耗时数据/.test(source)],
  ['显示状态标签', source => source.includes('状态')],
  ['状态展示使用中文映射', source => /toolStatusLabel\(execution\.status\)/.test(source)],
  ['显示输出标签', source => source.includes('输出')],
  ['渲染 output', source => /\{\{\s*execution\.output/.test(source)],
  ['输出缺失时呈现真实缺失态', source => /output[\s\S]{0,220}(?:暂无输出|暂无工具输出|待接入数据|—)/.test(source)],
  ['按 executions 真实列表循环，并为重复记录使用索引回退的唯一 key', toolExecutionLoopUsesUniqueIndexKey],
  ['空列表有中文空状态', source => /executions\.length\s*===?\s*0[\s\S]{0,260}(?:暂无工具执行记录|暂无工具执行|待接入数据)/.test(source)],
  ['空状态使用 role=status', source => source.includes('role="status"')],
  ['空状态使用 polite live region', source => source.includes('aria-live="polite"')],
  ['不导入 Pinia', source => !/from\s+['"]pinia['"]/.test(source)],
  ['不声明 Pinia Store', source => !/\bdefineStore\b/.test(source)],
  ['不导入任何 Store 路径', source => !/(?:stores|store)\//.test(source)],
  ['不调用 useXxxStore', source => !/\buse[A-Z]\w*Store\b/.test(source)],
  ['不导入任何 service 路径', source => !/(?:services|service)\//.test(source)],
  ['不直接调用 researchAgentService', source => !/\bresearchAgentService\b/.test(source)],
  ['全部展示依赖只来自 props', importsNoStoreOrService],
  ['使用语义 section 或 article 容器', source => /<(?:section|article)\b/.test(source)],
  ['根节点提供 aria-label', source => /<(?:section|article)\b[^>]*aria-label=/.test(source)],
  ['执行列表具有 list 语义', source => /<(?:ol|ul)\b/.test(source)],
  ['工具状态具有可访问名称', source => /status[\s\S]{0,220}aria-label|aria-label[\s\S]{0,220}status/.test(source)],
  ['装饰图标不重复播报', source => source.includes('aria-hidden="true"')],
  ['可交互详情提供 focus-visible', source => source.includes(':focus-visible')],
  ['焦点使用研究系统 focus token', source => source.includes('--research-shadow-focus')],
  ['动效支持 prefers-reduced-motion', source => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['reduced-motion 下关闭动画', source => /prefers-reduced-motion:\s*reduce[\s\S]{0,320}animation:\s*none/.test(source)],
  ['面板布局有 min-width: 0', source => /min-width:\s*0/.test(source)],
  ['执行项可收缩以免横向溢出', source => /min-width:\s*0/.test(source)],
  ['长输出允许断词', source => /overflow-wrap:\s*anywhere|word-break:\s*break-word/.test(source)],
  ['布局网格轨道允许收缩', source => source.includes('minmax(0,')],
  ['耗时字段不写死为数字', source => !/duration\s*:\s*(?:\d+|['"]\d)/.test(source)],
  ['队列字段不被伪造到工具条目', source => !/\bqueue\s*:\s*\d+/.test(source)],
  ['状态由 execution.status 驱动', source => /execution\.status/.test(source)],
  ['不从 event type 推断工具名', source => !/\bevent\.type\b/.test(source)],
  ['不从 event type 推断 Agent', source => !/\bevent\.type\b/.test(source)],
  ['Agent 与工具字段保持分离', source => /\bagent\b/.test(source) && /\btool\b/.test(source)],
  ['stage 与状态字段保持分离', source => /\bstage\b/.test(source) && /\bstatus\b/.test(source)],
  ['耗时与输出字段保持分离', source => /\bduration\b/.test(source) && /\boutput\b/.test(source)],
  ['不依赖全局窗口数据', source => !/\bwindow\.(?:agent|research)/.test(source)],
  ['不通过网络请求构造展示数据', source => !/\b(?:fetch|axios)\s*\(/.test(source)],
  ['显示阶段不使用硬编码阶段数组', source => !/const\s+PHASES\s*=\s*\[/.test(source)],
  ['状态展示映射为中文且不直接输出内部状态码', source => source.includes('运行中')
    && source.includes('已完成')
    && source.includes('异常')
    && /toolStatusLabel\(execution\.status\)/.test(source)
    && !/\{\{\s*execution\.status\s*\}\}/.test(source)],
  ['不以内置假输出作为默认值', source => !/output\s*:\s*['"]/.test(source)],
  ['不以内置假 Agent 作为默认值', source => !/agent\s*:\s*['"]/.test(source)],
  ['不以内置假工具作为默认值', source => !/tool\s*:\s*['"]/.test(source)],
  ['面板使用研究设计令牌', source => source.includes('var(--research-')],
  ['卡片标题使用 heading', source => /<h[2-4]\b/.test(source)],
  ['不以固定 1440 宽度实现布局', source => !/width:\s*1440px/.test(source)],
  ['不以固定 1920 宽度实现布局', source => !/width:\s*1920px/.test(source)],
  ['组件保留 scoped 样式隔离', source => /<style\s+scoped/.test(source)]
]

const assistantRules: readonly SourceRule[] = [
  ['只导入 agent store', source => source.includes('useAgentStore') && source.includes('stores/research/agent.store')],
  ['禁止 project store', source => !/stores\/research\/project\.store|\buseProjectStore\b/.test(source)],
  ['禁止 workflow store', source => !/stores\/research\/workflow\.store|\buseWorkflowStore\b/.test(source)],
  ['禁止 experiment store', source => !/stores\/research\/experiment\.store|\buseExperimentStore\b/.test(source)],
  ['禁止 knowledge store', source => !/stores\/research\/knowledge\.store|\buseKnowledgeStore\b/.test(source)],
  ['精确只导入一个 Store 路径', source => (source.match(/from\s+['"][^'"]*stores\/[^'"]+['"]/g) ?? []).length === 1],
  ['具有命名的会话导航栏', source => /<aside\b[^>]*aria-label="[^"]*研究会话/.test(source)],
  ['具有命名的主工作区', source => /<section\b[^>]*aria-label="[^"]*(?:工作区|对话)/.test(source)],
  ['顶部具有命名的研究上下文栏', source => /<(?:section|aside)\b[^>]*class="[^"]*context-bar[^"]*"[^>]*aria-label="[^"]*研究上下文/.test(source)],
  ['研究上下文显示当前项目字段', source => hasTemplateText(source, '当前项目')],
  ['当前项目明确显示待接入数据', source => /当前项目[\s\S]{0,240}待接入数据|待接入数据[\s\S]{0,240}当前项目/.test(source)],
  ['研究模式由 activeSession 派生', source => /研究模式[\s\S]{0,480}agentStore\.activeSession|agentStore\.activeSession[\s\S]{0,480}研究模式/.test(source)],
  ['AI 状态由 isSending 或 isLoading 派生', source => /AI\s*状态[\s\S]{0,480}agentStore\.(?:isSending|isLoading)|agentStore\.(?:isSending|isLoading)[\s\S]{0,480}AI\s*状态/.test(source)],
  ['显示结论分区', source => source.includes('结论')],
  ['显示证据分区', source => source.includes('证据')],
  ['显示推理摘要分区', source => source.includes('推理摘要')],
  ['显示引用分区', source => source.includes('引用')],
  ['显示下一步行动分区', source => source.includes('下一步行动')],
  ['结论使用默认展开的 details', source => /<details\s+open(?:\s|>)/.test(source)],
  ['结论分区使用 summary', source => /<details\s+open[\s\S]{0,320}<summary[^>]*>[\s\S]{0,120}结论/.test(source)],
  ['证据分区使用 details', source => /<details[\s\S]{0,320}<summary[^>]*>[\s\S]{0,120}证据/.test(source)],
  ['推理摘要分区使用 details', source => /<details[\s\S]{0,320}<summary[^>]*>[\s\S]{0,120}推理摘要/.test(source)],
  ['引用分区使用 details', source => /<details[\s\S]{0,320}<summary[^>]*>[\s\S]{0,120}引用/.test(source)],
  ['下一步行动分区使用 details', source => /<details[\s\S]{0,320}<summary[^>]*>[\s\S]{0,120}下一步行动/.test(source)],
  ['证据分区展示真实 evidence 数据，不使用说明替代', source => detailRendersDataNames(source, '证据', ['evidence'])],
  ['推理摘要分区展示真实 events 数据，不使用说明替代', source => detailRendersDataNames(source, '推理摘要', ['events'])],
  ['引用分区展示真实 citations 数据，不使用说明替代', source => detailRendersDataNames(source, '引用', ['citations'])],
  ['下一步行动分区从真实 events 派生', source => {
    const names = nextActionNamesDerivedFromEvents(source)
    return names.length > 0 && detailRendersDataNames(source, '下一步行动', names)
  }],
  ['解析并引入 EvidencePanel', source => importsComponent(source, 'EvidencePanel', 'EvidencePanel.vue')],
  ['渲染 EvidencePanel', source => rendersComponent(source, 'EvidencePanel')],
  ['解析并引入 ResearchTimeline', source => importsComponent(source, 'ResearchTimeline', 'ResearchTimeline.vue')],
  ['渲染 ResearchTimeline', source => rendersComponent(source, 'ResearchTimeline')],
  ['解析并引入 AgentStatusPanel', source => importsComponent(source, 'AgentStatusPanel', 'AgentStatusPanel.vue')],
  ['渲染 AgentStatusPanel', source => rendersComponent(source, 'AgentStatusPanel')],
  ['解析并引入 ToolExecutionPanel', source => importsComponent(source, 'ToolExecutionPanel', 'ToolExecutionPanel.vue')],
  ['渲染 ToolExecutionPanel', source => rendersComponent(source, 'ToolExecutionPanel')],
  ['会话来自 agentStore.sessions', source => source.includes('agentStore.sessions')],
  ['消息来自 agentStore.messages', source => source.includes('agentStore.messages')],
  ['事件来自 agentStore.events', source => source.includes('agentStore.events')],
  ['引用来自 agentStore.citations', source => source.includes('agentStore.citations')],
  ['证据来自 agentStore.evidence', source => source.includes('agentStore.evidence')],
  ['EvidencePanel evidence 绑定同名 computed Store 派生数据', source => componentBindsComputedStoreField(source, 'EvidencePanel', 'evidence', 'evidence')],
  ['EvidencePanel citations 绑定同名 computed Store 派生数据', source => componentBindsComputedStoreField(source, 'EvidencePanel', 'citations', 'citations')],
  ['ResearchTimeline items 绑定同名 events computed 派生数据', source => componentBindsComputedStoreField(source, 'ResearchTimeline', 'items', 'events')],
  ['ToolExecutionPanel executions 绑定同名 messages/toolCalls computed 派生数据', source => {
    const names = computedNamesDerivedFrom(source, 'messages')
      .filter(name => declarationFor(source, name).includes('toolCalls'))
    return names.length > 0 && componentOpeningTags(source, 'ToolExecutionPanel')
      .some(tag => tagBindsNamedProp(tag, 'executions', names))
  }],
  ['AgentStatusPanel agents 绑定最新真实事件与消息命中角色', source => /\bcomputed[\s\S]{0,1600}(?:label|detail)[\s\S]{0,1600}(?:文献智能体|实验智能体|分析智能体|写作智能体|审稿智能体)/.test(source)
    && /\[\.\.\.agentStore\.events\]\.reverse\(\)\.find/.test(source)
    && /message\.content\.includes\(name\)/.test(source)
    && componentBindsProp(source, 'AgentStatusPanel', 'agents')],
  ['AgentStatusPanel 不从 event type 推断角色', source => !/\bevent\.type\b/.test(source)],
  ['加载状态可见', source => /(?:isLoading|sessionLoading)/.test(source) && source.includes('state="loading"')],
  ['空状态可见', source => source.includes('state="empty"')],
  ['错误状态可见', source => source.includes('state="error"')],
  ['加载失败提供 retry', source => /@retry\s*=\s*"(?:retry|load)/.test(source)],
  ['错误消息提供 retry', source => source.includes('retryMessage')],
  ['页面主区域有无障碍名称', source => /<(?:main|section|div)\b[^>]*aria-label=/.test(source)],
  ['会话列表有无障碍名称', source => source.includes('aria-label="研究会话列表"')],
  ['消息区域使用 polite live region', source => source.includes('aria-live="polite"')],
  ['可交互项提供 focus-visible', source => source.includes(':focus-visible')],
  ['折叠分区可获得键盘焦点', source => /details[\s\S]{0,360}summary/.test(source)],
  ['动效支持 prefers-reduced-motion', source => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['1440 宽屏有明确断点', source => source.includes('@media (max-width: 1480px)')],
  ['1920 宽屏有密度断点', source => source.includes('@media (min-width: 1720px)')],
  ['主栅格允许收缩', source => source.includes('minmax(0,')],
  ['主容器防止水平溢出', source => /overflow-x:\s*(?:clip|hidden)|overflow:\s*(?:clip|hidden)/.test(source)],
  ['1440 保持可收缩三栏，并仅在更窄屏折叠', assistantKeepsThreeColumnsAt1440],
  ['不伪造队列数据', source => !/\bqueue\s*:\s*\d+/.test(source)],
  ['不伪造耗时数据', source => !/\bduration\s*:\s*['"]?(?:\d|—)/.test(source)],
  ['不使用角色类型映射', source => !/\b(?:ROLE|MESSAGE_ROLE)_\w*\s*=\s*\{/.test(source)],
  ['不使用角色类型映射函数', source => !/\bfunction\s+messageRole\b/.test(source)],
  ['不使用事件类型到角色映射', source => !/\bEVENT_TYPE_LABELS\b|\beventLabel\b/.test(source)],
  ['不从 event.type 推断研究角色', source => !/\bevent\.type\b/.test(source)],
  ['不引入假研究模式数组', source => !/const\s+(?:RESEARCH_)?MODES\s*=\s*\[/.test(source)],
  ['页面使用研究设计令牌', source => source.includes('var(--research-')],
  ['页面保持 scoped 样式隔离', source => /<style\s+scoped/.test(source)]
]

const agentCenterRules: readonly SourceRule[] = [
  ['只导入 agent store', source => source.includes('useAgentStore') && source.includes('stores/research/agent.store')],
  ['禁止 workflow store', source => !/stores\/research\/workflow\.store|\buseWorkflowStore\b/.test(source)],
  ['禁止 project store', source => !/stores\/research\/project\.store|\buseProjectStore\b/.test(source)],
  ['禁止 experiment store', source => !/stores\/research\/experiment\.store|\buseExperimentStore\b/.test(source)],
  ['精确只导入一个 Store 路径', source => (source.match(/from\s+['"][^'"]*stores\/[^'"]+['"]/g) ?? []).length === 1],
  ['固定角色包含文献智能体', source => source.includes('文献智能体')],
  ['固定角色包含实验智能体', source => source.includes('实验智能体')],
  ['固定角色包含分析智能体', source => source.includes('分析智能体')],
  ['固定角色包含写作智能体', source => source.includes('写作智能体')],
  ['固定角色包含审稿智能体', source => source.includes('审稿智能体')],
  ['固定角色定义恰好五个且名称唯一', hasExactlyFiveUniqueFixedRoles],
  ['AgentWorkspaceCard v-for 连接到恰好五个固定角色定义', loopConnectsToExactlyFiveFixedRoles],
  ['解析并引入 AgentWorkspaceCard', source => importsComponent(source, 'AgentWorkspaceCard', 'AgentWorkspaceCard.vue')],
  ['AgentWorkspaceCard 绑定 name', source => componentBindsProp(source, 'AgentWorkspaceCard', 'name')],
  ['AgentWorkspaceCard 绑定 role', source => componentBindsProp(source, 'AgentWorkspaceCard', 'role')],
  ['AgentWorkspaceCard 传递 status/currentTask/queue/dataAvailable 未知处理', loopForwardsRoleCardFields],
  ['解析并引入 ResearchMetricPanel', source => importsComponent(source, 'ResearchMetricPanel', 'ResearchMetricPanel.vue')],
  ['渲染 ResearchMetricPanel', source => rendersComponent(source, 'ResearchMetricPanel')],
  ['解析并引入 ResearchTimeline', source => importsComponent(source, 'ResearchTimeline', 'ResearchTimeline.vue')],
  ['渲染 ResearchTimeline', source => rendersComponent(source, 'ResearchTimeline')],
  ['解析并引入 EvidencePanel', source => importsComponent(source, 'EvidencePanel', 'EvidencePanel.vue')],
  ['渲染 EvidencePanel', source => rendersComponent(source, 'EvidencePanel')],
  ['解析并引入 ToolExecutionPanel', source => importsComponent(source, 'ToolExecutionPanel', 'ToolExecutionPanel.vue')],
  ['渲染 ToolExecutionPanel', source => rendersComponent(source, 'ToolExecutionPanel')],
  ['未知角色显示待接入数据', source => source.includes('待接入数据')],
  ['角色匹配基于精确角色名且使用最新真实事件与消息', agentCenterUsesLatestRealRoleEvents],
  ['角色匹配不从 event type 推断', source => !/\bevent\.type\b/.test(source)],
  ['角色匹配不从任务 type 推断', source => !/\btask\.type\b/.test(source)],
  ['工具执行源自 messages', source => source.includes('agentStore.messages')],
  ['工具执行源自真实 toolCalls', source => source.includes('toolCalls')],
  ['工具执行不源自伪造数组', source => !/const\s+(?:toolExecutions|toolCalls)\s*=\s*\[/.test(source)],
  ['时间线源自 agentStore.events', source => source.includes('agentStore.events')],
  ['证据源自 agentStore.evidence', source => source.includes('agentStore.evidence')],
  ['引用源自 agentStore.citations', source => source.includes('agentStore.citations')],
  ['EvidencePanel evidence 绑定同名 computed Store 派生数据', source => componentBindsComputedStoreField(source, 'EvidencePanel', 'evidence', 'evidence')],
  ['EvidencePanel citations 绑定同名 computed Store 派生数据', source => componentBindsComputedStoreField(source, 'EvidencePanel', 'citations', 'citations')],
  ['ResearchTimeline items 绑定同名 events computed 派生数据', source => componentBindsComputedStoreField(source, 'ResearchTimeline', 'items', 'events')],
  ['ToolExecutionPanel executions 绑定同名 messages/toolCalls computed 派生数据', source => {
    const names = computedNamesDerivedFrom(source, 'messages')
      .filter(name => declarationFor(source, name).includes('toolCalls'))
    return names.length > 0 && componentOpeningTags(source, 'ToolExecutionPanel')
      .some(tag => tagBindsNamedProp(tag, 'executions', names))
  }],
  ['ResearchMetricPanel items 绑定同名 Store lengths computed 派生数据', source => {
    const names = computedNamesDerivedFrom(source, 'sessions')
      .concat(computedNamesDerivedFrom(source, 'messages'))
      .concat(computedNamesDerivedFrom(source, 'events'))
      .concat(computedNamesDerivedFrom(source, 'citations'))
      .concat(computedNamesDerivedFrom(source, 'evidence'))
      .filter(name => /agentStore\.(?:sessions|messages|events|citations|evidence)\.length/.test(declarationFor(source, name)))
    return names.length > 0 && componentOpeningTags(source, 'ResearchMetricPanel')
      .some(tag => tagBindsNamedProp(tag, 'items', names))
  }],
  ['共享组件不传空数组作为数据', source => ['ResearchMetricPanel', 'ResearchTimeline', 'EvidencePanel', 'ToolExecutionPanel']
    .every(component => ['items', 'evidence', 'citations', 'executions'].every(prop => componentDoesNotBindEmptyArray(source, component, prop)))],
  ['不伪造 queue', source => !/\bqueue\s*:\s*\d+/.test(source)],
  ['不伪造 duration', source => !/\bduration\s*:\s*['"]?(?:\d|—)/.test(source)],
  ['不在页面层计算或显示假耗时', source => !/\b(?:startedAt|completedAt)\b/.test(source)],
  ['不伪造 task', source => !/\btask\s*:\s*['"](?:等待任务|暂无任务|执行中)/.test(source)],
  ['不伪造 status', source => !/\bstatus\s*:\s*['"](?:idle|pending|running|completed|error)/.test(source)],
  ['消息命中时不伪造角色卡状态', agentCenterLeavesMissingRoleStatusUnknown],
  ['不以任务错误冒充结果', source => !/result:\s*task\?\.error/.test(source)],
  ['加载状态可见', source => source.includes('state="loading"')],
  ['空状态可见', source => source.includes('state="empty"')],
  ['错误状态可见', source => source.includes('state="error"')],
  ['会话加载失败提供 retry', source => source.includes('retry-session-load')],
  ['研究失败提供 retry', source => source.includes('retry-research')],
  ['重试按钮可由键盘聚焦', source => source.includes(':focus-visible')],
  ['错误区使用 alert 语义', source => source.includes('role="alert"')],
  ['动态状态使用 polite 或 assertive live region', source => /aria-live="(?:polite|assertive)"/.test(source)],
  ['面板区有可访问名称', source => /aria-label="(?:科研任务输入|Agent 中心|工具执行)/.test(source)],
  ['动效支持 prefers-reduced-motion', source => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['1440 宽屏有明确断点', source => source.includes('@media (max-width: 1480px)')],
  ['1920 宽屏有密度断点', source => source.includes('@media (min-width: 1720px)')],
  ['网格轨道允许收缩', source => source.includes('minmax(0,')],
  ['根区防止水平溢出', source => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['1440 宽屏的角色区可折叠', source => /@media\s*\(max-width:\s*1480px\)[\s\S]{0,900}grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/.test(source)],
  ['窄屏工具区可收为单列', source => /@media\s*\(max-width:\s*1050px\)[\s\S]{0,900}grid-template-columns:\s*minmax\(0,\s*1fr\)/.test(source)],
  ['不写死 1440 主宽度', source => !/width:\s*1440px/.test(source)],
  ['不写死 1920 主宽度', source => !/width:\s*1920px/.test(source)],
  ['使用研究设计令牌', source => source.includes('var(--research-')],
  ['页面保持 scoped 样式隔离', source => /<style\s+scoped/.test(source)],
  ['研究任务输入有 label', source => /<label[^>]*for="research-task-input"/.test(source)],
  ['运行按钮声明 busy 状态', source => source.includes(':aria-busy')],
  ['固定角色不映射为工作流事件类型', source => !/EVENT_TYPE_LABELS|WORKFLOW_AGENT_MAP/.test(source)],
  ['未知数据不显示假完成状态', source => !/待接入数据[\s\S]{0,120}已完成/.test(source)],
  ['研究会话从 agent store 加载', source => source.includes('agentStore.loadSessions')],
  ['Agent 卡片从五角色映射循环', source => /<AgentWorkspaceCard\b[^>]*v-for=/.test(source)]
]

describe('Phase 8-M0-B2：props-only 共享组件契约（150）', () => {
  it('AgentWorkspaceCard 生产组件文件存在', () => {
    expect(existsSync(componentPath('AgentWorkspaceCard.vue'))).toBe(true)
  })

  it.each(agentWorkspaceCardRules)('AgentWorkspaceCard %s', (_label, predicate) => {
    const source = componentSource('AgentWorkspaceCard.vue')
    expect(isMissingOr(source, predicate)).toBe(true)
  })

  it('ToolExecutionPanel 生产组件文件存在', () => {
    expect(existsSync(componentPath('ToolExecutionPanel.vue'))).toBe(true)
  })

  it.each(toolExecutionPanelRules)('ToolExecutionPanel %s', (_label, predicate) => {
    const source = componentSource('ToolExecutionPanel.vue')
    expect(isMissingOr(source, predicate)).toBe(true)
  })
})

describe('Phase 8-M0-B2：AgentWorkspaceCard 数据缺失回归契约', () => {
  it('真实 template 在 dataAvailable=false 时仍显示 role，并将状态、任务与队列降级为待接入数据', () => {
    const host = agentWorkspaceCardTemplateElement()

    const roleBindings = interpolationLeafElements(host, 'role')
    expect(roleBindings.some(isVisibleWhenDataUnavailable)).toBe(true)
    for (const [field, label] of Object.entries({ status: '状态', currentTask: '当前任务', queue: '队列' })) {
      expect(hasUnavailableFallbackForField(host, field, label)).toBe(true)
    }
  })

  it('状态 union 不含 idle 时，真实 template 与 scoped CSS 不残留 idle 状态规则', () => {
    const source = componentSource('AgentWorkspaceCard.vue')
    const statusUnion = agentWorkspaceStatusUnion(source)
    const templateAndStyles = [
      parseSfc(source).descriptor.template?.content ?? '',
      ...parseSfc(source).descriptor.styles.map(style => style.content)
    ].join('\n')

    expect(statusUnion).not.toMatch(/\bidle\b/)
    expect(templateAndStyles).not.toMatch(/\.is-idle\b|(?:props\.)?status\s*===\s*['"]idle['"]|statusLabels\s*\[\s*['"]idle['"]\s*\]/)
  })
})

describe('Phase 8-M0-B2：共享智能体状态的真实缺失态', () => {
  it('AgentStatusPanel 不将未知队列伪造为 0，而是显示待接入数据', () => {
    const source = componentSource('AgentStatusPanel.vue')
    expect(source).toContain("queue ?? '待接入数据'")
    expect(source).not.toContain('queue ?? 0')
  })
})

describe('Phase 8-M0-B2：Assistant 三栏研究工作台', () => {
  it('Assistant 页面文件存在', () => {
    expect(existsSync(pagePath('Assistant.vue'))).toBe(true)
  })

  it.each(assistantRules)('Assistant %s', (_label, predicate) => {
    expect(predicate(pageSource('Assistant.vue'))).toBe(true)
  })
})

describe('Phase 8-M0-B2：Assistant 真实模板 details DOM 契约', () => {
  it('真实 template 恰好输出五个可折叠分区及其语义 summary', () => {
    const host = assistantTemplateElement()
    const labels = ['结论', '证据', '推理摘要', '引用', '下一步行动']

    expect(host.querySelectorAll('details')).toHaveLength(5)
    for (const label of labels) {
      expect(detailForSummary(host, label)?.querySelector('summary')?.tagName).toBe('SUMMARY')
    }
  })

  it('真实 template 的结论分区默认展开', () => {
    const host = assistantTemplateElement()
    const conclusion = detailForSummary(host, '结论')

    expect(conclusion).not.toBeNull()
    expect(conclusion?.open).toBe(true)
  })

  it('真实 template 的其余四个分区默认折叠', () => {
    const host = assistantTemplateElement()

    for (const label of ['证据', '推理摘要', '引用', '下一步行动']) {
      const detail = detailForSummary(host, label)
      expect(detail).not.toBeNull()
      expect(detail?.open).toBe(false)
    }
  })

  it('真实 template 的 summary 是可聚焦的原生控件，接收 Enter/Space 并可点击切换', () => {
    const host = assistantTemplateElement()
    document.body.append(host)
    try {
      const conclusion = detailForSummary(host, '结论')
      expect(conclusion).not.toBeNull()
      const summary = conclusion?.querySelector('summary')
      expect(summary).not.toBeNull()
      if (!conclusion || !summary) return

      summary.focus()
      expect(document.activeElement).toBe(summary)
      for (const key of ['Enter', ' ']) {
        expect(summary.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))).toBe(true)
      }
      const wasOpen = conclusion.open
      summary.click()
      expect(conclusion.open).toBe(!wasOpen)
    } finally {
      host.remove()
    }
  })
})

describe('Phase 8-M0-B2：AgentCenter 五角色可观测中心', () => {
  it('AgentCenter 页面文件存在', () => {
    expect(existsSync(pagePath('AgentCenter.vue'))).toBe(true)
  })

  it.each(agentCenterRules)('AgentCenter %s', (_label, predicate) => {
    expect(predicate(pageSource('AgentCenter.vue'))).toBe(true)
  })
})

describe('Phase 8-M0-B2：红灯契约数量守卫', () => {
  it('共享组件恰有 150 个实际契约，且不少于 150', () => {
    const sharedComponentContractCount = 2 + agentWorkspaceCardRules.length + toolExecutionPanelRules.length

    expect(sharedComponentContractCount).toBe(150)
    expect(sharedComponentContractCount).toBeGreaterThanOrEqual(150)
  })

  it('注册的实际 Vitest 用例不少于 220 个', () => {
    const registeredCaseCount = 2
      + agentWorkspaceCardRules.length
      + toolExecutionPanelRules.length
      + 1
      + 1
      + 1
      + assistantRules.length
      + 4
      + 1
      + agentCenterRules.length
      + 2

    expect(registeredCaseCount).toBeGreaterThanOrEqual(301)
  })
})
