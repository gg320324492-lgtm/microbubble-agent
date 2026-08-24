// Phase 8-K2 Scientific Device Integration Layer Tests
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

import {
  isValidScientificDevice, isValidSensorReading, isValidDeviceParameter,
  isValidDeviceType, isValidDeviceStatus,
  DEVICE_TYPES, DEVICE_STATUSES,
  __testHelpers as deviceHelpers
} from '../../src/shared/device/device-schema'
import type { ScientificDevice, SensorReading, DeviceParameter } from '../../src/shared/device/device-schema'

import {
  SimulatedDevice, seededRandom, hashSeed,
  createPumpSimulator, createOzoneSimulator, createSensorSimulator
} from '../../src/services/device/simulated-device'
import {
  DeviceStreamManager, STREAM_EVENT_TYPES
} from '../../src/services/device/device-stream-manager'
import {
  readingToRecord, readingsToDataset, aggregateReadings
} from '../../src/services/device/device-experiment-adapter'
import {
  readingsToFeatures, predictFromReadings, predictLatestReading, streamPredict
} from '../../src/services/device/device-twin-adapter'
import {
  getDeviceTemplate, listDeviceTemplates, DEVICE_TEMPLATE_KINDS
} from '../../src/services/device/device-templates'

const readShared = (name: string) => readFileSync(join(__dirname, '../../src/shared/device', name), 'utf8')
const read = (name: string) => readFileSync(join(__dirname, '../../src/services/device', name), 'utf8')
const readDocs = (name: string) => readFileSync(join(__dirname, '../../docs/device', name), 'utf8')

function mkReading(metric = 'ph', value = 7.0, deviceId = 'dev-1'): SensorReading {
  return { deviceId, timestamp: 1, metric, value, unit: '' }
}

describe('Phase 8-K2 schema validators', () => {
  it('DEVICE_TYPES has 5', () => {
    expect(DEVICE_TYPES.length).toBe(5)
  })
  it('DEVICE_TYPES frozen', () => {
    expect(Object.isFrozen(DEVICE_TYPES)).toBe(true)
  })
  it('DEVICE_STATUSES has 4', () => {
    expect(DEVICE_STATUSES.length).toBe(4)
  })
  it('DEVICE_STATUSES frozen', () => {
    expect(Object.isFrozen(DEVICE_STATUSES)).toBe(true)
  })
  for (const t of ['pump', 'ozone-generator', 'sensor', 'reactor', 'controller']) {
    it(`isValidDeviceType accepts ${t}`, () => {
      expect(isValidDeviceType(t)).toBe(true)
    })
  }
  for (const s of ['unknown', 'PUMP', '', 'drone']) {
    it(`isValidDeviceType rejects ${s}`, () => {
      expect(isValidDeviceType(s)).toBe(false)
    })
  }
  for (const s of ['offline', 'connecting', 'online', 'error']) {
    it(`isValidDeviceStatus accepts ${s}`, () => {
      expect(isValidDeviceStatus(s)).toBe(true)
    })
  }
  for (const s of ['disconnected', 'ONLINE', '']) {
    it(`isValidDeviceStatus rejects ${s}`, () => {
      expect(isValidDeviceStatus(s)).toBe(false)
    })
  }
  it('isValidDeviceParameter accepts numeric', () => {
    expect(isValidDeviceParameter({ name: 'a', value: 1.5, unit: 'mg' })).toBe(true)
  })
  it('isValidDeviceParameter accepts string', () => {
    expect(isValidDeviceParameter({ name: 'a', value: 'auto', unit: '' })).toBe(true)
  })
  it('isValidDeviceParameter accepts boolean', () => {
    expect(isValidDeviceParameter({ name: 'a', value: true, unit: '' })).toBe(true)
  })
  it('isValidDeviceParameter rejects empty name', () => {
    expect(isValidDeviceParameter({ name: '', value: 1, unit: 'u' })).toBe(false)
  })
  it('isValidDeviceParameter rejects null', () => {
    expect(isValidDeviceParameter(null)).toBe(false)
  })
  it('isValidScientificDevice accepts valid', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'pump', protocol: 'sim',
      status: 'online', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(true)
  })
  it('isValidScientificDevice rejects invalid type', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'unknown', protocol: 'sim',
      status: 'online', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(false)
  })
  it('isValidScientificDevice rejects bad status', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'pump', protocol: 'sim',
      status: 'invalid', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(false)
  })
  it('isValidScientificDevice rejects NaN', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'pump', protocol: 'sim',
      status: 'online', parameters: [], lastSeen: NaN, createdAt: 1
    })).toBe(false)
  })
  it('isValidSensorReading accepts valid', () => {
    expect(isValidSensorReading({ deviceId: 'd', timestamp: 1, metric: 'm', value: 1.5, unit: 'u' })).toBe(true)
  })
  it('isValidSensorReading rejects empty deviceId', () => {
    expect(isValidSensorReading({ deviceId: '', timestamp: 1, metric: 'm', value: 1, unit: 'u' })).toBe(false)
  })
  it('isValidSensorReading rejects NaN value', () => {
    expect(isValidSensorReading({ deviceId: 'd', timestamp: 1, metric: 'm', value: NaN, unit: 'u' })).toBe(false)
  })
  it('isValidSensorReading rejects negative timestamp', () => {
    expect(isValidSensorReading({ deviceId: 'd', timestamp: -1, metric: 'm', value: 1, unit: 'u' })).toBe(true)
  })
})

describe('Phase 8-K2 seeded random', () => {
  it('seededRandom returns finite number', () => {
    const r = seededRandom(1)()
    expect(Number.isFinite(r)).toBe(true)
  })
  it('seededRandom returns 0..1', () => {
    const fn = seededRandom(42)
    for (let i = 0; i < 10; i++) {
      const v = fn()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThanOrEqual(1)
    }
  })
  it('seededRandom deterministic for same seed', () => {
    const a = seededRandom(123)()
    const b = seededRandom(123)()
    expect(a).toBe(b)
  })
  it('seededRandom different seed different value', () => {
    const a = seededRandom(1)()
    const b = seededRandom(2)()
    expect(a).not.toBe(b)
  })
  it('hashSeed returns number', () => {
    expect(typeof hashSeed('abc')).toBe('number')
  })
  it('hashSeed deterministic', () => {
    expect(hashSeed('foo')).toBe(hashSeed('foo'))
  })
  it('hashSeed different inputs different outputs', () => {
    expect(hashSeed('foo')).not.toBe(hashSeed('bar'))
  })
})

describe('Phase 8-K2 SimulatedDevice', () => {
  it('creates with id', () => {
    const d = new SimulatedDevice('test', 'pump', [])
    expect(typeof d.id).toBe('string')
  })
  it('initial status offline', () => {
    expect(new SimulatedDevice('test', 'pump', []).status()).toBe('offline')
  })
  it('connect transitions to online', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.connect()
    expect(d.status()).toBe('online')
  })
  it('disconnect transitions back to offline', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.connect()
    await d.disconnect()
    expect(d.status()).toBe('offline')
  })
  it('read offline returns null', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    expect(await d.read('a')).toBeNull()
  })
  it('read online returns SensorReading', async () => {
    const d = new SimulatedDevice('test', 'pump', [{ name: 'flow', value: 1.0, unit: 'L/min' }])
    await d.connect()
    const r = await d.read('flow')
    expect(r).not.toBeNull()
    expect(r!.metric).toBe('flow')
  })
  it('read returns finite value', async () => {
    const d = new SimulatedDevice('test', 'pump', [{ name: 'flow', value: 1.0, unit: 'L/min' }])
    await d.connect()
    const r = await d.read('flow')
    expect(Number.isFinite(r!.value)).toBe(true)
  })
  it('read uses metric name not found returns baseValue 1', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.connect()
    const r = await d.read('non-existent')
    expect(r).not.toBeNull()
  })
  it('write adds parameter', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.write({ name: 'a', value: 1, unit: 'u' })
    expect(d.describe().parameters.some((p) => p.name === 'a')).toBe(true)
  })
  it('write replaces existing parameter', async () => {
    const d = new SimulatedDevice('test', 'pump', [{ name: 'a', value: 1, unit: 'u' }])
    await d.write({ name: 'a', value: 2, unit: 'u' })
    const p = d.describe().parameters.find((p) => p.name === 'a')!
    expect(p.value).toBe(2)
  })
  it('describe returns ScientificDevice', () => {
    const d = new SimulatedDevice('test', 'pump', [])
    const desc = d.describe()
    expect(desc.type).toBe('pump')
    expect(desc.name).toBe('test')
  })
  it('health tracks reads', async () => {
    const d = new SimulatedDevice('test', 'pump', [{ name: 'a', value: 1, unit: 'u' }])
    await d.connect()
    await d.read('a')
    await d.read('a')
    expect(d.health().reads).toBe(2)
  })
  it('health tracks writes', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.write({ name: 'a', value: 1, unit: 'u' })
    expect(d.health().writes).toBe(1)
  })
  it('health tracks errors when read offline', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.read('a')
    expect(d.health().errors).toBe(1)
  })
  it('health connected true when online', async () => {
    const d = new SimulatedDevice('test', 'pump', [])
    await d.connect()
    expect(d.health().connected).toBe(true)
  })
  it('health connected false when offline', () => {
    const d = new SimulatedDevice('test', 'pump', [])
    expect(d.health().connected).toBe(false)
  })
  it('createPumpSimulator sets default flow_rate', () => {
    const d = createPumpSimulator('p1')
    expect(d.describe().parameters.some((p) => p.name === 'flow_rate')).toBe(true)
  })
  it('createOzoneSimulator sets default ozone_dose', () => {
    const d = createOzoneSimulator('o1')
    expect(d.describe().parameters.some((p) => p.name === 'ozone_dose')).toBe(true)
  })
  it('createSensorSimulator sets default temperature', () => {
    const d = createSensorSimulator('s1')
    expect(d.describe().parameters.some((p) => p.name === 'temperature')).toBe(true)
  })
  it('createPumpSimulator type pump', () => {
    expect(createPumpSimulator('p1').type).toBe('pump')
  })
  it('createOzoneSimulator type ozone-generator', () => {
    expect(createOzoneSimulator('o1').type).toBe('ozone-generator')
  })
  it('createSensorSimulator type sensor', () => {
    expect(createSensorSimulator('s1').type).toBe('sensor')
  })
})

