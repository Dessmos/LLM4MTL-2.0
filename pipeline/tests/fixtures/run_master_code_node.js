// Test harness: runs one Code node of the master n8n workflow under plain Node.
//
// The node selects which subworkflow an experiment actually executes, so the
// regression test has to run the shipped JavaScript rather than a Python
// restatement of it. n8n exposes `$input` and `$('<node>')` to Code nodes; this
// stubs exactly those two and nothing else.
const fs = require('fs');
const path = require('path');

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const master = JSON.parse(fs.readFileSync(spec.master, 'utf8'));
const node = master.nodes.find((candidate) => candidate.name === spec.node);
if (!node) throw new Error(`Master workflow has no node named ${spec.node}`);

const items = spec.files.map((file) => ({
  json: {
    workflow_text: fs.readFileSync(file, 'utf8'),
    fileName: path.basename(file),
  },
  binary: { data: { fileName: path.basename(file) } },
}));

const $input = {
  all: () => items,
  first: () => items[0],
};
const $ = (name) => {
  if (name !== 'State Machine') throw new Error(`Unstubbed node reference: ${name}`);
  return { first: () => ({ json: spec.state }) };
};

const run = new Function('$input', '$', node.parameters.jsCode);
try {
  const output = run($input, $);
  process.stdout.write(JSON.stringify({ ok: true, result: output[0].json }));
} catch (error) {
  process.stdout.write(JSON.stringify({ ok: false, error: error.message }));
}
