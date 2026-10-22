// Probe: run through the cache-env wrapper and report what the child sees.
console.log('  ELECTRON_CACHE         =', process.env.ELECTRON_CACHE)
console.log('  ELECTRON_BUILDER_CACHE =', process.env.ELECTRON_BUILDER_CACHE)
console.log('  PATH 含 node_modules/.bin =', (process.env.PATH || '').includes('node_modules'))