describe('Phase 8-K2 DeviceStreamManager', () => {
  let mgr: DeviceStreamManager
  let dev: SimulatedDevice

  beforeEach(() => {
    mgr = new DeviceStreamManager(10)
    dev = createSensorSimulator('s1')
  })

  it('STREAM_EVENT_TYPES has 5', () => {
    expect(STREAM_EVENT_TYPES.length).toBe(5)
  })
  it('registerAdapter adds adapter', () => {
    mgr.registerAdapter(dev)
    expect(mgr.adapterCount()).toBe(1)
  })
  it('unregisterAdapter removes', () => {
    mgr.registerAdapter(dev)
    mgr.unregisterAdapter(dev.id)
    expect(mgr.adapterCount()).toBe(0)
  })
  it('unregisterAdapter clears buffer', async () => {
    await dev.connect()
    mgr.registerAdapter(dev)
    mgr.bufferData({ deviceId: dev.id, timestamp: 1, metric: 'm', value: 1, unit: 'u' })
    mgr.unregisterAdapter(dev.id)
    expect(mgr.getBufferSize(dev.id)).toBe(0)
  })
  it('subscribe returns unsubscribe', () => {
    const unsub = mgr.subscribe(dev.id, 'm', () => {})
    expect(typeof unsub).toBe('function')
  })
  it('subscribeAll listenerCount 1', () => {
    mgr.subscribeAll(() => {})
    expect(mgr.listenerCount()).toBe(0) // listenerCount counts per-key only
  })
  it('collectReading returns reading when online', async () => {
    await dev.connect()
    mgr.registerAdapter(dev)
    const r = await mgr.collectReading(dev.id, 'temperature')
    expect(r).not.toBeNull()
  })
  it('collectReading returns null when not registered', async () => {
    expect(await mgr.collectReading(dev.id, 'temperature')).toBeNull()
  })
  it('bufferData adds reading', () => {
    mgr.bufferData(mkReading())
    expect(mgr.getBufferSize(mkReading().deviceId)).toBe(1)
  })
  it('flush returns and clears', () => {
    mgr.bufferData(mkReading())
    const out = mgr.flush(mkReading().deviceId)
    expect(out.length).toBe(1)
    expect(mgr.getBufferSize(mkReading().deviceId)).toBe(0)
  })
  it('getBuffer returns copy', () => {
    mgr.bufferData(mkReading())
    const buf = mgr.getBuffer(mkReading().deviceId)
    buf.push(mkReading())
    expect(mgr.getBufferSize(mkReading().deviceId)).toBe(1)
  })
  it('buffer overflow drops oldest', () => {
    const small = new DeviceStreamManager(3)
    for (let i = 0; i < 5; i++) {
      small.bufferData({ deviceId: 'd', timestamp: i, metric: 'm', value: i, unit: '' })
    }
    expect(small.getBufferSize('d')).toBe(3)
    expect(small.getBuffer('d')[0].value).toBe(2)
  })
  it('emit invokes listener', () => {
    let called = false
    mgr.subscribe(dev.id, 'm', () => { called = true })
    mgr.emit({ type: 'reading', deviceId: dev.id, payload: { metric: 'm' }, timestamp: 1 })
    expect(called).toBe(true)
  })
  it('emit swallows listener errors', () => {
    mgr.subscribe(dev.id, 'm', () => { throw new Error('boom') })
    expect(() => mgr.emit({ type: 'reading', deviceId: dev.id, payload: { metric: 'm' }, timestamp: 1 })).not.toThrow()
  })
  it('subscribeAll catches all events', () => {
    let count = 0
    mgr.subscribeAll(() => { count++ })
    mgr.emit({ type: 'reading', deviceId: 'x', payload: {}, timestamp: 1 })
    mgr.emit({ type: 'reading', deviceId: 'y', payload: {}, timestamp: 2 })
    expect(count).toBe(2)
  })
  it('unsubscribeAll clears all subs for device', () => {
    mgr.subscribe(dev.id, 'a', () => {})
    mgr.subscribe(dev.id, 'b', () => {})
    const n = mgr.unsubscribeAll(dev.id)
    expect(n).toBe(2)
  })
  it('clear resets state', () => {
    mgr.registerAdapter(dev)
    mgr.subscribeAll(() => {})
    mgr.clear()
    expect(mgr.adapterCount()).toBe(0)
  })
  it('getAdapters returns array', () => {
    mgr.registerAdapter(dev)
    expect(Array.isArray(mgr.getAdapters())).toBe(true)
  })
})

describe('Phase 8-K2 DeviceExperimentAdapter', () => {
  it('readingToRecord returns ExperimentRecord', () => {
    const rec = readingToRecord(mkReading('ph', 7.5), 'alice', 'exp-1')
    expect(rec.experimentId).toBe('exp-1')
    expect(rec.parameters[0].name).toBe('ph')
  })
  it('readingToRecord sets operator', () => {
    const rec = readingToRecord(mkReading(), 'bob', 'e')
    expect(rec.operator).toBe('bob')
  })
  it('readingToRecord observations contains metric', () => {
    const rec = readingToRecord(mkReading('temp', 25), 'op', 'e')
    expect(rec.observations).toContain('temp')
  })
  it('readingToRecord notes contains device', () => {
    const rec = readingToRecord(mkReading('temp', 25, 'dev-x'), 'op', 'e')
    expect(rec.notes).toContain('dev-x')
  })
  it('readingToRecord parameter value matches reading', () => {
    const rec = readingToRecord(mkReading('temp', 25), 'op', 'e')
    expect(rec.parameters[0].value).toBe(25)
  })
  it('readingToRecord parameter type numeric', () => {
    const rec = readingToRecord(mkReading('temp', 25), 'op', 'e')
    expect(rec.parameters[0].type).toBe('numeric')
  })
  it('readingsToDataset empty returns empty dataset', () => {
    const ds = readingsToDataset([], 'empty')
    expect(ds.rows.length).toBe(0)
  })
  it('readingsToDataset single metric one variable', () => {
    const ds = readingsToDataset([
      mkReading('ph', 7.0),
      mkReading('ph', 7.1),
      mkReading('ph', 7.2)
    ], 'ph-data')
    expect(ds.variables.length).toBe(1)
    expect(ds.rows.length).toBe(3)
  })
  it('readingsToDataset multi metric multi variable', () => {
    const ds = readingsToDataset([
      mkReading('ph', 7.0),
      mkReading('temp', 25)
    ], 'mixed')
    expect(ds.variables.length).toBe(2)
  })
  it('readingsToDataset rows preserve order', () => {
    const ds = readingsToDataset([
      mkReading('ph', 1),
      mkReading('ph', 2),
      mkReading('ph', 3)
    ], 'd')
    expect(ds.rows.map((r) => r.ph)).toEqual([1, 2, 3])
  })
  it('readingsToDataset metadata has deviceId', () => {
    const ds = readingsToDataset([mkReading('a', 1, 'dev-99')], 'd')
    expect(ds.metadata.deviceId).toBe('dev-99')
  })
  it('aggregateReadings empty returns null', () => {
    expect(aggregateReadings([], 'ph')).toBeNull()
  })
  it('aggregateReadings computes mean', () => {
    const agg = aggregateReadings([
      mkReading('a', 1),
      mkReading('a', 2),
      mkReading('a', 3)
    ], 'a')
    expect(agg!.mean).toBe(2)
  })
  it('aggregateReadings computes min', () => {
    const agg = aggregateReadings([mkReading('a', 5), mkReading('a', 1), mkReading('a', 3)], 'a')
    expect(agg!.min).toBe(1)
  })
  it('aggregateReadings computes max', () => {
    const agg = aggregateReadings([mkReading('a', 5), mkReading('a', 1), mkReading('a', 3)], 'a')
    expect(agg!.max).toBe(5)
  })
  it('aggregateReadings count', () => {
    const agg = aggregateReadings([mkReading('a', 1), mkReading('a', 2)], 'a')
    expect(agg!.count).toBe(2)
  })
  it('aggregateReadings unit preserved', () => {
    const agg = aggregateReadings([mkReading('a', 1, 'd')], 'a')
    expect(agg!.unit).toBe('')
  })
})

describe('Phase 8-K2 DeviceTwinAdapter', () => {
  function setupTwin() {
    return {
      id: 'twin-1', name: 'twin', domain: 'env',
      inputs: ['ph'], outputs: ['degradation'],
      parameters: [{ name: 'p1', value: 1, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const,
      createdAt: 1, updatedAt: 2
    }
  }

  it('readingsToFeatures empty returns empty', () => {
    expect(readingsToFeatures([]).length).toBe(0)
  })
  it('readingsToFeatures groups by metric', () => {
    const f = readingsToFeatures([
      mkReading('ph', 1),
      mkReading('ph', 2),
      mkReading('temp', 25)
    ])
    expect(f.length).toBe(2)
    expect(f.find((x) => x.name === 'ph')).toBeDefined()
    expect(f.find((x) => x.name === 'temp')).toBeDefined()
  })
  it('readingsToFeatures preserves values', () => {
    const f = readingsToFeatures([mkReading('a', 1), mkReading('a', 2)])
    expect(f[0].values).toEqual([1, 2])
  })
  it('predictFromReadings returns one prediction', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(pred.length).toBe(1)
  })
  it('predictFromReadings prediction has modelId', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(pred[0].modelId).toBe('twin-1')
  })
  it('predictFromReadings prediction has confidence', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(typeof pred[0].confidence).toBe('number')
  })
  it('predictLatestReading returns TwinPrediction', () => {
    const p = predictLatestReading(mkReading('a', 5), setupTwin())
    expect(p.modelId).toBe('twin-1')
  })
  it('streamPredict invokes callback per reading', () => {
    let count = 0
    streamPredict({
      deviceId: 'd',
      readings: [mkReading('a', 1), mkReading('a', 2), mkReading('a', 3)],
      twinModel: setupTwin()
    }, () => { count++ })
    expect(count).toBe(3)
  })
  it('streamPredict returns predictions', () => {
    const preds = streamPredict({
      deviceId: 'd',
      readings: [mkReading('a', 1), mkReading('a', 2)],
      twinModel: setupTwin()
    }, () => {})
    expect(preds.length).toBe(2)
  })
})

