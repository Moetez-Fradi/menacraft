import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const currentFile = fileURLToPath(import.meta.url);
const currentDir = path.dirname(currentFile);
const rootDir = path.resolve(currentDir, '..');
const sourceDir = path.join(rootDir, 'src');
const distDir = path.join(rootDir, 'dist');
const isCleanOnly = process.argv.includes('--clean');

rmSync(distDir, { recursive: true, force: true });

if (isCleanOnly) {
  process.stdout.write('Cleaned dist directory.\\n');
  process.exit(0);
}

if (!existsSync(sourceDir)) {
  throw new Error(`Source directory not found: ${sourceDir}`);
}

mkdirSync(distDir, { recursive: true });
cpSync(sourceDir, distDir, { recursive: true });

process.stdout.write('Built extension into dist/.\\n');
