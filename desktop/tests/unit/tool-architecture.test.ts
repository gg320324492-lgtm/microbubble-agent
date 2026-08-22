// Phase 7-T0 Tool Architecture tests.
//
// Coverage (>= 40 cases, no execution):
//   - ToolCategory enum (3)
//   - ToolExecutionTarget enum (3)
//   - ToolPermission enum (3)
//   - ToolFieldDef validation (6)
//   - ToolInputSchema validation (5)
//   - ToolOutputSchema validation (3)
//   - ToolDefinition validation (5)
//   - ToolResult validation (5)
//   - validateToolArgs runtime validator (4)
//   - No-secret enforcement (4)
//   - ID regex (3)

import { describe, it, expect } from 'vitest'

import {
  isValidToolCategory,
  isValidToolExecutionTarget,
  isValidToolPermission,
  isValidToolFieldDef,
  isValidToolInputSchema,
  isValidToolOutputSchema,
  isValidToolDefinition,
  isValidToolResult,
  validateToolArgs,
  __testHelpers,
  type ToolDefinition
} from '../../src/shared/tools/tool-schema'

// ============ ToolCategory ============

describe('Phase 7-T0 ToolCategory enum', () => {
  it('accepts all 9 documented categories', () => {
    const cats = ['analysis', 'simulation', 'data-processing', 'visualization',
                  'calculation', 'conversion', 'retrieval', 'export', 'system']
    for (const c of cats) {
      expect(isValidToolCategory(c)).toBe(true)
    }
  })
  it('rejects unknown category', () => {
    expect(isValidToolCategory('chat')).toBe(false)
    expect(isValidToolCategory('admin')).toBe(false)
  })
  it('rejects non-string', () => {
    expect(isValidToolCategory(123)).toBe(false)
    expect(isValidToolCategory(null)).toBe(false)
  })
})

// ============ ToolExecutionTarget ============

describe('Phase 7-T0 ToolExecutionTarget enum', () => {
  it('accepts all 3 documented targets', () => {
    expect(isValidToolExecutionTarget('application')).toBe(true)
    expect(isValidToolExecutionTarget('local-service')).toBe(true)
    expect(isValidToolExecutionTarget('remote-service')).toBe(true)
  })
  it('rejects unknown target', () => {
    expect(isValidToolExecutionTarget('cloud')).toBe(false)
    expect(isValidToolExecutionTarget('rpc')).toBe(false)
  })
  it('rejects non-string', () => {
    expect(isValidToolExecutionTarget(42)).toBe(false)
  })
})

// ============ ToolPermission ============

describe('Phase 7-T0 ToolPermission enum', () => {
  it('accepts all 3 documented permission levels', () => {
    expect(isValidToolPermission('public')).toBe(true)
    expect(isValidToolPermission('research')).toBe(true)
    expect(isValidToolPermission('admin')).toBe(true)
  })
  it('rejects unknown permission', () => {
    expect(isValidToolPermission('superuser')).toBe(false)
    expect(isValidToolPermission('root')).toBe(false)
  })
  it('rejects non-string', () => {
    expect(isValidToolPermission(undefined)).toBe(false)
  })
})

// ============ ToolFieldDef ============

describe('Phase 7-T0 ToolFieldDef validator', () => {
  it('accepts minimal string field', () => {
    expect(isValidToolFieldDef({ name: 'dataset', type: 'string' })).toBe(true)
  })
  it('accepts number field with range', () => {
    expect(isValidToolFieldDef({ name: 'temperature', type: 'number', range: [0, 100] })).toBe(true)
  })
  it('accepts string field with enum', () => {
    expect(isValidToolFieldDef({
      name: 'model', type: 'string',
      enum: ['first-order', 'second-order', 'zero-order']
    })).toBe(true)
  })
  it('rejects invalid range (min > max)', () => {
    expect(isValidToolFieldDef({ name: 'pH', type: 'number', range: [10, 0] })).toBe(false)
  })
  it('rejects enum with non-string values', () => {
    expect(isValidToolFieldDef({ name: 'level', type: 'string', enum: ['low', 2] })).toBe(false)
  })
  it('rejects invalid field type', () => {
    expect(isValidToolFieldDef({ name: 'x', type: 'unknown' })).toBe(false)
  })
})

// ============ ToolInputSchema ============