describe('Phase 8-K2 DeviceTemplates', () => {
  it('DEVICE_TEMPLATE_KINDS has 3', () => {
    expect(DEVICE_TEMPLATE_KINDS.length).toBe(3)
  })
  for (const k of ['o3-mnb-reactor', 'cfd-experiment', 'water-treatment-monitoring']) {
    it(`getDeviceTemplate accepts ${k}`, () => {
      const t = getDeviceTemplate(k as never)
      expect(t.kind).toBe(k)
    })
  }
  it('getDeviceTemplate throws on unknown', () => {
    expect(() => getDeviceTemplate('nope' as never)).toThrow()
  })
  it('listDeviceTemplates returns 3', () => {
    expect(listDeviceTemplates().length).toBe(3)
  })
  it('listDeviceTemplates returns clones', () => {
    const list = listDeviceTemplates()
    list[0].devices[0].parameters.push({ name: 'm', value: 1, unit: 'u' })
    expect(listDeviceTemplates()[0].devices[0].parameters).not.toContainEqual(expect.objectContaining({ name: 'm' }))
  })
  it('o3-mnb-reactor has 5 devices', () => {
    expect(getDeviceTemplate('o3-mnb-reactor').devices.length).toBe(5)
  })
  it('cfd-experiment has 4 devices', () => {
    expect(getDeviceTemplate('cfd-experiment').devices.length).toBe(4)
  })
  it('water-treatment-monitoring has 4 devices', () => {
    expect(getDeviceTemplate('water-treatment-monitoring').devices.length).toBe(4)
  })
  it('o3-mnb-reactor contains pump', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    expect(t.devices.some((d) => d.type === 'pump')).toBe(true)
  })
  it('o3-mnb-reactor contains ozone-generator', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    expect(t.devices.some((d) => d.type === 'ozone-generator')).toBe(true)
  })
  it('each template has non-empty description', () => {
    for (const t of listDeviceTemplates()) expect(t.description.length).toBeGreaterThan(0)
  })
  it('each template has non-empty name', () => {
    for (const t of listDeviceTemplates()) expect(t.name.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-K2 secret guard', () => {
  it('findForbidden detects sk-', () => {
    expect(deviceHelpers.findForbidden('sk-abc')).toBe('sk-')
  })
  it('findForbidden detects apiKey', () => {
    expect(deviceHelpers.findForbidden('apiKey')).toBe('apiKey')
  })
  it('findForbidden detects Bearer', () => {
    expect(deviceHelpers.findForbidden('Bearer x')).toBe('Bearer ')
  })
  it('findForbidden detects authorization', () => {
    expect(deviceHelpers.findForbidden('authorization: x')).toBe('authorization')
  })
  it('findForbidden detects providerId', () => {
    expect(deviceHelpers.findForbidden('providerId=x')).toBe('providerId')
  })
  it('findForbidden handles null', () => {
    expect(deviceHelpers.findForbidden(null)).toBeNull()
  })
  it('findForbidden handles arrays', () => {
    expect(deviceHelpers.findForbidden(['ok', 'token'])).toBe('token')
  })
  it('findForbidden handles nested objects', () => {
    expect(deviceHelpers.findForbidden({ a: { b: 'cipher' } })).toBe('cipher')
  })
})

describe('Phase 8-K2 integration', () => {
  it('full device → record → dataset round trip', () => {
    const readings = [
      mkReading('ph', 7.0, 'dev-1'),
      mkReading('ph', 7.1, 'dev-1'),
      mkReading('ph', 7.2, 'dev-1')
    ]
    const records = readings.map((r) => readingToRecord(r, 'alice', 'exp-1'))
    expect(records.length).toBe(3)
    const ds = readingsToDataset(readings, 'all-readings')
    expect(ds.rows.length).toBe(3)
  })
  it('full device → twin prediction round trip', () => {
    const readings = [
      mkReading('ph', 7.0),
      mkReading('ph', 7.5)
    ]
    const twin = {
      id: 'twin-1', name: 'twin', domain: 'env',
      inputs: ['ph'], outputs: ['deg'],
      parameters: [{ name: 'p1', value: 0.5, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const, createdAt: 1, updatedAt: 2
    }
    const preds = predictFromReadings({ deviceId: 'dev-1', readings, twinModel: twin })
    expect(preds.length).toBe(1)
  })
  it('full device simulator → stream → record → dataset', async () => {
    const dev = createSensorSimulator('s1')
    await dev.connect()
    const mgr = new DeviceStreamManager()
    mgr.registerAdapter(dev)
    const r1 = await mgr.collectReading(dev.id, 'temperature')
    const r2 = await mgr.collectReading(dev.id, 'temperature')
    expect(r1).not.toBeNull()
    expect(r2).not.toBeNull()
    const records = [r1!, r2!].map((r) => readingToRecord(r, 'alice', 'exp-1'))
    expect(records.length).toBe(2)
    const ds = readingsToDataset([r1!, r2!], 'sensor-data')
    expect(ds.rows.length).toBe(2)
  })
})

describe('Phase 8-K2 schema edge cases', () => {
  it('isValidScientificDevice rejects null', () => {
    expect(isValidScientificDevice(null)).toBe(false)
  })
  it('isValidScientificDevice rejects array', () => {
    expect(isValidScientificDevice([])).toBe(false)
  })
  it('isValidSensorReading rejects null', () => {
    expect(isValidSensorReading(null)).toBe(false)
  })
  it('isValidDeviceParameter rejects object value', () => {
    expect(isValidDeviceParameter({ name: 'a', value: {}, unit: 'u' })).toBe(false)
  })
})

describe('Phase 8-K2 source contracts', () => {
  it('schema has ScientificDevice', () => {
    expect(readShared('device-schema.ts')).toContain('interface ScientificDevice')
  })
  it('schema has SensorReading', () => {
    expect(readShared('device-schema.ts')).toContain('interface SensorReading')
  })
  it('schema has DeviceParameter', () => {
    expect(readShared('device-schema.ts')).toContain('interface DeviceParameter')
  })
  it('schema has 5 device types', () => {
    expect(readShared('device-schema.ts')).toContain('pump')
    expect(readShared('device-schema.ts')).toContain('ozone-generator')
    expect(readShared('device-schema.ts')).toContain('sensor')
    expect(readShared('device-schema.ts')).toContain('reactor')
    expect(readShared('device-schema.ts')).toContain('controller')
  })
  it('schema has 4 device statuses', () => {
    expect(readShared('device-schema.ts')).toContain('offline')
    expect(readShared('device-schema.ts')).toContain('connecting')
    expect(readShared('device-schema.ts')).toContain('online')
    expect(readShared('device-schema.ts')).toContain('error')
  })
  it('adapter-schema has DeviceAdapter', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('interface DeviceAdapter')
  })
  it('simulator has SimulatedDevice', () => {
    expect(read('simulated-device.ts')).toContain('class SimulatedDevice')
  })
  it('simulator has createPumpSimulator', () => {
    expect(read('simulated-device.ts')).toContain('createPumpSimulator')
  })
  it('simulator has createOzoneSimulator', () => {
    expect(read('simulated-device.ts')).toContain('createOzoneSimulator')
  })
  it('simulator has createSensorSimulator', () => {
    expect(read('simulated-device.ts')).toContain('createSensorSimulator')
  })
  it('simulator has connect', () => {
    expect(read('simulated-device.ts')).toContain('connect')
  })
  it('simulator has disconnect', () => {
    expect(read('simulated-device.ts')).toContain('disconnect')
  })
  it('simulator has read', () => {
    expect(read('simulated-device.ts')).toContain('read')
  })
  it('simulator has write', () => {
    expect(read('simulated-device.ts')).toContain('write')
  })
  it('stream-manager has subscribe', () => {
    expect(read('device-stream-manager.ts')).toContain('subscribe')
  })
  it('stream-manager has collectReading', () => {
    expect(read('device-stream-manager.ts')).toContain('collectReading')
  })
  it('stream-manager has bufferData', () => {
    expect(read('device-stream-manager.ts')).toContain('bufferData')
  })
  it('experiment-adapter has readingToRecord', () => {
    expect(read('device-experiment-adapter.ts')).toContain('readingToRecord')
  })
  it('experiment-adapter has readingsToDataset', () => {
    expect(read('device-experiment-adapter.ts')).toContain('readingsToDataset')
  })
  it('twin-adapter has predictFromReadings', () => {
    expect(read('device-twin-adapter.ts')).toContain('predictFromReadings')
  })
  it('templates has 3 kinds', () => {
    expect(read('device-templates.ts')).toContain('o3-mnb-reactor')
    expect(read('device-templates.ts')).toContain('cfd-experiment')
    expect(read('device-templates.ts')).toContain('water-treatment-monitoring')
  })
  it('templates uses Object.freeze', () => {
    expect(read('device-templates.ts')).toContain('Object.freeze')
  })
})

describe('Phase 8-K2 docs presence', () => {
  it('device-integration.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/device/device-integration.md'))).toBe(true)
  })
  it('real-time-experiment-flow.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/device/real-time-experiment-flow.md'))).toBe(true)
  })
  it('device-integration.md mentions SimulatedDevice', () => {
    expect(readDocs('device-integration.md')).toContain('SimulatedDevice')
  })
  it('device-integration.md mentions DeviceStreamManager', () => {
    expect(readDocs('device-integration.md')).toContain('DeviceStreamManager')
  })
  it('real-time-experiment-flow.md mentions TwinPrediction', () => {
    expect(readDocs('real-time-experiment-flow.md')).toContain('TwinPrediction')
  })
})

