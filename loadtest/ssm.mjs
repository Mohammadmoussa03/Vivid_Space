#!/usr/bin/env node
/**
 * Run a shell script on the EC2 box via SSM and stream back stdout/stderr.
 * Avoids the quoting minefield of building --parameters on the command line.
 *
 *   node ssm.mjs "some; shell; script"
 *   node ssm.mjs --file script.sh
 */
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const INSTANCE = process.env.VS_INSTANCE || 'i-09f2cd2937606ff4e';
const REGION = process.env.VS_REGION || 'eu-central-1';

const argv = process.argv.slice(2);
const script = argv[0] === '--file' ? readFileSync(argv[1], 'utf8') : argv.join(' ');

const aws = (args) =>
  execFileSync('aws', args, {
    encoding: 'utf8',
    maxBuffer: 64 * 1024 * 1024,
    env: { ...process.env, AWS_PAGER: '', PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' },
  }).trim();

const paramFile = join(tmpdir(), `ssm-${process.pid}.json`);
writeFileSync(paramFile, JSON.stringify({ commands: [script] }));

const cid = aws([
  'ssm', 'send-command', '--region', REGION, '--instance-ids', INSTANCE,
  '--document-name', 'AWS-RunShellScript',
  '--parameters', `file://${paramFile}`,
  '--timeout-seconds', '1200',
  '--query', 'Command.CommandId', '--output', 'text',
]);
process.stderr.write(`[ssm] command ${cid}\n`);

const sleep = (ms) => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);

let status = 'Pending';
for (let i = 0; i < 240; i++) {
  sleep(5000);
  try {
    status = aws(['ssm', 'get-command-invocation', '--region', REGION, '--command-id', cid,
      '--instance-id', INSTANCE, '--query', 'Status', '--output', 'text']);
  } catch { continue; }
  if (!['Pending', 'InProgress', 'Delayed'].includes(status)) break;
}

const get = (field) => {
  try {
    return aws(['ssm', 'get-command-invocation', '--region', REGION, '--command-id', cid,
      '--instance-id', INSTANCE, '--query', field, '--output', 'text']);
  } catch { return ''; }
};

process.stderr.write(`[ssm] status ${status}\n`);
console.log(get('StandardOutputContent'));
const err = get('StandardErrorContent');
if (err && err !== 'None') process.stderr.write(`[ssm stderr]\n${err}\n`);
process.exit(status === 'Success' ? 0 : 1);
