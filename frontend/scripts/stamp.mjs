// After a build, record which commit the screens were built from, so the server can tell whether they match its own code (GET /api/version).
import { execSync } from 'node:child_process'
import { writeFileSync, existsSync } from 'node:fs'
let head = 'unknown'
try { head = execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim() } catch { /* not a git checkout */ }
if (existsSync('dist')) writeFileSync('dist/build.txt', head + '\n')