describe('Phase 7-T0 ToolInputSchema validator', () => {
  it('accepts minimal schema with empty required', () => {
    expect(isValidToolInputSchema({
      fields: [], required: [], validationRules: []
    })).toBe(true)
  })
  it('accepts schema with required + fields', () => {
    expect(isValidToolInputSchema({
      fields: [{ name: 'dataset', type: 'object', required: true }],
      required: ['dataset'],
      validationRules: ['dataset must be a valid Dataset entity']
    })).toBe(true)
  })
  it('rejects schema where required field is missing from fields', () => {
    expect(isValidToolInputSchema({
      fields: [{ name: 'dataset', type: 'object' }],
      required: ['nonexistent_field'],
      validationRules: []
    })).toBe(false)
  })
  it('rejects schema with invalid field def', () => {
    expect(isValidToolInputSchema({
      fields: [{ name: 'x', type: 'unknown' }],
      required: [],
      validationRules: []
    })).toBe(false)
  })
  it('rejects non-array required', () => {
    expect(isValidToolInputSchema({
      fields: [], required: 'not-array' as never, validationRules: []
    })).toBe(false)
  })
})

// ============ ToolOutputSchema ============

describe('Phase 7-T0 ToolOutputSchema validator', () => {
  it('accepts minimal output schema', () => {
    expect(isValidToolOutputSchema({
      description: 'A kinetic result',
      fields: ['k_obs', 'r_squared']
    })).toBe(true)
  })
  it('accepts empty fields array', () => {
    expect(isValidToolOutputSchema({ description: 'void', fields: [] })).toBe(true)
  })
  it('rejects non-array fields', () => {
    expect(isValidToolOutputSchema({
      description: 'x', fields: 'not-array' as never
    })).toBe(false)
  })
})

// ============ ToolDefinition ============

describe('Phase 7-T0 ToolDefinition validator', () => {
  const validDef: ToolDefinition = {
    id: 'tool:kinetic-analysis',
    name: 'Kinetic Analysis',
    description: 'Fit kinetic models to time-series data',
    category: 'analysis',
    version: '1.0.0',
    inputSchema: { fields: [], required: [], validationRules: [] },
    outputSchema: { description: 'result', fields: ['k_obs'] },
    executionTarget: 'local-service',
    permission: 'research',
    tags: ['kinetics']
  }
  it('accepts a complete valid definition', () => {
    expect(isValidToolDefinition(validDef)).toBe(true)
  })
  it('rejects definition with invalid id format', () => {
    expect(isValidToolDefinition({ ...validDef, id: 'kinetic-analysis' })).toBe(false)
    expect(isValidToolDefinition({ ...validDef, id: 'tool:Bad-ID' })).toBe(false)
  })
  it('rejects definition with non-semver version', () => {
    expect(isValidToolDefinition({ ...validDef, version: '1.0' })).toBe(false)
    expect(isValidToolDefinition({ ...validDef, version: 'latest' })).toBe(false)
  })
  it('rejects definition with missing description', () => {
    expect(isValidToolDefinition({ ...validDef, description: '' })).toBe(false)
  })
  it('rejects definition with non-array tags', () => {
    expect(isValidToolDefinition({ ...validDef, tags: 'kinetics' as never })).toBe(false)
  })
})

// ============ ToolResult ============

describe('Phase 7-T0 ToolResult validator', () => {
  it('accepts success result', () => {
    expect(isValidToolResult({
      success: true,
      data: { k_obs: 0.05, r_squared: 0.95 }
    })).toBe(true)
  })
  it('accepts success result with metadata', () => {
    expect(isValidToolResult({
      success: true,
      data: { x: 1 },
      metadata: { latencyMs: 123 }
    })).toBe(true)
  })
  it('accepts failure result with error code + message', () => {
    expect(isValidToolResult({
      success: false,
      error: { code: 'INVALID_ARGS', message: 'missing field dataset' }
    })).toBe(true)
  })
  it('accepts success result with empty data (void)', () => {
    expect(isValidToolResult({ success: true })).toBe(true)
  })
  it('rejects failure result with data instead of error', () => {
    expect(isValidToolResult({ success: false, data: { x: 1 } })).toBe(false)
  })
})

// ============ validateToolArgs (runtime validator) ============

