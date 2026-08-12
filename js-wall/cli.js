#!/usr/bin/env node
/**
 * js-wall CLI — run Python scripts inside the JS security wall.
 *
 * Usage:
 *   js-wall run script.py                    # Run a Python file
 *   js-wall run -c 'print("hi")'             # Run inline code
 *   js-wall run --timeout 5s --mem 256m script.py
 *   js-wall run --no-network script.py       # Block network
 */

const { run } = require('./wall');
const fs = require('fs');
const path = require('path');

function usage() {
  console.error(`
JS WALL — Secure Python Execution Boundary

Usage:
  js-wall run [options] <script.py>       Run a Python script
  js-wall run [options] -c <code>         Run inline Python code
  js-wall run [options]                   Read script from stdin

Options:
  --timeout, -t <n>      Wall-clock timeout (default: 30s, e.g. 5m, 1h)
  --cpu-time, -C <n>     CPU time limit (default: 20s)
  --memory, -m <n>       Max virtual memory (default: 512m, e.g. 256m, 1g)
  --max-output, -o <n>   Truncate stdout to N bytes (e.g. 1m for 1MB)
  --network, -n          Allow network access (default: BLOCKED)
  --python, -p <path>    Python interpreter path (default: python3)
  --env, -e KEY=VAL      Set environment variable (repeatable)
  --verbose, -v          Show debug info

Examples:
  js-wall run -t 10s -m 256m heavy.py
  js-wall run -c 'import os; print(os.listdir("/"))'
  echo 'print(sum(range(1000000)))' | js-wall run --cpu-time 5s
`);
  process.exit(2);
}

function parseArgs(argv) {
  const opts = { script: null, args: [], verbose: false };
  let i = 0;

  while (i < argv.length) {
    const a = argv[i];
    switch (a) {
      case '-h': case '--help': usage(); break;
      case '-v': case '--verbose': opts.verbose = true; break;
      case '-t': case '--timeout': opts.timeout = argv[++i]; break;
      case '-C': case '--cpu-time': opts.cpuTime = argv[++i]; break;
      case '-m': case '--memory': opts.memory = argv[++i]; break;
      case '-o': case '--max-output': opts.truncateOutput = argv[++i]; break;
      case '-n': case '--network': opts.allowNetwork = true; break;
      case '-p': case '--python': opts.python = argv[++i]; break;
      case '-e': case '--env': {
        const [k, ...vparts] = (argv[++i] || '').split('=');
        if (!opts.env) opts.env = {};
        opts.env[k] = vparts.join('=');
        break;
      }
      case '-c': {
        opts.script = argv[++i];
        break;
      }
      default: {
        if (a && !a.startsWith('-')) {
          opts.scriptPath = a;
          opts.args = argv.slice(i + 1);
          i = argv.length; // consume rest
        }
        break;
      }
    }
    i++;
  }

  return opts;
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0) usage();

  const sub = argv[0];
  if (sub !== 'run') usage();

  const opts = parseArgs(argv.slice(1));

  if (!opts.script && !opts.scriptPath) {
    // Read from stdin
    const chunks = [];
    process.stdin.setEncoding('utf8');
    for await (const chunk of process.stdin) {
      chunks.push(chunk);
    }
    opts.stdin = chunks.join('');
  }

  if (opts.verbose) {
    console.error('[JSWall CLI] Options:', JSON.stringify(opts, null, 2));
  }

  try {
    const result = await run(opts);
    process.stdout.write(result.stdout);

    if (result.stderr || result.exitCode !== 0 || result.timedOut || result.oom) {
      if (result.timedOut) {
        console.error('\n[JSWall] TIMED OUT — process killed after wall-clock limit');
      }
      if (result.oom) {
        console.error('\n[JSWall] OUT OF MEMORY — process killed (memory limit exceeded)');
      }
      if (result.exitCode !== 0 && !result.timedOut && !result.oom) {
        if (result.stderr) process.stderr.write(result.stderr);
      }
      process.exit(result.exitCode || 143); // 143 = SIGTERM/SIGKILL
    }
  } catch (err) {
    console.error('[JSWall] Sandbox error:', err.message);
    process.exit(1);
  }
}

main();
