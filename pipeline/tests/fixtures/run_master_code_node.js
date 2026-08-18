// Test harness: runs one Code node of the master n8n workflow the way n8n runs it.
//
// These nodes decide which subworkflow an experiment executes and what each run
// mode does next, so the regression tests have to run the shipped JavaScript
// rather than a Python restatement of it.
//
// n8n executes Code nodes inside a vm2 NodeVM, which is a fresh V8 context: it
// has the JavaScript built-ins and nothing Node installs on its own global. Code
// that reads `structuredClone`, `fetch`, `URL`, `TextEncoder` or `crypto` throws
// there while running fine under plain `node`. This harness therefore evaluates
// in a `node:vm` context configured to the same surface, so a Code node that
// cannot run in n8n cannot pass here either.
const fs = require('fs');
const path = require('path');
const vm = require('node:vm');

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const master = JSON.parse(fs.readFileSync(spec.master, 'utf8'));
const node = master.nodes.find((candidate) => candidate.name === spec.node);
if (!node) throw new Error(`Master workflow has no node named ${spec.node}`);

// `files` reads real workflow variants off disk the way the readWriteFile glob
// feeds the node; `input` passes items straight through.
const items = spec.files
  ? spec.files.map((file) => ({
    json: {
      workflow_text: fs.readFileSync(file, 'utf8'),
      fileName: path.basename(file),
    },
    binary: { data: { fileName: path.basename(file) } },
  }))
  : (spec.input || []).map((json) => ({ json }));

const $input = {
  all: () => items,
  first: () => items[0],
};

// Each stub is one referenced node: `json` is what it returned, `params` is how
// it is configured. The AI Model nodes are read through `params`, which is how
// the master keeps the exact model in n8n's own selector.
const stubs = { ...(spec.nodes || {}) };
if (spec.state) stubs['State Machine'] = { json: spec.state };
const $ = (name) => {
  const stub = stubs[name];
  if (!stub) throw new Error(`Unstubbed node reference: ${name}`);
  return {
    params: stub.params || {},
    first: () => ({ json: stub.json || {} }),
    all: () => (stub.items || [{ json: stub.json || {} }]),
  };
};

// What vm2 grants a Code node beyond the language built-ins. Anything absent
// here is absent in n8n too; `Proxy` is removed because vm2 does not expose it.
const sandbox = { $input, $, console, process, Buffer, setTimeout, clearTimeout };
const context = vm.createContext(sandbox);
vm.runInContext('Proxy = undefined;', context);

try {
  const run = vm.runInContext(`(function ($input, $) {\n${node.parameters.jsCode}\n})`, context);
  const output = run($input, $);
  process.stdout.write(JSON.stringify({ ok: true, result: output[0].json, items: output }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: error.message }));
}