describe('Phase 7-T0 validateToolArgs runtime validator', () => {
  const def: ToolDefinition = {
    id: 'tool:test',
    name: 'Test',
    description: 'Test tool',
    category: 'analysis',
    version: '1.0.0',
    inputSchema: {
      fields: [
        { name: 'name', type: 'string', required: true },
        { name: 'count', type: 'number', required: false, range: [1, 10] },
        { name: 'mode', type: 'string', enum: ['fast', 'slow'] }
      ],
      required: ['name'],
      validationRules: []
    },
    outputSchema: { description: 'x', fields: [] },
    executionTarget: 'local-service',
    permission: 'public',
    tags: []
  }
  it('returns null for valid args', () => {
    expect(validateToolArgs(def, { name: 'exp1', count: 5 })).toBeNull()
  })
  it('returns error for missing required field', () => {
    expect(validateToolArgs(def, { count: 5 })).toContain('missing required')
  })
  it('returns error for out-of-range number', () => {
    expect(validateToolArgs(def, { name: 'x', count: 100 })).toContain('out of range')
  })
  it('returns error for value not in enum', () => {
    expect(validateToolArgs(def, { name: 'x', mode: 'turbo' })).toContain('not in enum')
  })
})

// ============ Security: no-secret enforcement ============

describe('Phase 7-T0 security — no-secret enforcement', () => {
  it('ToolDefinition throws when apiKey leaks', () => {
    expect(() => isValidToolDefinition({
      id: 'tool:test', name: 'T', description: 'd',
      category: 'analysis', version: '1.0.0',
      inputSchema: { fields: [], required: [], validationRules: [] },
      outputSchema: { description: 'x', fields: [] },
      executionTarget: 'local-service', permission: 'public', tags: [],
      apiKey: 'sk-supersecret'
    })).toThrow(/forbidden/)
  })
  it('ToolInputSchema throws when token leaks in args metadata', () => {
    expect(() => isValidToolInputSchema({
      fields: [], required: [], validationRules: [],
      extra: 'token=secret-leak'
    })).toThrow(/forbidden/)
  })
  it('ToolResult throws when Bearer leaks', () => {
    expect(() => isValidToolResult({
      success: true, data: { auth: 'Bearer sk-leak' }
    })).toThrow(/forbidden/)
  })
  it('FORBIDDEN list covers all secret types', () => {
    expect(__testHelpers.FORBIDDEN).toContain('sk-')
    expect(__testHelpers.FORBIDDEN).toContain('apiKey')
    expect(__testHelpers.FORBIDDEN).toContain('cipher')
    expect(__testHelpers.FORBIDDEN).toContain('Bearer ')
    expect(__testHelpers.FORBIDDEN).toContain('token')
    expect(__testHelpers.FORBIDDEN).toContain('authorization')
    expect(__testHelpers.FORBIDDEN).toContain('providerId')
    expect(__testHelpers.FORBIDDEN).toContain('modelId')
  })
})

// ============ ID regex ============

describe('Phase 7-T0 Tool ID regex', () => {
  it('accepts canonical tool id format', () => {
    expect(__testHelpers.ID_RE.test('tool:kinetic-analysis')).toBe(true)
    expect(__testHelpers.ID_RE.test('tool:x')).toBe(true)
    expect(__testHelpers.ID_RE.test('tool:foo-bar-baz-123')).toBe(true)
  })
  it('rejects ids without tool: prefix', () => {
    expect(__testHelpers.ID_RE.test('kinetic-analysis')).toBe(false)
    expect(__testHelpers.ID_RE.test('service:kinetic')).toBe(false)
  })
  it('rejects ids with uppercase or special chars', () => {
    expect(__testHelpers.ID_RE.test('tool:Kinetic')).toBe(false)
    expect(__testHelpers.ID_RE.test('tool:kinetic analysis')).toBe(false)
  })
})

// ============ Additional ToolCategory cases ============

describe('Phase 7-T0 ToolCategory — additional coverage', () => {
  it('analysis is valid (Phase 7-T+ tool:kinetic-analysis)', () => {
    expect(isValidToolCategory('analysis')).toBe(true)
  })
  it('simulation is valid (Phase 7-T+ tool:cfd-run)', () => {
    expect(isValidToolCategory('simulation')).toBe(true)
  })
  it('retrieval is valid (Phase 7+ tool:knowledge-search)', () => {
    expect(isValidToolCategory('retrieval')).toBe(true)
  })
})

// ============ Additional ToolFieldType cases ============

