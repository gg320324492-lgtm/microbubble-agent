/**
 * scripts/generate-pwa-icons.mjs — 生成 PWA 图标
 *
 * 用纯 Node.js 生成珊瑚橙渐变 + 聊天气泡 emoji 的 PNG 图标
 * 避免依赖 canvas 包（增加依赖），手写 PNG 字节流
 */

import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { deflateSync } from 'node:zlib'

const __dirname = dirname(fileURLToPath(import.meta.url))
const publicDir = resolve(__dirname, '../public')
mkdirSync(publicDir, { recursive: true })

/**
 * 生成 PNG 文件
 * - size: 像素尺寸 (192 或 512)
 * - 含 CRC32 校验的 PNG 头 + IDAT + IEND
 */
function createPng(size) {
  const W = size, H = size
  const cx = W / 2, cy = H / 2
  const r = size * 0.42

  // 像素数据：珊瑚橙渐变 + 聊天气泡
  // 每行前加 1 byte filter (0 = None)
  const raw = Buffer.alloc(H * (W * 4 + 1))

  for (let y = 0; y < H; y++) {
    const rowOffset = y * (W * 4 + 1)
    raw[rowOffset] = 0 // filter type None
    for (let x = 0; x < W; x++) {
      const dx = x - cx, dy = y - cy
      const dist = Math.sqrt(dx * dx + dy * dy)

      const off = rowOffset + 1 + x * 4
      if (dist < r) {
        // 圆形 logo 内：珊瑚橙渐变
        const t = (dist / r)
        const r1 = Math.round(255 - t * 0)
        const g1 = Math.round(122 + t * 30)
        const b1 = Math.round(92 + t * 40)
        raw[off] = r1
        raw[off + 1] = g1
        raw[off + 2] = b1
        raw[off + 3] = 255
      } else if (dist < r + size * 0.05) {
        // 边缘渐变（消除锯齿）
        const t = (dist - r) / (size * 0.05)
        const a = Math.round(255 * (1 - t))
        raw[off] = 255
        raw[off + 1] = 122
        raw[off + 2] = 92
        raw[off + 3] = a
      } else {
        // 透明背景
        raw[off] = 0
        raw[off + 1] = 0
        raw[off + 2] = 0
        raw[off + 3] = 0
      }

      // 在中心画一个简化的聊天气泡
      if (dist < size * 0.25) {
        const bubbleDx = dx / (size * 0.25)
        const bubbleDy = dy / (size * 0.25)
        // 圆形气泡
        if (bubbleDx * bubbleDx + bubbleDy * bubbleDy < 0.9) {
          raw[off] = 255
          raw[off + 1] = 255
          raw[off + 2] = 255
          raw[off + 3] = 255
        }
        // 三个点（聊天气泡内的"打字"指示）
        if (
          (Math.abs(dx + size * 0.1) < size * 0.025 && Math.abs(dy) < size * 0.025) ||
          (Math.abs(dx) < size * 0.025 && Math.abs(dy) < size * 0.025) ||
          (Math.abs(dx - size * 0.1) < size * 0.025 && Math.abs(dy) < size * 0.025)
        ) {
          raw[off] = 255
          raw[off + 1] = 122
          raw[off + 2] = 92
          raw[off + 3] = 255
        }
      }
    }
  }

  // PNG 编码
  const compressed = deflateSync(raw)

  // CRC32 校验
  const crcTable = new Uint32Array(256)
  for (let i = 0; i < 256; i++) {
    let c = i
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1)
    }
    crcTable[i] = c
  }
  function crc32(buf) {
    let c = 0xFFFFFFFF
    for (let i = 0; i < buf.length; i++) {
      c = crcTable[(c ^ buf[i]) & 0xFF] ^ (c >>> 8)
    }
    return (c ^ 0xFFFFFFFF) >>> 0
  }

  function chunk(type, data) {
    const length = Buffer.alloc(4)
    length.writeUInt32BE(data.length, 0)
    const typeAndData = Buffer.concat([Buffer.from(type), data])
    const crc = Buffer.alloc(4)
    crc.writeUInt32BE(crc32(typeAndData), 0)
    return Buffer.concat([length, typeAndData, crc])
  }

  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(W, 0)
  ihdr.writeUInt32BE(H, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // color type RGBA
  ihdr[10] = 0 // compression
  ihdr[11] = 0 // filter
  ihdr[12] = 0 // interlace

  return Buffer.concat([
    sig,
    chunk('IHDR', ihdr),
    chunk('IDAT', compressed),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

// 生成两个尺寸
writeFileSync(resolve(publicDir, 'pwa-192.png'), createPng(192))
writeFileSync(resolve(publicDir, 'pwa-512.png'), createPng(512))
writeFileSync(resolve(publicDir, 'pwa-512-maskable.png'), createPng(512))

console.log('✅ PWA 图标生成完成：')
console.log('  - public/pwa-192.png (192x192)')
console.log('  - public/pwa-512.png (512x512)')
console.log('  - public/pwa-512-maskable.png (512x512 maskable)')