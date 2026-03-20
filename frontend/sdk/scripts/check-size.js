/**
 * Bundle size gate — runs after build.
 * Fails with exit code 1 if gzipped bundle exceeds 50KB.
 * Included in CI pipeline.
 */

const fs = require('fs')
const zlib = require('zlib')
const path = require('path')

const MAX_SIZE_KB = 50
const BUNDLE_PATH = path.join(__dirname, '../dist/index.esm.js')

if (!fs.existsSync(BUNDLE_PATH)) {
  console.error('❌ Bundle not found. Run `npm run build` first.')
  process.exit(1)
}

const raw = fs.readFileSync(BUNDLE_PATH)
const gzipped = zlib.gzipSync(raw)
const sizeKB = gzipped.length / 1024

const status = sizeKB <= MAX_SIZE_KB ? '✅' : '❌'
console.log(`${status} Bundle size: ${sizeKB.toFixed(2)} KB gzipped (limit: ${MAX_SIZE_KB} KB)`)

if (sizeKB > MAX_SIZE_KB) {
  console.error(`\nBundle exceeds ${MAX_SIZE_KB}KB limit. Reduce dependencies or split code.`)
  process.exit(1)
}

process.exit(0)
