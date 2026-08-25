// @vitest-environment happy-dom
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Phase 8-M0-B3 red UI contracts.
 *
 * These contracts intentionally inspect the renderer boundary rather than
 * importing a Store into presentational components.  A missing future
 * component has one direct existence failure; its detailed contracts become
 * active as soon as the component is introduced.
 */
const desktopRoot = resolve(__dirname, '../..')
const rendererRoot = resolve(desktopRoot, 'src/renderer/src')
const researchRoot = resolve(rendererRoot, 'components/research')
const workspacePagePath = resolve(rendererRoot, 'pages/research/ResearchWorkspace.vue')
const controlPagePath = resolve(rendererRoot, 'pages/research/ExperimentControlCenter.vue')
const workspaceStorePath = resolve(desktopRoot, 'src/stores/research-workspace.store.ts')
const controlStorePath = resolve(desktopRoot, 'src/stores/experiment-control.store.ts')

const read = (path: string): string => readFileSync(path, 'utf8')
const componentPath = (fileName: string): string => resolve(researchRoot, fileName)
const component = (fileName: string): string => {
  const path = componentPath(fileName)
  return existsSync(path) ? read(path) : ''
}
const withoutComments = (source: string): string =>
  source.replace(/<!--[\s\S]*?-->|\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g, '')

type Predicate = (source: string) => boolean
type SourceContract = readonly [label: string, predicate: Predicate]

const workspace = (): string => withoutComments(read(workspacePagePath))
const control = (): string => withoutComments(read(controlPagePath))
const workspaceStore = (): string => withoutComments(read(workspaceStorePath))
const controlStore = (): string => withoutComments(read(controlStorePath))