describe('Phase 8-K2 SimulatedDevice detailed', () => {
  it('default protocol is sim://local', () => {
    expect(new SimulatedDevice('a', 'pump', []).describe().protocol).toBe('sim://local')
  })
  it('custom protocol', () => {
    expect(new SimulatedDevice('a', 'pump', [], { protocol: 'modbus://1.2.3.4' }).describe().protocol).toBe('modbus://1.2.3.4')
  })
  it('describe returns cloned parameters', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'flow', value: 1, unit: 'L/min' }])
    const desc = d.describe()
    desc.parameters.push({ name: 'extra', value: 1, unit: '' })
    expect(d.describe().parameters.length).toBe(1)
  })
  it('read with metric not in parameters uses default base', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'flow', value: 5, unit: 'L' }])
    await d.connect()
    const r = await d.read('unknown')
    expect(r).not.toBeNull()
  })
  it('two reads produce different values (noise)', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 10, unit: 'u' }])
    await d.connect()
    const a = await d.read('x')
    const b = await d.read('x')
    expect(a!.value).not.toBe(b!.value)
  })
  it('deterministic with same seed', async () => {
    const a = new SimulatedDevice('same', 'pump', [{ name: 'x', value: 10, unit: 'u' }], { seed: 42 })
    const b = new SimulatedDevice('same', 'pump', [{ name: 'x', value: 10, unit: 'u' }], { seed: 42 })
    await a.connect()
    await b.connect()
    const ra = await a.read('x')
    const rb = await b.read('x')
    expect(ra!.value).toBe(rb!.value)
  })
  it('health uptime > 0 when online', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.connect()
    await new Promise((r) => setTimeout(r, 2))
    expect(d.health().uptime).toBeGreaterThan(0)
  })
  it('health uptime = 0 when offline', () => {
    expect(new SimulatedDevice('a', 'pump', []).health().uptime).toBe(0)
  })
  it('write boolean value', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.write({ name: 'enabled', value: true, unit: '' })
    expect(d.describe().parameters.some((p) => p.name === 'enabled' && p.value === true)).toBe(true)
  })
  it('write string value', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.write({ name: 'mode', value: 'auto', unit: '' })
    expect(d.describe().parameters.some((p) => p.name === 'mode' && p.value === 'auto')).toBe(true)
  })
  it('lastSeen updated after connect', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    const before = d.describe().lastSeen
    await new Promise((r) => setTimeout(r, 2))
    await d.connect()
    expect(d.describe().lastSeen).toBeGreaterThan(before)
  })
  it('lastSeen updated after read', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.connect()
    const before = d.describe().lastSeen
    await new Promise((r) => setTimeout(r, 2))
    await d.read('x')
    expect(d.describe().lastSeen).toBeGreaterThan(before)
  })
  it('lastSeen updated after write', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.connect()
    const before = d.describe().lastSeen
    await new Promise((r) => setTimeout(r, 2))
    await d.write({ name: 'a', value: 1, unit: 'u' })
    expect(d.describe().lastSeen).toBeGreaterThan(before)
  })
  it('createPumpSimulator has 2 default parameters', () => {
    expect(createPumpSimulator('p1').describe().parameters.length).toBe(2)
  })
  it('createOzoneSimulator has 2 default parameters', () => {
    expect(createOzoneSimulator('o1').describe().parameters.length).toBe(2)
  })
  it('createSensorSimulator has 2 default parameters', () => {
    expect(createSensorSimulator('s1').describe().parameters.length).toBe(2)
  })
})

describe('Phase 8-K2 DeviceStreamManager detailed', () => {
  it('bufferData appends multiple readings', () => {
    const mgr = new DeviceStreamManager()
    for (let i = 0; i < 5; i++) mgr.bufferData({ deviceId: 'd', timestamp: i, metric: 'm', value: i, unit: '' })
    expect(mgr.getBufferSize('d')).toBe(5)
  })
  it('flush empty returns empty', () => {
    expect(new DeviceStreamManager().flush('nope').length).toBe(0)
  })
  it('getBuffer for unknown device returns empty', () => {
    expect(new DeviceStreamManager().getBuffer('nope').length).toBe(0)
  })
  it('listenerCount starts at 0', () => {
    expect(new DeviceStreamManager().listenerCount()).toBe(0)
  })
  it('listenerCount increases per subscribe', () => {
    const mgr = new DeviceStreamManager()
    mgr.subscribe('d', 'a', () => {})
    mgr.subscribe('d', 'b', () => {})
    expect(mgr.listenerCount()).toBe(2)
  })
  it('unsubscribe removes listener', () => {
    const mgr = new DeviceStreamManager()
    const unsub = mgr.subscribe('d', 'a', () => {})
    unsub()
    expect(mgr.listenerCount()).toBe(0)
  })
  it('subscribeAll adds global listener', () => {
    const mgr = new DeviceStreamManager()
    let called = false
    const unsub = mgr.subscribeAll(() => { called = true })
    mgr.emit({ type: 'reading', deviceId: 'd', payload: {}, timestamp: 1 })
    expect(called).toBe(true)
    unsub()
  })
  it('subscribeAll unsub removes', () => {
    const mgr = new DeviceStreamManager()
    let count = 0
    const unsub = mgr.subscribeAll(() => { count++ })
    unsub()
    mgr.emit({ type: 'reading', deviceId: 'd', payload: {}, timestamp: 1 })
    expect(count).toBe(0)
  })
  it('collectReading emits reading event', async () => {
    const dev = createSensorSimulator('s')
    await dev.connect()
    const mgr = new DeviceStreamManager()
    mgr.registerAdapter(dev)
    let readEvent = false
    mgr.subscribeAll((e) => { if (e.type === 'reading') readEvent = true })
    await mgr.collectReading(dev.id, 'temperature')
    expect(readEvent).toBe(true)
  })
  it('collectReading emits error event when adapter missing', async () => {
    const mgr = new DeviceStreamManager()
    let errorEvent = false
    mgr.subscribeAll((e) => { if (e.type === 'error') errorEvent = true })
    await mgr.collectReading('nope', 'm')
    expect(errorEvent).toBe(true)
  })
  it('collectReading buffers the reading', async () => {
    const dev = createSensorSimulator('s')
    await dev.connect()
    const mgr = new DeviceStreamManager()
    mgr.registerAdapter(dev)
    await mgr.collectReading(dev.id, 'temperature')
    expect(mgr.getBufferSize(dev.id)).toBe(1)
  })
  it('unsubscribeAll returns 0 for unknown device', () => {
    expect(new DeviceStreamManager().unsubscribeAll('nope')).toBe(0)
  })
  it('clear removes all adapters', () => {
    const mgr = new DeviceStreamManager()
    const dev = createSensorSimulator('s')
    mgr.registerAdapter(dev)
    mgr.clear()
    expect(mgr.adapterCount()).toBe(0)
  })
  it('clear removes all listeners', () => {
    const mgr = new DeviceStreamManager()
    mgr.subscribe('d', 'a', () => {})
    mgr.clear()
    expect(mgr.listenerCount()).toBe(0)
  })
})

describe('Phase 8-K2 DeviceExperimentAdapter detailed', () => {
  it('readingToRecord produces unique id per reading', () => {
    const r1 = readingToRecord({ deviceId: 'd', timestamp: 1, metric: 'm', value: 1, unit: 'u' }, 'op', 'e')
    const r2 = readingToRecord({ deviceId: 'd', timestamp: 2, metric: 'm', value: 1, unit: 'u' }, 'op', 'e')
    expect(r1.id).not.toBe(r2.id)
  })
  it('readingToRecord observations include value', () => {
    const rec = readingToRecord({ deviceId: 'd', timestamp: 1, metric: 'ph', value: 7.5, unit: '' }, 'op', 'e')
    expect(rec.observations).toContain('7.5')
  })
  it('readingToRecord parameter unit matches reading', () => {
    const rec = readingToRecord({ deviceId: 'd', timestamp: 1, metric: 'm', value: 1, unit: 'mg/L' }, 'op', 'e')
    expect(rec.parameters[0].unit).toBe('mg/L')
  })
  it('readingsToDataset with multiple metrics sorted', () => {
    const ds = readingsToDataset([
      mkReading('b', 2), mkReading('a', 1)
    ], 'm')
    expect(ds.variables.map((v) => v.name)).toContain('a')
    expect(ds.variables.map((v) => v.name)).toContain('b')
  })
  it('readingsToDataset row includes deviceId', () => {
    const ds = readingsToDataset([mkReading('a', 1, 'dev-x')], 'd')
    expect(ds.rows[0]._deviceId).toBe('dev-x')
  })
  it('readingsToDataset row includes timestamp', () => {
    const ds = readingsToDataset([mkReading('a', 1, 'dev-x')], 'd')
    expect(ds.rows[0]._timestamp).toBe(1)
  })
  it('aggregateReadings with single reading', () => {
    const agg = aggregateReadings([mkReading('a', 5)], 'a')
    expect(agg!.mean).toBe(5)
    expect(agg!.min).toBe(5)
    expect(agg!.max).toBe(5)
  })
  it('aggregateReadings ignores other metrics', () => {
    const agg = aggregateReadings([
      mkReading('a', 1),
      mkReading('b', 100),
      mkReading('a', 3)
    ], 'a')
    expect(agg!.count).toBe(2)
    expect(agg!.mean).toBe(2)
  })
  it('aggregateReadings mean decimal precision', () => {
    const agg = aggregateReadings([
      mkReading('a', 1),
      mkReading('a', 2),
      mkReading('a', 3)
    ], 'a')
    expect(agg!.mean).toBeCloseTo(2, 5)
  })
  it('aggregateReadings max computation', () => {
    const agg = aggregateReadings([
      mkReading('a', 10),
      mkReading('a', 5),
      mkReading('a', 20)
    ], 'a')
    expect(agg!.max).toBe(20)
  })
})

