const { createHash } = require('node:crypto');
const { execFileSync } = require('node:child_process');
const { mkdirSync, readFileSync, readdirSync, writeFileSync } = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const read = file => readFileSync(path.join(root, file), 'utf8');
const html = read('index.html');
const scripts = [...html.matchAll(/<script src="(content\/[^"]+\.js)"><\/script>/g)].map(match => match[1]);
const citations = readdirSync(path.join(root, 'content/cit'))
  .filter(file => file.endsWith('.js')).sort().map(file => 'content/cit/' + file);
const context = vm.createContext({ window: {} });
for (const file of [...scripts, ...citations]) {
  vm.runInContext(read(file), context, { filename: file, timeout: 1000 });
}

const { validateContent } = require('../android-content-update.js');
const content = JSON.parse(JSON.stringify(context.window));
validateContent(content);
const snapshot = JSON.stringify({ schema: 1, content });
const timestamp = Number(execFileSync('git', ['log', '-1', '--format=%ct'], { cwd: root, encoding: 'utf8' }).trim());
const manifest = { schema: 1, timestamp, sha256: createHash('sha256').update(snapshot).digest('hex') };

const output = process.argv[2];
if (output) {
  mkdirSync(output, { recursive: true });
  writeFileSync(path.join(output, 'content-v1.json'), snapshot);
  writeFileSync(path.join(output, 'manifest-v1.json'), JSON.stringify(manifest) + '\n');
} else {
  process.stdout.write(JSON.stringify(manifest));
}