const WORKSPACE_BOUNDARY: readonly SourceContract[] = [
  ['从 useResearchWorkspaceStore 读取唯一页面状态', (source) => source.includes('useResearchWorkspaceStore')],
  ['创建唯一的 ResearchWorkspace Store 实例', (source) => /const\s+store\s*=\s*useResearchWorkspaceStore\(\)/.test(source)],
  ['不导入 ResearchWorkspaceService', (source) => !source.includes('ResearchWorkspaceService')],
  ['不导入 workspace service 路径', (source) => !/(?:services|service)\/workspace/.test(source)],
  ['不调用 loadWorkspace 初始化演示项目', (source) => !source.includes('loadWorkspace(')],
  ['不在页面创建 ResearchWorkspace', (source) => !/new\s+ResearchWorkspace/.test(source)],
  ['不在 mounted 生命周期写入工作区', (source) => !source.includes('onMounted')],
  ['不写 demo-project', (source) => !source.includes('demo-project')],
  ['不写入固定的演示活动', (source) => !source.includes('智能体规划新实验')],
  ['不写入固定 O3-MNB 项目描述', (source) => !source.includes('O3-MNB 降解')],
  ['不在页面调用 store.setWorkspace', (source) => !source.includes('store.setWorkspace')],
  ['不在页面调用任何 setWorkspace(', (source) => !source.includes('setWorkspace(')],
  ['不在页面创建 ref 或 reactive 业务副本', (source) => !/\b(?:ref|reactive)\s*\(/.test(source)],
  ['不通过 $patch 写入本地工作区状态', (source) => !source.includes('$patch')],
  ['不直接赋值 store.workspace', (source) => !/store\.workspace\s*=/.test(source)],
  ['不直接赋值 store.activities', (source) => !/store\.activities\s*=/.test(source)],
  ['不以 workspace 字面量伪造业务状态', (source) => !/\bworkspace\s*:\s*(?:\{|\[)/.test(source)],
  ['不以 activities 字面量伪造业务状态', (source) => !/\bactivities\s*:\s*\[/.test(source)],
  ['不以 progress 字面量伪造业务状态', (source) => !/\bprogress\s*:\s*\{/.test(source)],
  ['不导入 Pinia defineStore', (source) => !source.includes('defineStore')],
  ['不把已加载数据替换为页面演示数据', (source) => !/activities\s*:\s*\[/.test(source)]
]

const WORKSPACE_FOCUS: readonly SourceContract[] = [
  ['以中文 aria-label 标识科研工作区', (source) => /aria-label="科研工作区/.test(source)],
  ['呈现项目名称标签', (source) => source.includes('项目名称')],
  ['呈现研究领域标签', (source) => source.includes('研究领域')],
  ['呈现研究目标标签', (source) => source.includes('研究目标')],
  ['呈现研究阶段标签', (source) => source.includes('研究阶段')],
  ['项目标题来自 store.overview', (source) => source.includes('store.overview')],
  ['领域来自 overview.domain', (source) => source.includes('overview?.domain')],
  ['目标来自 overview.description', (source) => source.includes('overview?.description')],
  ['阶段来自 overview.status', (source) => source.includes('overview?.status')],
  ['不根据百分比推断研究阶段', (source) => !/progressPercent[\s\S]{0,120}(?:阶段|phase)/.test(source)],
  ['不根据模块状态推断研究阶段', (source) => !/modules[\s\S]{0,120}(?:阶段|phase)/.test(source)],
  ['使用 ResearchPageHeader', (source) => source.includes('ResearchPageHeader')],
  ['使用 ResearchPanel 组织可观测区域', (source) => source.includes('ResearchPanel')],
  ['工作区标题可在没有项目时保持可用', (source) => source.includes('科研工作区')],
  ['项目焦点容器可收缩', (source) => source.includes('research-workspace__focus') && /min-width:\s*0/.test(source)],
  ['标题层级从 h1 开始', (source) => source.includes('<h1')],
  ['焦点区不把项目描述伪造为目标', (source) => !source.includes('微纳米气泡研究项目')],
  ['真实数据字段使用可选链降级', (source) => source.includes('?.')]
]

const WORKSPACE_PROGRESS: readonly SourceContract[] = [
  ['呈现总进度区域', (source) => source.includes('总进度')],
  ['总进度读取 progress.percent', (source) => source.includes('progress?.percent')],
  ['总进度具有 progressbar 语义', (source) => source.includes('role="progressbar"')],
  ['总进度声明最小值', (source) => source.includes('aria-valuemin="0"')],
  ['总进度声明最大值', (source) => source.includes('aria-valuemax="100"')],
  ['总进度声明当前值', (source) => source.includes(':aria-valuenow')],
  ['呈现任务进度标签', (source) => source.includes('任务进度')],
  ['任务进度读取 totalTasks', (source) => source.includes('totalTasks')],
  ['任务进度读取 completedTasks', (source) => source.includes('completedTasks')],
  ['呈现实验进度标签', (source) => source.includes('实验进度')],
  ['实验进度读取 totalExperiments', (source) => source.includes('totalExperiments')],
  ['实验进度读取 completedExperiments', (source) => source.includes('completedExperiments')],
  ['呈现论文进度标签', (source) => source.includes('论文进度')],
  ['论文进度读取 totalManuscripts', (source) => source.includes('totalManuscripts')],
  ['论文进度读取 publishedManuscripts', (source) => source.includes('publishedManuscripts')],
  ['呈现知识进度标签', (source) => source.includes('知识进度')],
  ['知识进度读取 totalKnowledge', (source) => source.includes('totalKnowledge')],
  ['知识进度读取 indexedKnowledge', (source) => source.includes('indexedKnowledge')],
  ['使用 ResearchMetricPanel 呈现真实汇总', (source) => source.includes('ResearchMetricPanel')],
  ['没有进度时显示中文进度空态', (source) => source.includes('暂无进度数据')]
]

const WORKSPACE_COMMAND: readonly SourceContract[] = [
  ['呈现真实研究里程碑', (source) => source.includes('研究里程碑')],
  ['里程碑以 progress 为唯一来源', (source) => source.includes(':progress="store.progress"')],
  ['使用 ResearchTimeline 呈现里程碑', (source) => source.includes('ResearchTimeline')],
  ['不在空进度时生成已完成结论', (source) => !source.includes('已完成全部研究')],
  ['呈现风险信号区域', (source) => source.includes('风险信号')],
  ['风险从 failed 模块状态读取', (source) => source.includes("status === 'failed'")],
  ['风险从 paused 模块状态读取', (source) => source.includes("status === 'paused'")],
  ['风险从 disabled 模块状态读取', (source) => source.includes("status === 'disabled'")],
  ['无风险时使用保守中文文案', (source) => source.includes('暂无风险信号')],
  ['不把暂无风险称为安全评估', (source) => !source.includes('系统安全')],
  ['呈现 AI 当前行动区域', (source) => source.includes('AI 当前行动')],
  ['AI 当前行动只筛选 agent 活动', (source) => source.includes("kind === 'agent'")],
  ['没有 agent 活动时显示中文空态', (source) => source.includes('暂无 AI 当前行动')],
  ['不写死 AI 任务标题', (source) => !source.includes('ExperimentAgent')],
  ['呈现模块入口区域', (source) => source.includes('模块入口')],
  ['模块入口遍历 store.modules', (source) => source.includes('store.modules')],
  ['模块入口为可聚焦 button 或 link', (source) => /<(?:button|a)\b/.test(source)],
  ['模块入口有中文 aria-label', (source) => /aria-label="(?:模块入口|打开模块)/.test(source)],
  ['没有模块时显示中文空态', (source) => source.includes('暂无科研模块')],
  ['模块入口使用 :focus-visible', (source) => source.includes(':focus-visible')]
]

const WORKSPACE_STATES: readonly SourceContract[] = [
  ['导入统一 ResearchState', (source) => source.includes('ResearchState')],
  ['加载时渲染 ResearchState loading', (source) => source.includes('state="loading"')],
  ['加载由 store.isLoading 驱动', (source) => source.includes('store.isLoading')],
  ['错误时渲染 ResearchState error', (source) => source.includes('state="error"')],
  ['错误由 store.errorMessage 驱动', (source) => source.includes('store.errorMessage')],
  ['错误状态包含中文重试语义', (source) => source.includes('重新加载') || source.includes('@retry')],
  ['空工作区渲染 ResearchState empty', (source) => source.includes('state="empty"')],
  ['空态由 !store.workspace 驱动', (source) => source.includes('!store.workspace')],
  ['加载、错误和空态不遮蔽已有真实工作区', (source) => source.includes('&& !store.workspace')],
  ['页面状态具有 live region 组件', (source) => source.includes('ResearchState')],
  ['不把错误降级为演示页面', (source) => !source.includes('控制中心已就绪')],
  ['工作区主体可在状态完成后显示', (source) => source.includes('v-else') || source.includes('v-if="store.workspace"')]
]

const WORKSPACE_LAYOUT: readonly SourceContract[] = [
  ['根容器阻止横向溢出', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['所有网格轨道允许收缩', (source) => source.includes('minmax(0,')],
  ['子网格使用 min-width: 0', (source) => /min-width:\s*0/.test(source)],
  ['1440 使用紧凑断点', (source) => source.includes('@media (max-width: 1480px)')],
  ['1440 断点使指挥区安全换行', (source) => /@media\s*\(max-width:\s*1480px\)[\s\S]*grid-template-columns:\s*1fr/.test(source)],
  ['1920 使用扩展密度断点', (source) => source.includes('@media (min-width: 1720px)')],
  ['1920 断点保持 minmax 网格', (source) => /@media\s*\(min-width:\s*1720px\)[\s\S]*minmax\(0,/.test(source)],
  ['不写死 1440 或 1920 宽度', (source) => !/width:\s*(?:1440|1920)px/.test(source)]
]

const CONTROL_PAGE: readonly SourceContract[] = [
  ['根节点使用 SCADA 主题', (source) => source.includes('data-research-theme="scada"')],
  ['根节点提供中文 SCADA aria-label', (source) => /aria-label="实验控制中心 SCADA"/.test(source)],
  ['从 useExperimentControlStore 读取页面状态', (source) => source.includes('useExperimentControlStore')],
  ['创建唯一的 ExperimentControl Store 实例', (source) => /const\s+store\s*=\s*useExperimentControlStore\(\)/.test(source)],
  ['不以对象字面量伪造局部 Store', (source) => !/const\s+store\s*=\s*\{/.test(source)],
  ['不声明 mock Store', (source) => !/\b(?:mockStore|localStore|fakeStore)\b/.test(source)],
  ['不直接导入 service', (source) => !/(?:services|service)\//.test(source)],
  ['不在页面调用 pushAlert', (source) => !source.includes('pushAlert')],
  ['不在页面使用 onMounted 伪造状态', (source) => !source.includes('onMounted')],
  ['不写控制中心已就绪默认报警', (source) => !source.includes('控制中心已就绪')],
  ['不传硬编码空预测数组', (source) => !source.includes(':predictions="[]"')],
  ['预测绑定真实 store.predictions', (source) => source.includes(':predictions="store.predictions"')],
  ['导入 SCADADeviceTopology', (source) => source.includes('SCADADeviceTopology')],
  ['渲染 SCADADeviceTopology', (source) => /<SCADADeviceTopology(?:\s|\/|>)/.test(source)],
  ['拓扑绑定真实 devices', (source) => source.includes(':devices="store.devices"')],
  ['导入 SCADAMetricGrid', (source) => source.includes('SCADAMetricGrid')],
  ['渲染 SCADAMetricGrid', (source) => /<SCADAMetricGrid(?:\s|\/|>)/.test(source)],
  ['指标网格绑定真实 metrics', (source) => source.includes(':metrics="store.metrics"')],
  ['导入 SCADAAlertPanel', (source) => source.includes('SCADAAlertPanel')],
  ['渲染 SCADAAlertPanel', (source) => /<SCADAAlertPanel(?:\s|\/|>)/.test(source)],
  ['报警面板绑定真实 alerts', (source) => source.includes(':alerts="store.alerts"')],
  ['导入共享 research PredictionPanel', (source) => source.includes('components/research/PredictionPanel.vue')],
  ['渲染预测面板', (source) => /<PredictionPanel(?:\s|\/|>)/.test(source)],
  ['导入 DeviceStatusPanel', (source) => source.includes('DeviceStatusPanel')],
  ['设备状态绑定真实 devices', (source) => source.includes('store.devices')],
  ['AI 建议绑定真实 recommendations', (source) => source.includes(':recommendations="store.recommendations"')],
  ['时间线绑定真实 timeline', (source) => source.includes(':entries="store.timeline"')],
  ['experimentStatus 由 dashboards 与 timeline 派生', (source) => /const\s+experimentStatus\s*=\s*computed[\s\S]{0,700}store\.dashboards[\s\S]{0,700}store\.timeline/.test(source)],
  ['runStatus 由 timeline 派生', (source) => /const\s+runStatus\s*=\s*computed[\s\S]{0,700}store\.timeline/.test(source)],
  ['实验状态渲染 experimentStatus', (source) => /\{\{\s*experimentStatus\s*\}\}/.test(source)],
  ['Run 状态渲染 runStatus', (source) => /\{\{\s*runStatus\s*\}\}/.test(source)],
  ['实验状态从 dashboards 或 timeline 读取', (source) => source.includes('store.dashboards') && source.includes('store.timeline')],
  ['呈现实验状态中文标签', (source) => source.includes('实验状态')],
  ['实验状态空态由 dashboards 与 timeline 同时为空驱动', (source) => /v-(?:if|else-if)\s*=\s*"(?=[^"]*store\.dashboards\.length\s*===\s*0)(?=[^"]*store\.timeline\.length\s*===\s*0)[^"]*"[\s\S]{0,360}暂无实验状态/.test(source)],
  ['呈现 Run 状态中文标签', (source) => source.includes('Run 状态')],
  ['Run 空态由 timeline 为空驱动', (source) => /v-(?:if|else-if)\s*=\s*"[^"]*store\.timeline\.length\s*===\s*0[^"]*"[\s\S]{0,360}暂无 Run 记录/.test(source)],
  ['没有设备时显示中文空态', (source) => source.includes('暂无设备接入数据')],
  ['没有实时指标时显示中文空态', (source) => source.includes('暂无实时指标')],
  ['没有报警时显示中文空态', (source) => source.includes('暂无报警')],
  ['没有 AI 建议时显示中文空态', (source) => source.includes('暂无 AI 建议')],
  ['没有预测时显示中文空态', (source) => source.includes('暂无数字孪生预测')],
  ['不伪造实时指标字面量', (source) => !/metric\s*:\s*['"]/.test(source)],
  ['不伪造设备字面量', (source) => !/deviceId\s*:\s*['"]/.test(source)],
  ['不伪造 AI 建议字面量', (source) => !/recommendations\s*:\s*\[/.test(source)],
  ['不伪造实验时间线字面量', (source) => !/timeline\s*:\s*\[/.test(source)],
  ['SCADA 主视图使用可收缩网格', (source) => source.includes('minmax(0,')],
  ['控制中心根容器阻止横向溢出', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['控制中心子项可收缩', (source) => /min-width:\s*0/.test(source)],
  ['控制中心在 1440 紧凑换行', (source) => source.includes('@media (max-width: 1480px)')],
  ['控制中心在 1920 扩展主视图', (source) => source.includes('@media (min-width: 1720px)')],
  ['控制中心不写死 1440 或 1920 宽度', (source) => !/width:\s*(?:1440|1920)px/.test(source)],
  ['控制中心可聚焦操作具有 :focus-visible', (source) => source.includes(':focus-visible')],
  ['SCADA 动效在 reduced motion 下停用', (source) => source.includes('@media (prefers-reduced-motion: reduce)')]
]

const CONTROL_STORE: readonly SourceContract[] = [
  ['Store 导入 TwinPrediction 类型', (source) => source.includes('TwinPrediction')],
  ['Store 声明 predictions 集合', (source) => /predictions:\s*\[\]\s+as\s+TwinPrediction\[\]/.test(source)],
  ['Store 声明 setPredictions', (source) => source.includes('setPredictions')],
  ['setPredictions 接收 TwinPrediction[]', (source) => /setPredictions\(predictions:\s*TwinPrediction\[\]\)/.test(source)],
  ['Store 声明 addPrediction', (source) => source.includes('addPrediction')],
  ['addPrediction 接收 TwinPrediction', (source) => /addPrediction\(prediction:\s*TwinPrediction\)/.test(source)],
  ['reset 清理 predictions', (source) => /reset\(\)[\s\S]*this\.predictions\s*=\s*\[\]/.test(source)],
  ['预测集合只存 Store 数据而非页面字面量', (source) => !source.includes('预测演示')],
  ['Store 保留 devices 边界', (source) => source.includes('devices: [] as DeviceStatusPanel[]')],
  ['Store 保留 metrics 边界', (source) => source.includes('metrics: [] as RealtimeMetric[]')],
  ['Store 保留 alerts 边界', (source) => source.includes('alerts: [] as')],
  ['Store 保留 recommendations 边界', (source) => source.includes('recommendations: [] as AIRecommendation[]')]
]

interface TwinPanelContract {
  readonly name: string
  readonly fileName: string
  readonly optionalProp: string
  readonly plural: boolean
  readonly fields: readonly string[]
}

const TWIN_PANELS: readonly TwinPanelContract[] = [
  { name: 'ReactorTwinPanel', fileName: 'digital-twin/ReactorTwinPanel.vue', optionalProp: 'device', plural: false, fields: ['name', 'status', 'recentReadings', '反应器', '暂无反应器设备'] },
  { name: 'PumpTwinPanel', fileName: 'digital-twin/PumpTwinPanel.vue', optionalProp: 'device', plural: false, fields: ['name', 'status', 'recentReadings', '泵', '暂无泵设备'] },
  { name: 'OzoneGeneratorTwinPanel', fileName: 'digital-twin/OzoneGeneratorTwinPanel.vue', optionalProp: 'device', plural: false, fields: ['name', 'status', 'recentReadings', '臭氧发生器', '暂无臭氧发生器设备'] },
  { name: 'SensorTwinPanel', fileName: 'digital-twin/SensorTwinPanel.vue', optionalProp: 'devices', plural: true, fields: ['name', 'status', 'recentReadings', '传感器', '暂无传感器设备'] }
]

const TWIN_COMMON: readonly SourceContract[] = [
  ['使用 defineProps 接收展示数据', (source) => source.includes('defineProps')],
  ['不导入 Pinia', (source) => !/from\s+['"]pinia['"]|defineStore/.test(source)],
  ['不导入任何 Store', (source) => !/(?:stores|store)\//.test(source)],
  ['不导入任何 service', (source) => !/(?:services|service)\//.test(source)],
  ['声明 DeviceStatusPanel 数据类型', (source) => source.includes('DeviceStatusPanel')],
  ['声明 ariaLabel prop', (source) => source.includes('ariaLabel')],
  ['根节点提供 aria-label', (source) => source.includes('aria-label')],
  ['中文空态使用 role=status', (source) => source.includes('role="status"')],
  ['保留原生键盘语义或明确键盘处理器', (source) => /<(?:button|details|summary)\b|@keydown(?:\.(?:enter|space))?=/.test(source)],
  ['交互元素具有 :focus-visible', (source) => source.includes(':focus-visible')],
  ['动效支持 prefers-reduced-motion', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['容器可以收缩', (source) => /min-width:\s*0/.test(source)],
  ['容器阻止横向溢出', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['1440 桌面紧凑布局', (source) => source.includes('@media (max-width: 1480px)')],
  ['1920 桌面扩展布局', (source) => source.includes('@media (min-width: 1720px)')],
  ['使用研究设计令牌', (source) => source.includes('var(--research-')]
]

const TOPOLOGY_MAPPING: readonly SourceContract[] = [
  ['SCADADeviceTopology 文件存在', () => existsSync(componentPath('SCADADeviceTopology.vue'))],
  ['拓扑使用 defineProps', (source) => source === '' || source.includes('defineProps')],
  ['拓扑不导入 Pinia', (source) => source === '' || !/from\s+['"]pinia['"]|defineStore/.test(source)],
  ['拓扑不导入 Store', (source) => source === '' || !/(?:stores|store)\//.test(source)],
  ['拓扑不导入 service', (source) => source === '' || !/(?:services|service)\//.test(source)],
  ['拓扑接收 devices prop', (source) => source === '' || source.includes('devices')],
  ['拓扑导入 ReactorTwinPanel', (source) => source === '' || source.includes('ReactorTwinPanel')],
  ['拓扑导入 PumpTwinPanel', (source) => source === '' || source.includes('PumpTwinPanel')],
  ['拓扑导入 OzoneGeneratorTwinPanel', (source) => source === '' || source.includes('OzoneGeneratorTwinPanel')],
  ['拓扑导入 SensorTwinPanel', (source) => source === '' || source.includes('SensorTwinPanel')],
  ['反应器按精确 reactor type 映射', (source) => source === '' || /device\.type\s*===\s*['"]reactor['"]/.test(source)],
  ['泵按精确 pump type 映射', (source) => source === '' || /device\.type\s*===\s*['"]pump['"]/.test(source)],
  ['臭氧发生器按精确 ozone-generator type 映射', (source) => source === '' || /device\.type\s*===\s*['"]ozone-generator['"]/.test(source)],
  ['传感器按精确 sensor type 映射', (source) => source === '' || /device\.type\s*===\s*['"]sensor['"]/.test(source)],
  ['不根据设备名称猜测类型', (source) => source === '' || !/device\.name\.(?:includes|match|toLowerCase)/.test(source)],
  ['没有设备时显示中文空态', (source) => source === '' || source.includes('暂无设备接入数据')]
]

const TOPOLOGY_BINDINGS: readonly SourceContract[] = [
  ['reactor：computed 从 props.devices.find 精确筛选并绑定 ReactorTwinPanel', (source) => source === '' || /const\s+reactor\s*=\s*computed[\s\S]{0,180}props\.devices\.find\([\s\S]{0,260}device\.type\s*===\s*['"]reactor['"][\s\S]{0,1200}<ReactorTwinPanel\b[^>]*:device\s*=\s*"reactor"/.test(source)],
  ['pump：computed 从 props.devices.find 精确筛选并绑定 PumpTwinPanel', (source) => source === '' || /const\s+pump\s*=\s*computed[\s\S]{0,180}props\.devices\.find\([\s\S]{0,260}device\.type\s*===\s*['"]pump['"][\s\S]{0,1200}<PumpTwinPanel\b[^>]*:device\s*=\s*"pump"/.test(source)],
  ['ozoneGenerator：computed 从 props.devices.find 精确筛选并绑定 OzoneGeneratorTwinPanel', (source) => source === '' || /const\s+ozoneGenerator\s*=\s*computed[\s\S]{0,180}props\.devices\.find\([\s\S]{0,260}device\.type\s*===\s*['"]ozone-generator['"][\s\S]{0,1200}<OzoneGeneratorTwinPanel\b[^>]*:device\s*=\s*"ozoneGenerator"/.test(source)],
  ['sensors：computed 从 props.devices.filter 精确筛选并绑定 SensorTwinPanel', (source) => source === '' || /const\s+sensors\s*=\s*computed[\s\S]{0,180}props\.devices\.filter\([\s\S]{0,260}device\.type\s*===\s*['"]sensor['"][\s\S]{0,1200}<SensorTwinPanel\b[^>]*:devices\s*=\s*"sensors"/.test(source)]
]

const SCADA_COMPONENTS = [
  ['SCADAMetricGrid', 'SCADAMetricGrid.vue', '暂无实时指标'],
  ['SCADAAlertPanel', 'SCADAAlertPanel.vue', '暂无报警'],
  ['SCADADeviceTopology', 'SCADADeviceTopology.vue', '暂无设备接入数据']
] as const

const SCADA_COMMON: readonly SourceContract[] = [
  ['使用 defineProps 接收展示数据', (source) => source.includes('defineProps')],
  ['不导入 Pinia', (source) => !/from\s+['"]pinia['"]|defineStore/.test(source)],
  ['不导入任何 Store', (source) => !/(?:stores|store)\//.test(source)],
  ['不导入任何 service', (source) => !/(?:services|service)\//.test(source)],
  ['根节点提供 aria-label', (source) => source.includes('aria-label')],
  ['空态具有 role=status', (source) => source.includes('role="status"')],
  ['空态为中文', (source) => /暂无|尚未/.test(source)],
  ['保留原生键盘语义或明确键盘处理器', (source) => /<(?:button|details|summary)\b|@keydown(?:\.(?:enter|space))?=/.test(source)],
  ['可交互元素具有 :focus-visible', (source) => source.includes(':focus-visible')],
  ['动效支持 prefers-reduced-motion', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['容器可以收缩', (source) => /min-width:\s*0/.test(source)],
  ['容器阻止横向溢出', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['网格轨道允许收缩', (source) => source.includes('minmax(0,')],
  ['1440 桌面紧凑布局', (source) => source.includes('@media (max-width: 1480px)')],
  ['1920 桌面扩展布局', (source) => source.includes('@media (min-width: 1720px)')],
  ['使用研究 SCADA 令牌', (source) => source.includes('var(--research-')]
]

const METRIC_GRID: readonly SourceContract[] = [
  ['接收 RealtimeMetric[]', (source) => source.includes('RealtimeMetric')],
  ['声明 metrics prop', (source) => source.includes('metrics')],
  ['按 metric 名称分组', (source) => source.includes('.metric') && (source.includes('Map') || source.includes('reduce'))],
  ['渲染 SCADAChartPanel', (source) => source.includes('SCADAChartPanel')],
  ['向图表传递真实 metrics', (source) => source.includes(':metrics=')],
  ['向图表传递真实 metricName', (source) => source.includes(':metric-name=') || source.includes(':metricName=')],
  ['不写死图表实时数值', (source) => !/value\s*:\s*\d/.test(source)],
  ['呈现暂无实时指标', (source) => source.includes('暂无实时指标')],
  ['指标空态不称为系统在线', (source) => !source.includes('系统在线')],
  ['指标区域有中文 aria-label', (source) => /aria-label="实时指标/.test(source)],
  ['指标装饰元素 aria-hidden', (source) => source.includes('aria-hidden')],
  ['指标读数使用科学数字字体令牌', (source) => source.includes('--research-font-scientific')]
]

const ALERT_PANEL: readonly SourceContract[] = [
  ['声明 ControlAlert 展示类型', (source) => source.includes('ControlAlert')],
  ['声明 alerts prop', (source) => source.includes('alerts')],
  ['呈现 severity', (source) => source.includes('.severity')],
  ['呈现 message', (source) => source.includes('.message')],
  ['呈现 timestamp', (source) => source.includes('.timestamp')],
  ['不调用 pushAlert', (source) => !source.includes('pushAlert')],
  ['不写系统就绪默认报警', (source) => !source.includes('控制中心已就绪')],
  ['呈现暂无报警', (source) => source.includes('暂无报警')],
  ['报警区域有中文 aria-label', (source) => /aria-label="报警/.test(source)],
  ['严重报警具有语义等级', (source) => source.includes('critical')],
  ['报警装饰具有 aria-hidden', (source) => source.includes('aria-hidden')],
  ['报警动效使用研究运动令牌', (source) => source.includes('--research-duration-')]
]

const TOPOLOGY_DETAILS: readonly SourceContract[] = [
  ['根节点有中文拓扑 aria-label', (source) => source.includes('aria-label') && source.includes('数字孪生')],
  ['反应器面板接收真实 reactor', (source) => source.includes('<ReactorTwinPanel') && source.includes(':device=')],
  ['泵面板接收真实 pump', (source) => source.includes('<PumpTwinPanel') && source.includes(':device=')],
  ['臭氧发生器面板接收真实 ozone generator', (source) => source.includes('<OzoneGeneratorTwinPanel') && source.includes(':device=')],
  ['传感器面板接收真实 sensors', (source) => source.includes('<SensorTwinPanel') && source.includes(':devices=')],
  ['拓扑信号装饰具有 aria-hidden', (source) => source.includes('aria-hidden')],
  ['拓扑空态为暂无设备接入数据', (source) => source.includes('暂无设备接入数据')],
  ['拓扑不创建虚构设备', (source) => !/deviceId\s*:\s*['"]/.test(source)],
  ['拓扑使用 SCADA 网格令牌', (source) => source.includes('--research-scada-grid')],
  ['拓扑使用 reduced motion 降级', (source) => source.includes('@media (prefers-reduced-motion: reduce)')],
  ['拓扑 1440 时可换行', (source) => source.includes('@media (max-width: 1480px)')],
  ['拓扑 1920 时扩展布局', (source) => source.includes('@media (min-width: 1720px)')],
  ['拓扑阻止横向溢出', (source) => /overflow-x:\s*(?:clip|hidden)/.test(source)],
  ['拓扑不写死 1440 或 1920 宽度', (source) => !/width:\s*(?:1440|1920)px/.test(source)],
  ['拓扑使用 min-width 0', (source) => /min-width:\s*0/.test(source)]
]

describe('Phase 8-M0-B3：ResearchWorkspace 真实科研指挥中心（90）', () => {
  it.each(WORKSPACE_BOUNDARY)('ResearchWorkspace 数据边界：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
  it.each(WORKSPACE_FOCUS)('ResearchWorkspace 项目焦点：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
  it.each(WORKSPACE_PROGRESS)('ResearchWorkspace 真实进度：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
  it.each(WORKSPACE_COMMAND)('ResearchWorkspace 指挥区：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
  it.each(WORKSPACE_STATES)('ResearchWorkspace 状态：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
  it.each(WORKSPACE_LAYOUT)('ResearchWorkspace 响应式：%s', (_label, predicate) => {
    expect(predicate(workspace())).toBe(true)
  })
})

describe('Phase 8-M0-B3：ExperimentControlCenter SCADA 真实数据边界（58）', () => {
  it.each(CONTROL_PAGE)('ExperimentControlCenter：%s', (_label, predicate) => {
    expect(predicate(control())).toBe(true)
  })
  it.each(CONTROL_STORE)('ExperimentControlStore：%s', (_label, predicate) => {
    expect(predicate(controlStore())).toBe(true)
  })
})

describe('Phase 8-M0-B3：四个 props-only 数字孪生面板（84）', () => {
  it.each(TWIN_PANELS)('%s 生产组件文件存在', (panel) => {
    expect(existsSync(componentPath(panel.fileName))).toBe(true)
  })
  it.each(TWIN_PANELS.flatMap((panel) => TWIN_COMMON.map((contract) => [panel, contract] as const)))
  ('%s 通用契约：%s', (panel, [_label, predicate]) => {
    const source = component(panel.fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(TWIN_PANELS.flatMap((panel) => panel.fields.map((field) => [panel, field] as const)))
  ('%s 呈现真实字段或中文空态：%s', (panel, field) => {
    const source = component(panel.fileName)
    expect(source === '' || source.includes(field)).toBe(true)
  })
  it.each(TWIN_PANELS)('%s 声明 %s props', (panel) => {
    const source = component(panel.fileName)
    const expectsArray = panel.plural ? /devices\s*\??\s*:/ : /device\s*\??\s*:/
    expect(source === '' || (expectsArray.test(source) && source.includes('ariaLabel'))).toBe(true)
  })
  it.each(TOPOLOGY_MAPPING)('SCADADeviceTopology：%s', (_label, predicate) => {
    expect(predicate(component('SCADADeviceTopology.vue'))).toBe(true)
  })
  it.each(TOPOLOGY_BINDINGS)('SCADADeviceTopology 精确 computed 绑定：%s', (_label, predicate) => {
    expect(predicate(component('SCADADeviceTopology.vue'))).toBe(true)
  })
})

describe('Phase 8-M0-B3：三个 props-only SCADA 组件（78）', () => {
  it.each(SCADA_COMPONENTS)('%s 生产组件文件存在', (_name, fileName) => {
    expect(existsSync(componentPath(fileName))).toBe(true)
  })
  it.each(SCADA_COMPONENTS.flatMap(([name, fileName]) => SCADA_COMMON.map((contract) => [name, fileName, contract] as const)))
  ('%s 通用契约：%s', (_name, fileName, [_label, predicate]) => {
    const source = component(fileName)
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(METRIC_GRID)('SCADAMetricGrid：%s', (_label, predicate) => {
    const source = component('SCADAMetricGrid.vue')
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(ALERT_PANEL)('SCADAAlertPanel：%s', (_label, predicate) => {
    const source = component('SCADAAlertPanel.vue')
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(TOPOLOGY_DETAILS)('SCADADeviceTopology：%s', (_label, predicate) => {
    const source = component('SCADADeviceTopology.vue')
    expect(source === '' || predicate(source)).toBe(true)
  })
  it.each(SCADA_COMPONENTS)('%s 保留精确中文空态 %s', (_name, fileName, emptyLabel) => {
    const source = component(fileName)
    expect(source === '' || source.includes(emptyLabel)).toBe(true)
  })
})

describe('Phase 8-M0-B3：合同数量守卫', () => {
  it('至少执行 320 个 B3 UI 合同', () => {
    const count = WORKSPACE_BOUNDARY.length
      + WORKSPACE_FOCUS.length
      + WORKSPACE_PROGRESS.length
      + WORKSPACE_COMMAND.length
      + WORKSPACE_STATES.length
      + WORKSPACE_LAYOUT.length
      + CONTROL_PAGE.length
      + CONTROL_STORE.length
      + TWIN_PANELS.length
      + TWIN_PANELS.length * TWIN_COMMON.length
      + TWIN_PANELS.reduce((total, panel) => total + panel.fields.length, 0)
      + TWIN_PANELS.length
      + TOPOLOGY_MAPPING.length
      + TOPOLOGY_BINDINGS.length
      + SCADA_COMPONENTS.length
      + SCADA_COMPONENTS.length * SCADA_COMMON.length
      + METRIC_GRID.length
      + ALERT_PANEL.length
      + TOPOLOGY_DETAILS.length
      + SCADA_COMPONENTS.length

    expect(count).toBeGreaterThanOrEqual(320)
  })
})