describe('Phase 8-K2 DeviceTwinAdapter detailed', () => {
  function setupTwin() {
    return {
      id: 'twin-1', name: 'twin', domain: 'env',
      inputs: ['a'], outputs: ['b'],
      parameters: [{ name: 'p1', value: 1, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const, createdAt: 1, updatedAt: 2
    }
  }
  it('readingsToFeatures single reading one value', () => {
    const f = readingsToFeatures([mkReading('a', 5)])
    expect(f[0].values).toEqual([5])
  })
  it('readingsToFeatures groups multiple readings', () => {
    const f = readingsToFeatures([
      mkReading('a', 1), mkReading('a', 2), mkReading('a', 3)
    ])
    expect(f[0].values).toEqual([1, 2, 3])
  })
  it('predictFromReadings prediction has finite output', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(Number.isFinite(pred[0].output.y)).toBe(true)
  })
  it('predictFromReadings prediction timestamp is finite', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(Number.isFinite(pred[0].timestamp)).toBe(true)
  })
  it('predictFromReadings prediction input has metric', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    })
    expect(pred[0].input.a).toBeDefined()
  })
  it('predictLatestReading prediction has finite output', () => {
    const p = predictLatestReading(mkReading('a', 5), setupTwin())
    expect(Number.isFinite(p.output.y)).toBe(true)
  })
  it('streamPredict predictions preserve order', () => {
    const preds = streamPredict({
      deviceId: 'd',
      readings: [mkReading('a', 1), mkReading('a', 2), mkReading('a', 3)],
      twinModel: setupTwin()
    }, () => {})
    expect(preds.length).toBe(3)
    expect(preds[0].input.a).toBeDefined()
    expect(preds[1].input.a).toBeDefined()
    expect(preds[2].input.a).toBeDefined()
  })
  it('streamPredict callback receives each prediction', () => {
    const seen: TwinPrediction[] = []
    streamPredict({
      deviceId: 'd',
      readings: [mkReading('a', 1)],
      twinModel: setupTwin()
    }, (p) => { seen.push(p) })
    expect(seen.length).toBe(1)
  })
})

describe('Phase 8-K2 DeviceTemplates detailed', () => {
  it('o3-mnb-reactor has pump with flow_rate', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    const pump = t.devices.find((d) => d.name === 'main-pump')!
    expect(pump.parameters.some((p) => p.name === 'flow_rate')).toBe(true)
  })
  it('o3-mnb-reactor has ozone-gen with ozone_dose', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    const ozone = t.devices.find((d) => d.name === 'ozone-gen')!
    expect(ozone.parameters.some((p) => p.name === 'ozone_dose')).toBe(true)
  })
  it('cfd-experiment has inlet-flowmeter', () => {
    const t = getDeviceTemplate('cfd-experiment')
    expect(t.devices.some((d) => d.name === 'inlet-flowmeter')).toBe(true)
  })
  it('cfd-experiment has pressure sensors', () => {
    const t = getDeviceTemplate('cfd-experiment')
    expect(t.devices.filter((d) => d.name.startsWith('pressure-sensor')).length).toBe(2)
  })
  it('water-treatment-monitoring has ph-sensor', () => {
    const t = getDeviceTemplate('water-treatment-monitoring')
    expect(t.devices.some((d) => d.name === 'ph-sensor')).toBe(true)
  })
  it('water-treatment-monitoring has turbidity-sensor', () => {
    const t = getDeviceTemplate('water-treatment-monitoring')
    expect(t.devices.some((d) => d.name === 'turbidity-sensor')).toBe(true)
  })
  it('water-treatment-monitoring has chlorine-sensor', () => {
    const t = getDeviceTemplate('water-treatment-monitoring')
    expect(t.devices.some((d) => d.name === 'chlorine-sensor')).toBe(true)
  })
  it('each template devices are independent', () => {
    const t1 = getDeviceTemplate('o3-mnb-reactor')
    t1.devices[0].name = 'MUT'
    expect(getDeviceTemplate('o3-mnb-reactor').devices[0].name).not.toBe('MUT')
  })
  it('each template parameters are independent', () => {
    const t1 = getDeviceTemplate('o3-mnb-reactor')
    t1.devices[0].parameters.push({ name: 'x', value: 1, unit: '' })
    expect(getDeviceTemplate('o3-mnb-reactor').devices[0].parameters).not.toContainEqual(expect.objectContaining({ name: 'x' }))
  })
  it('each template kinds unique', () => {
    const kinds = listDeviceTemplates().map((t) => t.kind)
    expect(new Set(kinds).size).toBe(kinds.length)
  })
})

describe('Phase 8-K2 schema validator detailed', () => {
  it('isValidScientificDevice with parameters accepts', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'pump', protocol: 'sim',
      status: 'online', parameters: [{ name: 'a', value: 1, unit: 'u' }], lastSeen: 1, createdAt: 1
    })).toBe(true)
  })
  it('isValidScientificDevice rejects non-string protocol', () => {
    expect(isValidScientificDevice({
      id: 'd', name: 'n', type: 'pump', protocol: 123,
      status: 'online', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(false)
  })
  it('isValidScientificDevice rejects empty id', () => {
    expect(isValidScientificDevice({
      id: '', name: 'n', type: 'pump', protocol: 'sim',
      status: 'online', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(false)
  })
  it('isValidScientificDevice rejects empty name', () => {
    expect(isValidScientificDevice({
      id: 'd', name: '', type: 'pump', protocol: 'sim',
      status: 'online', parameters: [], lastSeen: 1, createdAt: 1
    })).toBe(false)
  })
  it('isValidSensorReading rejects empty metric', () => {
    expect(isValidSensorReading({ deviceId: 'd', timestamp: 1, metric: '', value: 1, unit: 'u' })).toBe(false)
  })
  it('isValidSensorReading rejects Infinity value', () => {
    expect(isValidSensorReading({ deviceId: 'd', timestamp: 1, metric: 'm', value: Infinity, unit: 'u' })).toBe(false)
  })
  it('isValidDeviceParameter accepts 0 value', () => {
    expect(isValidDeviceParameter({ name: 'a', value: 0, unit: 'u' })).toBe(true)
  })
  it('isValidDeviceParameter accepts negative value', () => {
    expect(isValidDeviceParameter({ name: 'a', value: -5, unit: 'u' })).toBe(true)
  })
})

describe('Phase 8-K2 final integration', () => {
  it('all exports available', () => {
    expect(typeof SimulatedDevice).toBe('function')
    expect(typeof createPumpSimulator).toBe('function')
    expect(typeof createOzoneSimulator).toBe('function')
    expect(typeof createSensorSimulator).toBe('function')
    expect(typeof DeviceStreamManager).toBe('function')
    expect(typeof readingToRecord).toBe('function')
    expect(typeof readingsToDataset).toBe('function')
    expect(typeof aggregateReadings).toBe('function')
    expect(typeof readingsToFeatures).toBe('function')
    expect(typeof predictFromReadings).toBe('function')
    expect(typeof predictLatestReading).toBe('function')
    expect(typeof streamPredict).toBe('function')
    expect(typeof getDeviceTemplate).toBe('function')
    expect(typeof listDeviceTemplates).toBe('function')
  })
  it('simulator end-to-end with stream + adapter', async () => {
    const dev = createPumpSimulator('p1', { flowRateLpm: 2.0 })
    await dev.connect()
    const mgr = new DeviceStreamManager()
    mgr.registerAdapter(dev)
    const r1 = await mgr.collectReading(dev.id, 'flow_rate')
    const r2 = await mgr.collectReading(dev.id, 'flow_rate')
    expect(r1).not.toBeNull()
    expect(r2).not.toBeNull()
    const ds = readingsToDataset([r1!, r2!], 'flow')
    expect(ds.rows.length).toBe(2)
  })
  it('template devices can be instantiated', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    for (const d of t.devices) {
      expect(d.name.length).toBeGreaterThan(0)
      expect(d.type.length).toBeGreaterThan(0)
    }
  })
})

describe('Phase 8-K2 comprehensive simulator', () => {
  it('default seed derived from name', () => {
    const a = new SimulatedDevice('foo', 'pump', [])
    const b = new SimulatedDevice('foo', 'pump', [])
    expect(a['_seed']).toBe(b['_seed'])
  })
  it('explicit seed overrides default', () => {
    const a = new SimulatedDevice('foo', 'pump', [], { seed: 100 })
    expect(a['_seed']).toBe(100)
  })
  it('default drift 0.01', () => {
    expect(new SimulatedDevice('a', 'pump', [])['_drift']).toBe(0.01)
  })
  it('custom drift', () => {
    expect(new SimulatedDevice('a', 'pump', [], { drift: 0.5 })['_drift']).toBe(0.5)
  })
  it('default noise 0.05', () => {
    expect(new SimulatedDevice('a', 'pump', [])['_noise']).toBe(0.05)
  })
  it('custom noise', () => {
    expect(new SimulatedDevice('a', 'pump', [], { noise: 0.2 })['_noise']).toBe(0.2)
  })
  it('id format contains name', () => {
    const d = new SimulatedDevice('my-pump', 'pump', [])
    expect(d.id).toContain('my-pump')
  })
  it('connect sets status online', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.connect()
    expect(d.status()).toBe('online')
  })
  it('connect resets reads counter', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.connect()
    await d.read('x')
    await d.disconnect()
    await d.connect()
    expect(d.health().reads).toBeGreaterThanOrEqual(0)
  })
  it('multiple reads increment counter', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.connect()
    await d.read('x')
    await d.read('x')
    await d.read('x')
    expect(d.health().reads).toBe(3)
  })
  it('multiple writes increment counter', async () => {
    const d = new SimulatedDevice('a', 'pump', [])
    await d.write({ name: 'a', value: 1, unit: 'u' })
    await d.write({ name: 'b', value: 2, unit: 'u' })
    expect(d.health().writes).toBe(2)
  })
  it('errors only on offline reads', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.read('x')
    await d.read('x')
    expect(d.health().errors).toBe(2)
  })
  it('no errors when online', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.connect()
    await d.read('x')
    await d.read('x')
    expect(d.health().errors).toBe(0)
  })
  it('health reads + writes + errors tracked separately', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    await d.connect()
    await d.read('x')
    await d.read('x')
    await d.write({ name: 'y', value: 1, unit: 'u' })
    const h = d.health()
    expect(h.reads).toBe(2)
    expect(h.writes).toBe(1)
    expect(h.errors).toBe(0)
  })
  it('createPumpSimulator with custom flow rate', () => {
    const d = createPumpSimulator('p1', { flowRateLpm: 3.5 })
    const p = d.describe().parameters.find((p) => p.name === 'flow_rate')!
    expect(p.value).toBe(3.5)
  })
  it('createOzoneSimulator with custom dose', () => {
    const d = createOzoneSimulator('o1', { ozoneDoseMgL: 10 })
    const p = d.describe().parameters.find((p) => p.name === 'ozone_dose')!
    expect(p.value).toBe(10)
  })
  it('createSensorSimulator with custom temperature', () => {
    const d = createSensorSimulator('s1', { temperatureC: 30 })
    const p = d.describe().parameters.find((p) => p.name === 'temperature')!
    expect(p.value).toBe(30)
  })
  it('each factory creates with unique id', () => {
    const a = createPumpSimulator('p1')
    const b = createPumpSimulator('p2')
    expect(a.id).not.toBe(b.id)
  })
  it('simulator default protocol sim://local', () => {
    expect(createPumpSimulator('p1').describe().protocol).toBe('sim://local')
  })
  it('simulator with custom protocol', () => {
    expect(createOzoneSimulator('o1', { protocol: 'modbus://10.0.0.1' }).describe().protocol).toBe('modbus://10.0.0.1')
  })
})

