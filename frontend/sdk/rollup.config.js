import resolve from '@rollup/plugin-node-resolve'
import typescript from '@rollup/plugin-typescript'
import { terser } from 'rollup-plugin-terser'

const production = process.env.NODE_ENV === 'production'

export default {
  input: 'src/index.ts',
  output: [
    {
      file: 'dist/index.esm.js',
      format: 'esm',
      sourcemap: !production,
    },
    {
      file: 'dist/index.cjs.js',
      format: 'cjs',
      sourcemap: !production,
      exports: 'named',
    },
  ],
  plugins: [
    resolve({ browser: true }),
    typescript({
      tsconfig: './tsconfig.json',
      declaration: true,
      declarationDir: 'dist',
    }),
    production && terser({
      compress: {
        passes: 2,
        drop_console: true,   // Remove debug logs in production
        pure_funcs: ['console.log', 'console.warn'],
      },
      mangle: true,
      format: {
        comments: false,
      },
    }),
  ].filter(Boolean),
  // No external deps — zero dependency SDK
  external: [],
}
