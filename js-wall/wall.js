#!/usr/bin/env node
/**
 * JS Wall — JavaScript security boundary for Python execution.
 * Uses bubblewrap (bwrap) for namespace isolation + prlimit for resource caps.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

// ── Default limits ──────────────────────────────────────────────────────────
const DEFAULTS = {
  timeout: 30,           // wall-clock seconds
  cpuTime: 20,           // CPU seconds (prlimit --cpu)
  memory: '512m',        // max RSS (prlimit --as / setrlimit RLIMIT_AS)
  maxFileSize: '100m',   // max output file size
  workDir: null,         // auto-created tmpdir if null
  readOnlyRoot: true,    // rootfs read-only except work dir
  allowNetwork: false,   // block network by default
  env: {},               // extra env vars
  python: 'python3',     // python interpreter to use
};

// ── Helpers ─────────────────────────────────────────────────────────────────
function randomId() {
  return crypto.randomBytes(8).toString('hex');
}

function humanToBytes(s) {
  const m = /^(\d+(?:\.\d+)?)\s*(b|k|kb|m|mb|g|gb)?$/i.exec(String(s).trim().toLowerCase());
  if (!m) throw new Error(`Cannot parse size: ${s}`);
  const n = parseFloat(m[1]);
  const u = (m[2] || 'b').replace('b', '');
  const mult = { '': 1, k: 1024, m: 1024 ** 2, g: 1024 ** 3 };
  return Math.floor(n * (mult[u] || 1));
}

function humanToSeconds(s) {
  if (typeof s === 'number') return s;
  const m = /^(\d+)\s*(s|m|h)?$/i.exec(String(s).trim());
  if (!m) throw new Error(`Cannot parse duration: ${s}`);
  const n = parseInt(m[1], 10);
  const u = (m[2] || 's').toLowerCase();
  const mult = { s: 1, m: 60, h: 3600 };
  return n * mult[u];
}

// ── Build bwrap sandbox command ─────────────────────────────────────────────
function buildSandbox({ workDir, readOnlyRoot, allowNetwork, env, extraBinds }) {
  const args = [];

  // Namespace isolation
  args.push('--unshare-user');
  args.push('--unshare-ipc');
  args.push('--unshare-pid');
  args.push('--unshare-uts');
  args.push('--unshare-cgroup');
  if (!allowNetwork) {
    args.push('--unshare-net');
  }

  // Basic rootfs — bind-mount essential dirs read-only
  const roBinds = [
    '/usr', '/lib', '/lib64', '/bin', '/sbin',
  ];

  // Architecture-specific library paths
  const archLibDirs = [
    '/usr/lib/x86_64-linux-gnu',
    '/lib/x86_64-linux-gnu',
  ];
  for (const d of archLibDirs) {
    if (fs.existsSync(d)) {
      roBinds.push(d);
    }
  }
  for (const d of roBinds) {
    if (fs.existsSync(d)) {
      args.push('--ro-bind', d, d);
    }
  }

  // /etc — read only (include resolv.conf + hosts for DNS when network is allowed)
  if (fs.existsSync('/etc')) {
    if (allowNetwork) {
      // Full /etc read-only so DNS resolution works
      args.push('--ro-bind', '/etc', '/etc');
      // systemd-resolved stub lives under /run on modern Ubuntu
      if (fs.existsSync('/run/systemd/resolve')) {
        args.push('--ro-bind', '/run/systemd/resolve', '/run/systemd/resolve');
      }
    } else {
      // Minimal /etc — just what python needs to start
      const etcFiles = ['/etc/passwd', '/etc/group', '/etc/nsswitch.conf',
                        '/etc/host.conf', '/etc/localtime', '/etc/timezone'];
      for (const f of etcFiles) {
        if (fs.existsSync(f)) args.push('--ro-bind', f, f);
      }
    }
  }

  // /proc — minimal
  args.push('--proc', '/proc');

  // /dev — minimal
  args.push('--dev', '/dev');

  // Writable work directory
  workDir = workDir || fs.mkdtempSync(path.join(os.tmpdir(), 'jswall-'));
  args.push('--bind', workDir, '/work');
  args.push('--chdir', '/work');

  // Extra bind mounts (for venvs, data dirs, etc.)
  if (extraBinds) {
    for (const bind of extraBinds) {
      if (typeof bind === 'string') {
        // Simple ro-bind: same src and dest
        if (fs.existsSync(bind)) {
          args.push('--ro-bind', bind, bind);
        }
      } else if (bind.src && bind.dest) {
        const mode = bind.mode || 'ro-bind';
        if (fs.existsSync(bind.src)) {
          args.push(`--${mode}`, bind.src, bind.dest);
        }
      }
    }
  }

  // Writable /tmp
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'jswalltmp-'));
  args.push('--bind', tmpDir, '/tmp');

  // Environment
  const envList = ['PATH=/usr/bin:/bin:/usr/sbin:/sbin', 'HOME=/work'];
  for (const [k, v] of Object.entries(env)) {
    envList.push(`${k}=${v}`);
  }
  for (const e of envList) {
    args.push('--setenv', ...e.split('=', 2));
  }

  return { args, workDir, tmpDir };
}

// ── Run a Python script inside the wall ─────────────────────────────────────
function run(opts = {}) {
  const config = { ...DEFAULTS, ...opts };

  return new Promise((resolve, reject) => {
    const { args: bwrapArgs, workDir, tmpDir } = buildSandbox(config);

    // Prepare the script file inside the sandbox workdir
    const scriptPath = path.join(workDir, 'script.py');
    if (config.script) {
      // Write the script content
      fs.writeFileSync(scriptPath, config.script, 'utf8');
    } else if (config.scriptPath) {
      // Copy script file into workdir
      const src = fs.readFileSync(config.scriptPath, 'utf8');
      fs.writeFileSync(scriptPath, src, 'utf8');
    } else {
      // Pipe stdin as the script
      fs.writeFileSync(scriptPath, config.stdin || '', 'utf8');
    }

    // Resource limits applied via prlimit wrapper inside bwrap
    const prlimitArgs = [];
    if (config.cpuTime) {
      prlimitArgs.push(`--cpu=${humanToSeconds(config.cpuTime)}`);
    }
    if (config.memory) {
      prlimitArgs.push(`--as=${humanToBytes(config.memory)}`);
    }
    if (config.maxFileSize) {
      prlimitArgs.push(`--fsize=${humanToBytes(config.maxFileSize)}`);
    }

    // Build the full command: bwrap [...] -- prlimit [...] python3 script.py [args...]
    const innerCmd = [
      'prlimit',
      ...prlimitArgs,
      config.python || 'python3',
      'script.py',
      ...(config.args || []),
    ];

    const fullCmd = ['bwrap', ...bwrapArgs, '--', ...innerCmd];

    if (config.verbose) {
      console.error('[JSWall] command:', fullCmd.join(' '));
      console.error('[JSWall] workdir:', workDir);
    }

    const child = spawn(fullCmd[0], fullCmd.slice(1), {
      stdio: ['pipe', 'pipe', 'pipe'],
      env: {}, // bwrap handles env
    });

    let stdout = '';
    let stderr = '';
    let killed = false;
    let timedOut = false;

    child.stdout.on('data', (d) => { stdout += d.toString(); });
    child.stderr.on('data', (d) => { stderr += d.toString(); });

    // Wall-clock timeout
    let timer = null;
    if (config.timeout) {
      timer = setTimeout(() => {
        timedOut = true;
        killed = true;
        child.kill('SIGKILL');
        // Also kill the whole process group if possible
        try { process.kill(-child.pid, 'SIGKILL'); } catch (_) {}
      }, humanToSeconds(config.timeout) * 1000);
    }

    child.on('error', (err) => {
      clearTimeout(timer);
      cleanup();
      reject(Object.assign(err, { stdout, stderr, timedOut: false, killed: false }));
    });

    child.on('exit', (code, signal) => {
      clearTimeout(timer);
      cleanup();
      const oom = stderr.includes('MemoryError') ||
                  stderr.includes('Cannot allocate memory') ||
                  signal === 'SIGKILL' && !timedOut;

      resolve({
        exitCode: code,
        signal,
        stdout,
        stderr,
        timedOut,
        killed,
        oom,
        truncated: config.truncateOutput &&
                   stdout.length > config.truncateOutput
                     ? stdout.slice(0, config.truncateOutput)
                     : false,
      });
    });

    function cleanup() {
      // Clean up temp dirs
      try { fs.rmSync(workDir, { recursive: true, force: true }); } catch (_) {}
      try { fs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}
    }
  });
}

// ── Exports ─────────────────────────────────────────────────────────────────
module.exports = { run, DEFAULTS, humanToBytes, humanToSeconds };