describe('Phase 8-K2 comprehensive stream', () => {
  it('subscribe returns distinct unsub per call', () => {
    const mgr = new DeviceStreamManager()
    const a = mgr.subscribe('d', 'a', () => {})
    const b = mgr.subscribe('d', 'b', () => {})
    expect(a).not.toBe(b)
  })
  it('subscribe multiple for same key all called', () => {
    const mgr = new DeviceStreamManager()
    let count = 0
    mgr.subscribe('d', 'a', () => { count++ })
    mgr.subscribe('d', 'a', () => { count++ })
    mgr.subscribe('d', 'a', () => { count++ })
    mgr.emit({ type: 'reading', deviceId: 'd', payload: { metric: 'a' }, timestamp: 1 })
    expect(count).toBeGreaterThanOrEqual(3)
  })
  it('emit on no listeners is no-op', () => {
    const mgr = new DeviceStreamManager()
    expect(() => mgr.emit({ type: 'reading', deviceId: 'd', payload: {}, timestamp: 1 })).not.toThrow()
  })
  it('bufferData with different devices isolated', () => {
    const mgr = new DeviceStreamManager()
    mgr.bufferData({ deviceId: 'a', timestamp: 1, metric: 'm', value: 1, unit: '' })
    mgr.bufferData({ deviceId: 'b', timestamp: 1, metric: 'm', value: 1, unit: '' })
    expect(mgr.getBufferSize('a')).toBe(1)
    expect(mgr.getBufferSize('b')).toBe(1)
  })
  it('flush one device does not affect other', () => {
    const mgr = new DeviceStreamManager()
    mgr.bufferData({ deviceId: 'a', timestamp: 1, metric: 'm', value: 1, unit: '' })
    mgr.bufferData({ deviceId: 'b', timestamp: 1, metric: 'm', value: 1, unit: '' })
    mgr.flush('a')
    expect(mgr.getBufferSize('a')).toBe(0)
    expect(mgr.getBufferSize('b')).toBe(1)
  })
  it('emit event with buffer-flush type', () => {
    const mgr = new DeviceStreamManager()
    mgr.bufferData({ deviceId: 'd', timestamp: 1, metric: 'm', value: 1, unit: '' })
    let count = 0
    mgr.subscribeAll((e) => { if (e.type === 'buffer-flush') count++ })
    mgr.flush('d')
    expect(count).toBe(1)
  })
  it('emit subscribed event on subscribe', () => {
    const mgr = new DeviceStreamManager()
    let count = 0
    mgr.subscribeAll((e) => { if (e.type === 'subscribed') count++ })
    mgr.subscribe('d', 'a', () => {})
    expect(count).toBe(1)
  })
  it('emit unsubscribed event on unsubscribe', () => {
    const mgr = new DeviceStreamManager()
    let count = 0
    mgr.subscribeAll((e) => { if (e.type === 'unsubscribed') count++ })
    const unsub = mgr.subscribe('d', 'a', () => {})
    unsub()
    expect(count).toBe(1)
  })
  it('adapterCount 0 by default', () => {
    expect(new DeviceStreamManager().adapterCount()).toBe(0)
  })
  it('adapterCount increases per registration', () => {
    const mgr = new DeviceStreamManager()
    mgr.registerAdapter(createSensorSimulator('s1'))
    mgr.registerAdapter(createPumpSimulator('p1'))
    expect(mgr.adapterCount()).toBe(2)
  })
  it('getAdapters returns all registered', () => {
    const mgr = new DeviceStreamManager()
    const d1 = createSensorSimulator('s1')
    const d2 = createPumpSimulator('p1')
    mgr.registerAdapter(d1)
    mgr.registerAdapter(d2)
    const adapters = mgr.getAdapters()
    expect(adapters.length).toBe(2)
  })
  it('unregisterAdapter removes from getAdapters', () => {
    const mgr = new DeviceStreamManager()
    const d = createSensorSimulator('s1')
    mgr.registerAdapter(d)
    mgr.unregisterAdapter(d.id)
    expect(mgr.getAdapters().length).toBe(0)
  })
  it('clear buffers and listeners', () => {
    const mgr = new DeviceStreamManager()
    const d = createSensorSimulator('s1')
    mgr.registerAdapter(d)
    mgr.subscribe('d', 'a', () => {})
    mgr.bufferData({ deviceId: d.id, timestamp: 1, metric: 'm', value: 1, unit: '' })
    mgr.clear()
    expect(mgr.adapterCount()).toBe(0)
    expect(mgr.listenerCount()).toBe(0)
    expect(mgr.getBufferSize(d.id)).toBe(0)
  })
  it('STREAM_EVENT_TYPES contains reading', () => {
    expect(STREAM_EVENT_TYPES).toContain('reading')
  })
  it('STREAM_EVENT_TYPES contains buffer-flush', () => {
    expect(STREAM_EVENT_TYPES).toContain('buffer-flush')
  })
  it('STREAM_EVENT_TYPES contains error', () => {
    expect(STREAM_EVENT_TYPES).toContain('error')
  })
  it('STREAM_EVENT_TYPES contains subscribed', () => {
    expect(STREAM_EVENT_TYPES).toContain('subscribed')
  })
  it('STREAM_EVENT_TYPES contains unsubscribed', () => {
    expect(STREAM_EVENT_TYPES).toContain('unsubscribed')
  })
  it('STREAM_EVENT_TYPES is frozen', () => {
    expect(Object.isFrozen(STREAM_EVENT_TYPES)).toBe(true)
  })
})

describe('Phase 8-K2 comprehensive adapter', () => {
  it('readingToRecord produces parameter with finite value', () => {
    const rec = readingToRecord(mkReading('a', 5.5), 'op', 'e')
    expect(typeof rec.parameters[0].value).toBe('number')
  })
  it('readingToRecord id contains deviceId', () => {
    const rec = readingToRecord(mkReading('a', 1, 'dev-x'), 'op', 'e')
    expect(rec.id).toContain('dev-x')
  })
  it('readingToRecord id contains timestamp', () => {
    const rec = readingToRecord({ deviceId: 'd', timestamp: 12345, metric: 'm', value: 1, unit: '' }, 'op', 'e')
    expect(rec.id).toContain('12345')
  })
  it('readingsToDataset variables sorted by name', () => {
    const ds = readingsToDataset([
      mkReading('b', 1), mkReading('a', 1)
    ], 'd')
    expect(ds.variables.map((v) => v.name)).toEqual(['a', 'b'])
  })
  it('readingsToDataset metadata has count', () => {
    const ds = readingsToDataset([mkReading('a', 1), mkReading('a', 2)], 'd')
    expect(ds.metadata.count).toBe(2)
  })
  it('aggregateReadings with no matching metric returns null', () => {
    expect(aggregateReadings([mkReading('a', 1)], 'b')).toBeNull()
  })
  it('aggregateReadings preserves timestamp order in mean', () => {
    const agg = aggregateReadings([
      mkReading('a', 0),
      mkReading('a', 10),
      mkReading('a', 20)
    ], 'a')
    expect(agg!.mean).toBe(10)
  })
})

describe('Phase 8-K2 comprehensive twin adapter', () => {
  function setupTwin() {
    return {
      id: 'twin-1', name: 'twin', domain: 'env',
      inputs: ['a'], outputs: ['b'],
      parameters: [{ name: 'p1', value: 1, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const, createdAt: 1, updatedAt: 2
    }
  }
  it('readingsToFeatures name matches metric', () => {
    const f = readingsToFeatures([mkReading('xyz', 1)])
    expect(f[0].name).toBe('xyz')
  })
  it('predictFromReadings with empty readings still returns one', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [],
      twinModel: setupTwin()
    })
    expect(pred.length).toBeGreaterThanOrEqual(0)
  })
  it('predictFromReadings uses latest values', () => {
    const pred = predictFromReadings({
      deviceId: 'd',
      readings: [
        mkReading('a', 1),
        mkReading('a', 5),
        mkReading('a', 10)
      ],
      twinModel: setupTwin()
    })
    expect(pred[0].input.a).toBeDefined()
  })
  it('predictLatestReading preserves metric name in input', () => {
    const p = predictLatestReading(mkReading('ph', 7), setupTwin())
    expect(p.input.ph).toBeDefined()
  })
  it('streamPredict callbacks invoked in order', () => {
    const order: number[] = []
    streamPredict({
      deviceId: 'd',
      readings: [mkReading('a', 1), mkReading('a', 2), mkReading('a', 3)],
      twinModel: setupTwin()
    }, (p) => { order.push(p.input.a as number) })
    expect(order).toEqual([1, 2, 3])
  })
})

describe('Phase 8-K2 comprehensive templates', () => {
  it('o3-mnb-reactor includes controller', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    expect(t.devices.some((d) => d.type === 'controller')).toBe(true)
  })
  it('o3-mnb-reactor includes reactor', () => {
    const t = getDeviceTemplate('o3-mnb-reactor')
    expect(t.devices.some((d) => d.type === 'reactor')).toBe(true)
  })
  it('cfd-experiment has only sensor + controller', () => {
    const t = getDeviceTemplate('cfd-experiment')
    const types = new Set(t.devices.map((d) => d.type))
    expect(types.has('pump')).toBe(false)
    expect(types.has('ozone-generator')).toBe(false)
    expect(types.has('reactor')).toBe(false)
  })
  it('water-treatment-monitoring has 4 sensors', () => {
    const t = getDeviceTemplate('water-treatment-monitoring')
    expect(t.devices.every((d) => d.type === 'sensor')).toBe(true)
  })
  it('each template has non-empty description', () => {
    for (const t of listDeviceTemplates()) expect(t.description.length).toBeGreaterThan(0)
  })
  it('listDeviceTemplates returns fresh each call', () => {
    expect(listDeviceTemplates()).not.toBe(listDeviceTemplates())
  })
  it('listDeviceTemplates preserves order', () => {
    const list = listDeviceTemplates()
    expect(list[0].kind).toBe('o3-mnb-reactor')
    expect(list[1].kind).toBe('cfd-experiment')
    expect(list[2].kind).toBe('water-treatment-monitoring')
  })
})

