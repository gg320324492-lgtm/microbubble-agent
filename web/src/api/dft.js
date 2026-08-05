// MicroBubble DFT 计算 API 封装 — Phase 5 集成 (W-N-D)
//
// 7 个端点 (全部 /api/v1/dft/*):
//   GET    /dft/tools                  → 工具健康状态
//   POST   /dft/gaussian               → 提交 Gaussian 16W 计算
//   POST   /dft/gromacs                → 提交 GROMACS MD
//   POST   /dft/mace                   → 提交 MACE 优化
//   POST   /dft/pyscf                  → 提交 PySCF
//   GET    /dft/status/{task_id}       → 任务状态
//   GET    /dft/result/{task_id}       → 任务结果
//
// 与后端 app/api/v1/dft.py 配套，axios 全局带 Authorization header.

import axios from 'axios'

/** 工具健康状态（前端启动时调一次） */
export const fetchDftTools = () =>
  axios.get('/api/v1/dft/tools').then((r) => r.data)

/** 提交 Gaussian 16W 计算 */
export const submitGaussian = (params) =>
  axios.post('/api/v1/dft/gaussian', params).then((r) => r.data)

/** 提交 GROMACS MD（5 个核心参数） */
export const submitGromacs = (params) =>
  axios.post('/api/v1/dft/gromacs', params).then((r) => r.data)

/** 提交 MACE 优化 */
export const submitMace = (params) =>
  axios.post('/api/v1/dft/mace', params).then((r) => r.data)

/** 提交 PySCF 计算 */
export const submitPyscf = (params) =>
  axios.post('/api/v1/dft/pyscf', params).then((r) => r.data)

/** 任务状态（轮询用） */
export const fetchDftStatus = (taskId) =>
  axios.get(`/api/v1/dft/status/${taskId}`).then((r) => r.data)

/** 任务结果（完成后拉） */
export const fetchDftResult = (taskId) =>
  axios.get(`/api/v1/dft/result/${taskId}`).then((r) => r.data)
