#!/usr/bin/env node

const { spawnSync } = require('node:child_process');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');

const PYTHON_PACKAGE_NAME = 'cafitac-agent-memory';

const COMMAND_ALIASES = new Map([
  ['bootstrap', 'hermes-bootstrap'],
  ['doctor', 'hermes-doctor'],
]);

function commandExists(command) {
  const whichCommand = process.platform === 'win32' ? 'where' : 'which';
  const probe = spawnSync(whichCommand, [command], {
    stdio: 'pipe',
    encoding: 'utf8',
  });
  return probe.status === 0;
}

function mapArgs(argv) {
  if (argv.length === 0) {
    return ['--help'];
  }

  const [first, ...rest] = argv;
  const mapped = COMMAND_ALIASES.get(first) ?? first;
  return [mapped, ...rest];
}

function pythonPackageSpec() {
  try {
    const packageJson = JSON.parse(readFileSync(join(__dirname, '..', 'package.json'), 'utf8'));
    if (packageJson.version) {
      return `${PYTHON_PACKAGE_NAME}==${packageJson.version}`;
    }
  } catch (_) {
    // Fall back to an unpinned package name only if package metadata is unavailable.
  }
  return PYTHON_PACKAGE_NAME;
}

function buildInvocation(args) {
  const forcedPython = process.env.AGENT_MEMORY_PYTHON_EXECUTABLE;
  if (forcedPython) {
    return {
      command: forcedPython,
      args: ['-m', 'agent_memory.api.cli', ...args],
      source: 'python-module',
    };
  }

  if (commandExists('uvx')) {
    return {
      command: 'uvx',
      args: ['--from', pythonPackageSpec(), 'agent-memory', ...args],
      source: 'uvx',
    };
  }

  if (commandExists('pipx')) {
    return {
      command: 'pipx',
      args: ['run', pythonPackageSpec(), ...args],
      source: 'pipx',
    };
  }

  return null;
}

function main() {
  const args = mapArgs(process.argv.slice(2));
  const invocation = buildInvocation(args);

  if (!invocation) {
    process.stderr.write(
      [
        'agent-memory npm launcher could not find a supported Python runtime path.',
        'Install uv (preferred) or pipx, or set AGENT_MEMORY_PYTHON_EXECUTABLE to a Python 3.11+ interpreter that can import agent_memory.',
      ].join('\n') + '\n',
    );
    process.exit(1);
  }

  const child = spawnSync(invocation.command, invocation.args, {
    stdio: 'pipe',
    encoding: 'utf8',
    env: process.env,
  });

  if (child.stdout) {
    process.stdout.write(child.stdout);
  }
  if (child.stderr) {
    process.stderr.write(child.stderr);
  }

  if (child.error) {
    process.stderr.write(`${child.error.message}\n`);
    process.exit(1);
  }

  process.exit(child.status ?? 1);
}

main();