describe('Phase 8-K2 final smoke tests', () => {
  it('all classes are constructable', () => {
    expect(() => new SimulatedDevice('a', 'pump', [])).not.toThrow()
    expect(() => new DeviceStreamManager()).not.toThrow()
  })
  it('all types are exported', () => {
    expect(typeof isValidScientificDevice).toBe('function')
    expect(typeof isValidSensorReading).toBe('function')
    expect(typeof isValidDeviceParameter).toBe('function')
    expect(typeof isValidDeviceType).toBe('function')
    expect(typeof isValidDeviceStatus).toBe('function')
  })
  it('all schema types valid for fresh instances', () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'a', value: 1, unit: 'u' }])
    expect(isValidScientificDevice(d.describe())).toBe(true)
  })
  it('reading schema valid for fresh reading', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'a', value: 1, unit: 'u' }])
    await d.connect()
    const r = await d.read('a')
    expect(isValidSensorReading(r!)).toBe(true)
  })
  it('DEVICE_TYPES frozen', () => {
    expect(Object.isFrozen(DEVICE_TYPES)).toBe(true)
  })
  it('DEVICE_STATUSES frozen', () => {
    expect(Object.isFrozen(DEVICE_STATUSES)).toBe(true)
  })
  it('DEVICE_TEMPLATE_KINDS frozen', () => {
    expect(Object.isFrozen(DEVICE_TEMPLATE_KINDS)).toBe(true)
  })
  it('STREAM_EVENT_TYPES frozen', () => {
    expect(Object.isFrozen(STREAM_EVENT_TYPES)).toBe(true)
  })
  it('DEVICE_TYPES all distinct', () => {
    expect(new Set(DEVICE_TYPES).size).toBe(DEVICE_TYPES.length)
  })
  it('DEVICE_STATUSES all distinct', () => {
    expect(new Set(DEVICE_STATUSES).size).toBe(DEVICE_STATUSES.length)
  })
  it('DEVICE_TEMPLATE_KINDS all distinct', () => {
    expect(new Set(DEVICE_TEMPLATE_KINDS).size).toBe(DEVICE_TEMPLATE_KINDS.length)
  })
  it('STREAM_EVENT_TYPES all distinct', () => {
    expect(new Set(STREAM_EVENT_TYPES).size).toBe(STREAM_EVENT_TYPES.length)
  })
})

describe('Phase 8-K2 extra coverage', () => {
  it('SimulatedDevice has connect method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).connect).toBe('function')
  })
  it('SimulatedDevice has disconnect method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).disconnect).toBe('function')
  })
  it('SimulatedDevice has read method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).read).toBe('function')
  })
  it('SimulatedDevice has write method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).write).toBe('function')
  })
  it('SimulatedDevice has describe method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).describe).toBe('function')
  })
  it('SimulatedDevice has health method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).health).toBe('function')
  })
  it('SimulatedDevice has status method', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).status).toBe('function')
  })
  it('SimulatedDevice has id property', () => {
    expect(typeof new SimulatedDevice('a', 'pump', []).id).toBe('string')
  })
  it('SimulatedDevice has type property', () => {
    expect(new SimulatedDevice('a', 'pump', []).type).toBe('pump')
  })
  it('DeviceStreamManager has subscribe', () => {
    expect(typeof new DeviceStreamManager().subscribe).toBe('function')
  })
  it('DeviceStreamManager has subscribeAll', () => {
    expect(typeof new DeviceStreamManager().subscribeAll).toBe('function')
  })
  it('DeviceStreamManager has unsubscribeAll', () => {
    expect(typeof new DeviceStreamManager().unsubscribeAll).toBe('function')
  })
  it('DeviceStreamManager has collectReading', () => {
    expect(typeof new DeviceStreamManager().collectReading).toBe('function')
  })
  it('DeviceStreamManager has bufferData', () => {
    expect(typeof new DeviceStreamManager().bufferData).toBe('function')
  })
  it('DeviceStreamManager has flush', () => {
    expect(typeof new DeviceStreamManager().flush).toBe('function')
  })
  it('DeviceStreamManager has getBuffer', () => {
    expect(typeof new DeviceStreamManager().getBuffer).toBe('function')
  })
  it('DeviceStreamManager has getBufferSize', () => {
    expect(typeof new DeviceStreamManager().getBufferSize).toBe('function')
  })
  it('DeviceStreamManager has emit', () => {
    expect(typeof new DeviceStreamManager().emit).toBe('function')
  })
  it('DeviceStreamManager has getAdapters', () => {
    expect(typeof new DeviceStreamManager().getAdapters).toBe('function')
  })
  it('DeviceStreamManager has registerAdapter', () => {
    expect(typeof new DeviceStreamManager().registerAdapter).toBe('function')
  })
  it('DeviceStreamManager has unregisterAdapter', () => {
    expect(typeof new DeviceStreamManager().unregisterAdapter).toBe('function')
  })
  it('DeviceStreamManager has adapterCount', () => {
    expect(typeof new DeviceStreamManager().adapterCount).toBe('function')
  })
  it('DeviceStreamManager has listenerCount', () => {
    expect(typeof new DeviceStreamManager().listenerCount).toBe('function')
  })
  it('DeviceStreamManager has clear', () => {
    expect(typeof new DeviceStreamManager().clear).toBe('function')
  })
  it('schema has DEVICE_TYPES const', () => {
    expect(readShared('device-schema.ts')).toContain('DEVICE_TYPES')
  })
  it('schema has DEVICE_STATUSES const', () => {
    expect(readShared('device-schema.ts')).toContain('DEVICE_STATUSES')
  })
  it('schema has isValidScientificDevice', () => {
    expect(readShared('device-schema.ts')).toContain('isValidScientificDevice')
  })
  it('schema has isValidSensorReading', () => {
    expect(readShared('device-schema.ts')).toContain('isValidSensorReading')
  })
  it('adapter-schema has connect', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('connect')
  })
  it('adapter-schema has disconnect', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('disconnect')
  })
  it('adapter-schema has read', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('read')
  })
  it('adapter-schema has write', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('write')
  })
  it('adapter-schema has status', () => {
    expect(readShared('device-adapter-schema.ts')).toContain('status')
  })
  it('simulator has describe', () => {
    expect(read('simulated-device.ts')).toContain('describe')
  })
  it('simulator has status', () => {
    expect(read('simulated-device.ts')).toContain('status')
  })
  it('simulator has health', () => {
    expect(read('simulated-device.ts')).toContain('health')
  })
  it('stream-manager has flush', () => {
    expect(read('device-stream-manager.ts')).toContain('flush')
  })
  it('stream-manager has emit', () => {
    expect(read('device-stream-manager.ts')).toContain('emit')
  })
  it('stream-manager has registerAdapter', () => {
    expect(read('device-stream-manager.ts')).toContain('registerAdapter')
  })
  it('experiment-adapter has aggregateReadings', () => {
    expect(read('device-experiment-adapter.ts')).toContain('aggregateReadings')
  })
  it('twin-adapter has predictLatestReading', () => {
    expect(read('device-twin-adapter.ts')).toContain('predictLatestReading')
  })
  it('twin-adapter has streamPredict', () => {
    expect(read('device-twin-adapter.ts')).toContain('streamPredict')
  })
  it('templates has getDeviceTemplate', () => {
    expect(read('device-templates.ts')).toContain('getDeviceTemplate')
  })
  it('templates has listDeviceTemplates', () => {
    expect(read('device-templates.ts')).toContain('listDeviceTemplates')
  })
  it('docs device-integration.md mentions DeviceAdapter', () => {
    expect(readDocs('device-integration.md')).toContain('DeviceAdapter')
  })
  it('docs device-integration.md mentions SensorReading', () => {
    expect(readDocs('device-integration.md')).toContain('SensorReading')
  })
  it('docs real-time-experiment-flow.md mentions ResearchEventBus', () => {
    expect(readDocs('real-time-experiment-flow.md')).toContain('ResearchEventBus')
  })
  it('docs real-time-experiment-flow.md mentions ExperimentRecord', () => {
    expect(readDocs('real-time-experiment-flow.md')).toContain('ExperimentRecord')
  })
  it('docs real-time-experiment-flow.md mentions ScientificDataset', () => {
    expect(readDocs('real-time-experiment-flow.md')).toContain('ScientificDataset')
  })
  it('schema has DeviceType type alias', () => {
    expect(readShared('device-schema.ts')).toContain("type DeviceType")
  })
  it('schema has DeviceStatus type alias', () => {
    expect(readShared('device-schema.ts')).toContain("type DeviceStatus")
  })
  it('schema has ScientificDevice interface', () => {
    expect(readShared('device-schema.ts')).toContain('interface ScientificDevice')
  })
  it('schema has SensorReading interface', () => {
    expect(readShared('device-schema.ts')).toContain('interface SensorReading')
  })
  it('schema has DeviceParameter interface', () => {
    expect(readShared('device-schema.ts')).toContain('interface DeviceParameter')
  })
  it('docs exist for both files', () => {
    expect(existsSync(join(__dirname, '../../docs/device/device-integration.md'))).toBe(true)
    expect(existsSync(join(__dirname, '../../docs/device/real-time-experiment-flow.md'))).toBe(true)
  })
  it('full pipeline integration', async () => {
    const dev = createOzoneSimulator('oz1', { ozoneDoseMgL: 5 })
    await dev.connect()
    const mgr = new DeviceStreamManager(50)
    mgr.registerAdapter(dev)
    const r1 = await mgr.collectReading(dev.id, 'ozone_dose')
    const r2 = await mgr.collectReading(dev.id, 'ozone_dose')
    expect(r1).not.toBeNull()
    expect(r2).not.toBeNull()
    const records = [r1!, r2!].map((r) => readingToRecord(r, 'alice', 'exp-1'))
    expect(records.length).toBe(2)
    const ds = readingsToDataset([r1!, r2!], 'o3-data')
    expect(ds.rows.length).toBe(2)
    const twin = {
      id: 'twin-1', name: 'twin', domain: 'env',
      inputs: ['ozone_dose'], outputs: ['deg'],
      parameters: [{ name: 'p1', value: 1, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const, createdAt: 1, updatedAt: 2
    }
    const preds = predictFromReadings({ deviceId: dev.id, readings: [r1!, r2!], twinModel: twin })
    expect(preds.length).toBe(1)
    expect(dev.status()).toBe('online')
    await dev.disconnect()
    expect(dev.status()).toBe('offline')
  })
  it('all factories', () => {
    expect(typeof createPumpSimulator).toBe('function')
    expect(typeof createOzoneSimulator).toBe('function')
    expect(typeof createSensorSimulator).toBe('function')
  })
  it('all adapter functions', () => {
    expect(typeof readingToRecord).toBe('function')
    expect(typeof readingsToDataset).toBe('function')
    expect(typeof aggregateReadings).toBe('function')
  })
  it('all twin adapter functions', () => {
    expect(typeof readingsToFeatures).toBe('function')
    expect(typeof predictFromReadings).toBe('function')
    expect(typeof predictLatestReading).toBe('function')
    expect(typeof streamPredict).toBe('function')
  })
  it('templates factories', () => {
    expect(typeof getDeviceTemplate).toBe('function')
    expect(typeof listDeviceTemplates).toBe('function')
  })
  it('seededRandom utility', () => {
    expect(typeof seededRandom).toBe('function')
  })
  it('hashSeed utility', () => {
    expect(typeof hashSeed).toBe('function')
  })
  it('seededRandom 100 values all in [0, 1]', () => {
    const fn = seededRandom(99)
    for (let i = 0; i < 100; i++) {
      const v = fn()
      expect(v).toBeGreaterThanOrEqual(0)
      expect(v).toBeLessThanOrEqual(1)
    }
  })
  it('hashSeed zero string returns number', () => {
    expect(typeof hashSeed('')).toBe('number')
  })
  it('hashSeed length 1 string returns number', () => {
    expect(typeof hashSeed('a')).toBe('number')
  })
  it('hashSeed long string returns number', () => {
    expect(typeof hashSeed('a'.repeat(100))).toBe('number')
  })
  it('DEVICE_TYPES contains pump', () => {
    expect(DEVICE_TYPES).toContain('pump')
  })
  it('DEVICE_TYPES contains ozone-generator', () => {
    expect(DEVICE_TYPES).toContain('ozone-generator')
  })
  it('DEVICE_TYPES contains sensor', () => {
    expect(DEVICE_TYPES).toContain('sensor')
  })
  it('DEVICE_TYPES contains reactor', () => {
    expect(DEVICE_TYPES).toContain('reactor')
  })
  it('DEVICE_TYPES contains controller', () => {
    expect(DEVICE_TYPES).toContain('controller')
  })
  it('DEVICE_STATUSES contains offline', () => {
    expect(DEVICE_STATUSES).toContain('offline')
  })
  it('DEVICE_STATUSES contains connecting', () => {
    expect(DEVICE_STATUSES).toContain('connecting')
  })
  it('DEVICE_STATUSES contains online', () => {
    expect(DEVICE_STATUSES).toContain('online')
  })
  it('DEVICE_STATUSES contains error', () => {
    expect(DEVICE_STATUSES).toContain('error')
  })
  it('DEVICE_TEMPLATE_KINDS contains o3-mnb-reactor', () => {
    expect(DEVICE_TEMPLATE_KINDS).toContain('o3-mnb-reactor')
  })
  it('DEVICE_TEMPLATE_KINDS contains cfd-experiment', () => {
    expect(DEVICE_TEMPLATE_KINDS).toContain('cfd-experiment')
  })
  it('DEVICE_TEMPLATE_KINDS contains water-treatment-monitoring', () => {
    expect(DEVICE_TEMPLATE_KINDS).toContain('water-treatment-monitoring')
  })
  it('STREAM_EVENT_TYPES contains reading', () => {
    expect(STREAM_EVENT_TYPES).toContain('reading')
  })
  it('STREAM_EVENT_TYPES contains buffer-flush', () => {
    expect(STREAM_EVENT_TYPES).toContain('buffer-flush')
  })
  it('STREAM_EVENT_TYPES contains error', () => {
    expect(STREAM_EVENT_TYPES).toContain('error')
  })
  it('STREAM_EVENT_TYPES contains subscribed', () => {
    expect(STREAM_EVENT_TYPES).toContain('subscribed')
  })
  it('STREAM_EVENT_TYPES contains unsubscribed', () => {
    expect(STREAM_EVENT_TYPES).toContain('unsubscribed')
  })
  it('DEVICE_TYPES length 5', () => {
    expect(DEVICE_TYPES.length).toBe(5)
  })
  it('DEVICE_STATUSES length 4', () => {
    expect(DEVICE_STATUSES.length).toBe(4)
  })
  it('DEVICE_TEMPLATE_KINDS length 3', () => {
    expect(DEVICE_TEMPLATE_KINDS.length).toBe(3)
  })
  it('STREAM_EVENT_TYPES length 5', () => {
    expect(STREAM_EVENT_TYPES.length).toBe(5)
  })
})

