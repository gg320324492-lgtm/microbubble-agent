import { describe, expect, it } from 'vitest'
import electronViteConfig from '../../electron.vite.config'

describe('Electron main-process bundle', () => {
  it('bundles the ESM-only electron-store dependency instead of requiring it from CommonJS', () => {
    const config = electronViteConfig as {
      main?: {
        plugins?: Array<{
          config?: (config: Record<string, unknown>) => void
        } | null>
      }
    }
    const externalizePlugin = config.main?.plugins?.find(
      (plugin) => plugin?.config && 'name' in plugin && plugin.name === 'vite:externalize-deps'
    )
    const resolved: Record<string, unknown> = {}

    expect(externalizePlugin, 'main build must keep the externalize-deps plugin').toBeDefined()
    externalizePlugin!.config!(resolved)

    const external = (
      resolved.build as { rollupOptions?: { external?: Array<string | RegExp> } } | undefined
    )?.rollupOptions?.external ?? []
    expect(external).not.toContain('electron-store')
    expect(external.some((entry) => entry instanceof RegExp && entry.test('electron-store/index.js'))).toBe(false)
  })

  it('wraps CommonJS dependencies deterministically instead of using auto cycle detection', () => {
    const config = electronViteConfig as {
      main?: {
        build?: {
          commonjsOptions?: { strictRequires?: boolean | string }
        }
      }
    }

    expect(config.main?.build?.commonjsOptions?.strictRequires).toBe(true)
  })
})