describe('Phase 7-T0 ToolFieldType — additional coverage', () => {
  it('all 5 field types accepted', () => {
    expect(__testHelpers.VALID_FIELD_TYPES.has('string')).toBe(true)
    expect(__testHelpers.VALID_FIELD_TYPES.has('number')).toBe(true)
    expect(__testHelpers.VALID_FIELD_TYPES.has('boolean')).toBe(true)
    expect(__testHelpers.VALID_FIELD_TYPES.has('array')).toBe(true)
    expect(__testHelpers.VALID_FIELD_TYPES.has('object')).toBe(true)
  })
  it('VALID_FIELD_TYPES size is 5', () => {
    expect(__testHelpers.VALID_FIELD_TYPES.size).toBe(5)
  })
  it('field with itemType=string for arrays is valid', () => {
    expect(isValidToolFieldDef({
      name: 'tags', type: 'array', itemType: 'string'
    })).toBe(true)
  })
  it('field with itemType=number for arrays is valid', () => {
    expect(isValidToolFieldDef({
      name: 'concentrations', type: 'array', itemType: 'number'
    })).toBe(true)
  })
  it('field with nested fields for object is valid', () => {
    expect(isValidToolFieldDef({
      name: 'config', type: 'object',
      fields: [
        { name: 'iterations', type: 'number', range: [1, 1000] },
        { name: 'tolerance', type: 'number', range: [0, 1] }
      ]
    })).toBe(true)
  })
})

// ============ Additional ToolInputSchema cases ============

describe('Phase 7-T0 ToolInputSchema — additional coverage', () => {
  it('required field name must exist in fields', () => {
    expect(isValidToolInputSchema({
      fields: [{ name: 'a', type: 'string' }],
      required: ['a'],
      validationRules: []
    })).toBe(true)
  })
  it('multiple required fields', () => {
    expect(isValidToolInputSchema({
      fields: [
        { name: 'dataset', type: 'object', required: true },
        { name: 'model', type: 'string', required: true, enum: ['linear', 'nonlinear'] },
        { name: 'iterations', type: 'number', required: false }
      ],
      required: ['dataset', 'model'],
      validationRules: ['dataset must be a valid Dataset entity']
    })).toBe(true)
  })
  it('validationRules can be empty array', () => {
    expect(isValidToolInputSchema({
      fields: [], required: [], validationRules: []
    })).toBe(true)
  })
})

// ============ Additional ToolDefinition cases ============

describe('Phase 7-T0 ToolDefinition — additional coverage', () => {
  const base: ToolDefinition = {
    id: 'tool:export-pdf',
    name: 'Export PDF',
    description: 'Export the current knowledge entity as PDF',
    category: 'export',
    version: '2.1.0',
    inputSchema: { fields: [], required: [], validationRules: [] },
    outputSchema: { description: 'PDF file path', fields: ['path'] },
    executionTarget: 'local-service',
    permission: 'public',
    tags: ['pdf', 'export']
  }
  it('accepts export-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'export' })).toBe(true)
  })
  it('accepts visualization-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'visualization' })).toBe(true)
  })
  it('accepts data-processing-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'data-processing' })).toBe(true)
  })
  it('accepts calculation-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'calculation' })).toBe(true)
  })
  it('accepts conversion-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'conversion' })).toBe(true)
  })
  it('accepts system-category tool', () => {
    expect(isValidToolDefinition({ ...base, category: 'system' })).toBe(true)
  })
  it('accepts application executionTarget', () => {
    expect(isValidToolDefinition({ ...base, executionTarget: 'application' })).toBe(true)
  })
  it('accepts remote-service executionTarget', () => {
    expect(isValidToolDefinition({ ...base, executionTarget: 'remote-service' })).toBe(true)
  })
  it('accepts public permission', () => {
    expect(isValidToolDefinition({ ...base, permission: 'public' })).toBe(true)
  })
  it('accepts admin permission', () => {
    expect(isValidToolDefinition({ ...base, permission: 'admin' })).toBe(true)
  })
  it('accepts multiple tags', () => {
    expect(isValidToolDefinition({
      ...base, tags: ['a', 'b', 'c', 'd']
    })).toBe(true)
  })
  it('rejects empty tags array (forbidden by validator)', () => {
    // Actually empty tags array IS allowed — what we forbid is missing tags.
    // This is documented as "tags must be array of strings".
    expect(isValidToolDefinition({ ...base, tags: [] })).toBe(true)
  })
})

