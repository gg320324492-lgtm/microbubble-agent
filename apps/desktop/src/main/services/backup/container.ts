// 备份容器格式（M5-1）— MNBBK1 自实现，零依赖（node:crypto + node:zlib）。
// 二进制布局: magic "MNBBK1"(6B) | salt(16B) | iv(12B) | gzip密文 | authTag(16B)
// gzip 明文: [4B JSON长度 LE] + JSON头部(版本/时间/清单+各段sha256) + 各段数据连续排列
// 密钥: scrypt(password, salt, N=16384, r=8, p=1, keylen=32) → AES-256-GCM
import { createCipheriv, createDecipheriv, randomBytes, scryptSync, createHash } from 'node:crypto'
import { gzipSync, gunzipSync } from 'node:zlib'

const MAGIC = Buffer.from('MNBBK1')
const SALT_LEN = 16
const IV_LEN = 12
const TAG_LEN = 16
const HEADER_LEN_LEN = 4

export interface BackupSegment {
  name: string
  data: Buffer
}

export interface ContainerHeader {
  format: string
  app_version: string
  created_at: number
  segments: { name: string; size: number; sha256: string }[]
}

function deriveKey(password: string, salt: Buffer): Buffer {
  return scryptSync(Buffer.from(password, 'utf8'), salt, 32, { N: 16384, r: 8, p: 1 })
}

/** 打包：段数据 + 密码 → 加密容器 Buffer */
export function packContainer(
  segments: BackupSegment[],
  meta: { app_version: string },
  password: string
): Buffer {
  const salt = randomBytes(SALT_LEN)
  const iv = randomBytes(IV_LEN)
  const key = deriveKey(password, salt)

  const manifest: ContainerHeader['segments'] = []
  const datas: Buffer[] = []
  for (const seg of segments) {
    const sha256 = createHash('sha256').update(seg.data).digest('base64')
    manifest.push({ name: seg.name, size: seg.data.length, sha256 })
    datas.push(seg.data)
  }
  const header: ContainerHeader = {
    format: 'MNBBK1',
    app_version: meta.app_version,
    created_at: Date.now(),
    segments: manifest
  }

  const headerBuf = Buffer.from(JSON.stringify(header), 'utf8')
  const lenBuf = Buffer.alloc(HEADER_LEN_LEN)
  lenBuf.writeUInt32LE(headerBuf.length)
  const plaintext = Buffer.concat([lenBuf, headerBuf, ...datas])

  const compressed = gzipSync(plaintext)
  const cipher = createCipheriv('aes-256-gcm', key, iv)
  const encrypted = Buffer.concat([cipher.update(compressed), cipher.final()])
  const authTag = cipher.getAuthTag()

  return Buffer.concat([MAGIC, salt, iv, encrypted, authTag])
}

/** 拆解：解密验签 + gunzip + 解析头部与段数据；密码错/篡改在此抛错 */
export function unpackContainer(data: Buffer, password: string): {
  header: ContainerHeader
  segments: Map<string, Buffer>
} {
  if (data.length < MAGIC.length + SALT_LEN + IV_LEN + TAG_LEN) {
    throw new Error('文件太小，不是有效的备份容器')
  }
  if (!data.subarray(0, MAGIC.length).equals(MAGIC)) {
    throw new Error('无效的备份文件格式（magic 不匹配）')
  }
  const salt = data.subarray(MAGIC.length, MAGIC.length + SALT_LEN)
  const iv = data.subarray(MAGIC.length + SALT_LEN, MAGIC.length + SALT_LEN + IV_LEN)
  const authTag = data.subarray(data.length - TAG_LEN)
  const encrypted = data.subarray(MAGIC.length + SALT_LEN + IV_LEN, data.length - TAG_LEN)

  const key = deriveKey(password, salt)
  const decipher = createDecipheriv('aes-256-gcm', key, iv)
  decipher.setAuthTag(authTag)
  let decrypted: Buffer
  try {
    decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()])
  } catch {
    throw new Error('解密失败：密码错误或文件已损坏')
  }

  const decompressed = gunzipSync(decrypted)

  const headerLen = decompressed.readUInt32LE(0)
  const header: ContainerHeader = JSON.parse(decompressed.subarray(HEADER_LEN_LEN, HEADER_LEN_LEN + headerLen).toString('utf8'))

  let offset = HEADER_LEN_LEN + headerLen
  const segments = new Map<string, Buffer>()
  for (const seg of header.segments) {
    segments.set(seg.name, decompressed.subarray(offset, offset + seg.size))
    offset += seg.size
  }
  return { header, segments }
}