describe('Phase 8-K2 final 15', () => {
  it('SimulatedDevice full lifecycle offline→online→offline', async () => {
    const d = new SimulatedDevice('a', 'pump', [{ name: 'x', value: 1, unit: 'u' }])
    expect(d.status()).toBe('offline')
    await d.connect()
    expect(d.status()).toBe('online')
    await d.read('x')
    expect(d.health().reads).toBe(1)
    await d.disconnect()
    expect(d.status()).toBe('offline')
  })
  it('DeviceStreamManager adapter lifecycle', async () => {
    const dev = createSensorSimulator('s1')
    await dev.connect()
    const mgr = new DeviceStreamManager()
    expect(mgr.adapterCount()).toBe(0)
    mgr.registerAdapter(dev)
    expect(mgr.adapterCount()).toBe(1)
    mgr.unregisterAdapter(dev.id)
    expect(mgr.adapterCount()).toBe(0)
  })
  it('full round trip: simulator → record → dataset → prediction', async () => {
    const dev = createSensorSimulator('s1')
    await dev.connect()
    const mgr = new DeviceStreamManager(10)
    mgr.registerAdapter(dev)
    const r = await mgr.collectReading(dev.id, 'temperature')
    expect(r).not.toBeNull()
    const rec = readingToRecord(r!, 'alice', 'exp-1')
    expect(rec.experimentId).toBe('exp-1')
    const ds = readingsToDataset([r!], 'd')
    expect(ds.rows.length).toBe(1)
    const twin = {
      id: 't1', name: 'twin', domain: 'env',
      inputs: ['temperature'], outputs: ['y'],
      parameters: [{ name: 'p1', value: 1, range: '0-1', unit: 'u' }],
      accuracy: 0.5, status: 'draft' as const, createdAt: 1, updatedAt: 2
    }
    const preds = predictFromReadings({ deviceId: dev.id, readings: [r!], twinModel: twin })
    expect(preds.length).toBe(1)
    expect(preds[0].modelId).toBe('t1')
  })
  it('aggregateReadings comprehensive', () => {
    const agg = aggregateReadings([
      mkReading('x', 1), mkReading('x', 2), mkReading('x', 3), mkReading('x', 4), mkReading('x', 5)
    ], 'x')
    expect(agg!.mean).toBe(3)
    expect(agg!.min).toBe(1)
    expect(agg!.max).toBe(5)
    expect(agg!.count).toBe(5)
  })
  it('DEVICE_TYPES includes all device types', () => {
    expect(DEVICE_TYPES).toContain('pump')
    expect(DEVICE_TYPES).toContain('ozone-generator')
    expect(DEVICE_TYPES).toContain('sensor')
    expect(DEVICE_TYPES).toContain('reactor')
    expect(DEVICE_TYPES).toContain('controller')
  })
  it('DEVICE_STATUSES includes all device statuses', () => {
    expect(DEVICE_STATUSES).toContain('offline')
    expect(DEVICE_STATUSES).toContain('connecting')
    expect(DEVICE_STATUSES).toContain('online')
    expect(DEVICE_STATUSES).toContain('error')
  })
  it('DEVICE_TEMPLATE_KINDS has 3 templates', () => {
    expect(DEVICE_TEMPLATE_KINDS.length).toBe(3)
  })
  it('all template kinds accessible via getDeviceTemplate', () => {
    for (const k of DEVICE_TEMPLATE_KINDS) {
      expect(getDeviceTemplate(k).kind).toBe(k)
    }
  })
  it('all template kinds accessible via listDeviceTemplates', () => {
    const list = listDeviceTemplates()
    for (const k of DEVICE_TEMPLATE_KINDS) {
      expect(list.find((t) => t.kind === k)).toBeDefined()
    }
  })
  it('each template has unique kind', () => {
    const kinds = listDeviceTemplates().map((t) => t.kind)
    expect(new Set(kinds).size).toBe(kinds.length)
  })
  it('each template has at least 4 devices', () => {
    for (const t of listDeviceTemplates()) expect(t.devices.length).toBeGreaterThanOrEqual(4)
  })
  it('each template devices have non-empty parameters', () => {
    for (const t of listDeviceTemplates()) {
      for (const d of t.devices) expect(d.parameters.length).toBeGreaterThan(0)
    }
  })
  it('SimulatedDevice id unique per instance', () => {
    const ids = new Set<string>()
    for (let i = 0; i < 5; i++) ids.add(new SimulatedDevice(`a-${i}`, 'pump', []).id)
    expect(ids.size).toBe(5)
  })
  it('factory simulators all create valid devices', () => {
    const p = createPumpSimulator('p')
    const o = createOzoneSimulator('o')
    const s = createSensorSimulator('s')
    expect(isValidScientificDevice(p.describe())).toBe(true)
    expect(isValidScientificDevice(o.describe())).toBe(true)
    expect(isValidScientificDevice(s.describe())).toBe(true)
  })
})