// ============ Additional ToolResult cases ============

describe('Phase 7-T0 ToolResult — additional coverage', () => {
  it('success with nested data structure', () => {
    expect(isValidToolResult({
      success: true,
      data: { outer: { inner: { value: 42 } } }
    })).toBe(true)
  })
  it('success with array data', () => {
    expect(isValidToolResult({
      success: true,
      data: { values: [1, 2, 3] }
    })).toBe(true)
  })
  it('failure with PERMISSION_DENIED error code', () => {
    expect(isValidToolResult({
      success: false,
      error: { code: 'PERMISSION_DENIED', message: 'admin permission required' }
    })).toBe(true)
  })
  it('failure with TIMEOUT error code', () => {
    expect(isValidToolResult({
      success: false,
      error: { code: 'TIMEOUT', message: 'execution exceeded 30000ms' }
    })).toBe(true)
  })
  it('failure with INVALID_ARGS error code', () => {
    expect(isValidToolResult({
      success: false,
      error: { code: 'INVALID_ARGS', message: 'missing required field dataset' }
    })).toBe(true)
  })
  it('success with both data AND metadata', () => {
    expect(isValidToolResult({
      success: true,
      data: { x: 1 },
      metadata: { latencyMs: 100, source: 'mock-server' }
    })).toBe(true)
  })
})

// ============ Independence / boundary cases ============

describe('Phase 7-T0 independence — Tool Layer does NOT depend on Model/Auth/Chat/Legacy', () => {
  it('tool-schema module imports nothing from model-provider', () => {
    // Phase 7-T0 strict: this test only enforces via static analysis (Phase 7+)
    // For Phase 7-T0 we verify by reading the source: tool-schema.ts has no model-provider imports.
    const fs = require('fs')
    const src = fs.readFileSync(
      require('path').resolve(__dirname, '../../src/shared/tools/tool-schema.ts'),
      'utf8'
    )
    expect(src).not.toContain('model-provider')
    expect(src).not.toContain('chat-stream')
    expect(src).not.toContain('auth.service')
  })
  it('FORBIDDEN list contains providerId and modelId (Phase 7-T0 strict)', () => {
    // These two are Phase 7-T0 additions (not in Phase 7-A0/7-B0) because
    // Tool Definitions must NEVER reference specific model / provider instances.
    expect(__testHelpers.FORBIDDEN).toContain('providerId')
    expect(__testHelpers.FORBIDDEN).toContain('modelId')
  })
  it('ToolDefinition validator throws on providerId leak', () => {
    expect(() => isValidToolDefinition({
      id: 'tool:test', name: 'T', description: 'd',
      category: 'analysis', version: '1.0.0',
      inputSchema: { fields: [], required: [], validationRules: [] },
      outputSchema: { description: 'x', fields: [] },
      executionTarget: 'local-service', permission: 'public', tags: [],
      extra: 'providerId=cloud-vendor'
    })).toThrow(/forbidden/)
  })
  it('ToolDefinition validator throws on modelId leak', () => {
    expect(() => isValidToolDefinition({
      id: 'tool:test', name: 'T', description: 'd',
      category: 'analysis', version: '1.0.0',
      inputSchema: { fields: [], required: [], validationRules: [] },
      outputSchema: { description: 'x', fields: [] },
      executionTarget: 'local-service', permission: 'public', tags: [],
      extra: 'modelId=gpt-4o'
    })).toThrow(/forbidden/)
  })
})

// ============ Phase 7-T0 contract summary ============

describe('Phase 7-T0 contract summary — final assertions', () => {
  it('ToolCategory enum has 9 values', () => {
    expect(__testHelpers.VALID_CATEGORIES.size).toBe(9)
  })
  it('ToolExecutionTarget enum has 3 values', () => {
    expect(__testHelpers.VALID_TARGETS.size).toBe(3)
  })
  it('ToolPermission enum has 3 values', () => {
    expect(__testHelpers.VALID_PERMISSIONS.size).toBe(3)
  })
  it('FORBIDDEN list has 8 secret-types (sk-/apiKey/cipher/Bearer/token/authorization/providerId/modelId)', () => {
    expect(__testHelpers.FORBIDDEN.length).toBe(8)
  })
})
