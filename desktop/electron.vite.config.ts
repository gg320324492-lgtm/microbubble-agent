import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'
import { copyFileSync, mkdirSync, readdirSync } from 'node:fs'

/** Phase 10.6 hotfix: copy SQL schema files into out/main/database/schema/
 *  electron-vite 不打包 .sql 文件, 但 MigrationManager.resolveSchemaDir() 用
 *  out/main/database/schema 路径 (在 asar 内). 必须在 build 后确保该目录存在. */
function copySchemaPlugin() {
  return {
    name: 'copy-schema-to-out-main',
    closeBundle() {
      const srcDir = resolve(__dirname, 'src/main/database/schema')
      const destDir = resolve(__dirname, 'out/main/database/schema')
      try {
        mkdirSync(destDir, { recursive: true })
        for (const f of readdirSync(srcDir)) {
          if (f.endsWith('.sql')) {
            copyFileSync(resolve(srcDir, f), resolve(destDir, f))
          }
        }
        console.log(`[copy-schema] copied ${readdirSync(srcDir).length} SQL files to out/main/database/schema/`)
      } catch (e) {
        console.error('[copy-schema] failed:', e)
      }
    }
  }
}

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin({ exclude: ['electron-store'] }), copySchemaPlugin()],
    build: {
      outDir: 'out/main',
      commonjsOptions: {
        // `auto` detects cycles while modules load and can change the bundle graph
        // between cold and warm builds. Wrap every CommonJS module deterministically.
        strictRequires: true
      },
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/main/index.ts')
        }
      }
    },
    resolve: {
      alias: {
        '@shared': resolve(__dirname, 'src/shared')
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      outDir: 'out/preload',
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/preload/index.ts')
        }
      }
    },
    resolve: {
      alias: {
        '@shared': resolve(__dirname, 'src/shared')
      }
    }
  },
  renderer: {
    root: resolve(__dirname, 'src/renderer'),
    plugins: [vue()],
    build: {
      outDir: 'out/renderer',
      rollupOptions: {
        input: {
          index: resolve(__dirname, 'src/renderer/index.html')
        }
      }
    },
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src/renderer/src'),
        '@shared': resolve(__dirname, 'src/shared')
      }
    }
  }
})
