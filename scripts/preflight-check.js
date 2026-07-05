#!/usr/bin/env node
/**
 * ─── Preflight Health Check + Root-Cause Diagnostics ──────────────────
 * Runs BEFORE Playwright tests to ensure ALL Docker containers are healthy.
 * If any container is unhealthy, it shows detailed diagnostic info (logs,
 * exit code, restart count) so you can fix the root cause — NOT auto-restart.
 *
 * Usage: node preflight-check.js
 *        node preflight-check.js --compose-dir /path/to/compose
 *
 * Exit code: 0 = all systems go, 1 = unrecoverable failure
 */

const { execSync } = require('child_process');
const path = require('path');

// ─── Configuration ──────────────────────────────────────────────────────
const COMPOSE_DIR = process.argv.includes('--compose-dir')
  ? process.argv[process.argv.indexOf('--compose-dir') + 1]
  : path.resolve(__dirname, '..', '..');

const COMPOSE_FILE = path.join(COMPOSE_DIR, 'docker-compose.yml');

// Services we expect to be running (from docker-compose.yml)
// Marked as critical=true means the test suite cannot proceed without them
const EXPECTED_SERVICES = [
  { name: 'nginx',               critical: false },
  { name: 'gateway',             critical: true  },
  { name: 'guardrails',          critical: false },
  { name: 'aida-bridge',         critical: false },
  { name: 'collector',           critical: false },
  { name: 'bias-monitor',        critical: false },
  { name: 'frontend',            critical: true  },
  { name: 'postgres',            critical: false },
  { name: 'redis',               critical: false },
  { name: 'ollama',              critical: false },
  { name: 'opa',                 critical: false },
  { name: 'agent-sidecar',       critical: false },
  { name: 'internal-ca',         critical: false },
  { name: 'cert-manager',        critical: false },
  { name: 'sidecar-proxy',       critical: false },
  { name: 'kill-switch',         critical: false },
  { name: 'budget-controller',   critical: false },
  { name: 'semantic-cache',      critical: false },
  { name: 'hallucination-detector', critical: false },
  { name: 'closed-loop',         critical: false },
  { name: 'retraining',          critical: false },
  { name: 'mlflow',              critical: false },
];

// API health check endpoints (for services that expose HTTP health endpoints)
const API_HEALTH_CHECKS = [
  { name: 'Gateway',       url: 'http://localhost:8000/health',       port: 8000 },
  { name: 'Guardrails',    url: 'http://localhost:8005/health',       port: 8005 },
  { name: 'AIDA Bridge',   url: 'http://localhost:8001/health',       port: 8001 },
  { name: 'Frontend',      url: 'http://localhost:3001',              port: 3001 },
  { name: 'Collector',     url: 'http://localhost:8006/health',       port: 8006 },
  { name: 'OPA',           url: 'http://localhost:8181/v1/data',      port: 8181 },
  { name: 'Kill Switch',   url: 'http://localhost:10001/health',      port: 10001 },
  { name: 'Sidecar Proxy', url: 'http://localhost:10002/health',      port: 10002 },
  { name: 'Internal CA',   url: 'http://localhost:8443/health',       port: 8443 },
  { name: 'Cert Manager',  url: 'http://localhost:8444/health',       port: 8444 },
  { name: 'Hallucination Detector', url: 'http://localhost:8008/health', port: 8008 },
];

// ─── Helpers ────────────────────────────────────────────────────────────

function run(cmd, options = {}) {
  try {
    return execSync(cmd, { encoding: 'utf-8', stdio: 'pipe', ...options }).trim();
  } catch (e) {
    return options.silent ? '' : e.stdout ? e.stdout.trim() : '';
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function color(s, code) {
  return `\x1b[${code}m${s}\x1b[0m`;
}
const green = (s) => color(s, 32);
const red = (s) => color(s, 31);
const yellow = (s) => color(s, 33);
const cyan = (s) => color(s, 36);
const bold = (s) => color(s, 1);

// ─── Step 1: Check Docker is running ────────────────────────────────────

function checkDockerAvailable() {
  console.log(cyan('\n══════════════════════════════════════════════════════════════'));
  console.log(cyan('  PREFLIGHT CHECK — Docker Container Health + Diagnostics'));
  console.log(cyan('══════════════════════════════════════════════════════════════\n'));

  try {
    const info = run('docker info --format "{{.ServerVersion}}"');
    console.log(`  ✅ Docker is running (version: ${info.trim()})`);
    return true;
  } catch {
    console.error(red('  ❌ Docker is not running or not accessible'));
    return false;
  }
}

// ─── Step 2: Get container status ───────────────────────────────────────

function getContainerStatus() {
  // Get all containers with "polarisgate" in the name (from docker-compose)
  const output = run(
    `docker ps -a --format "{{.Names}}|{{.Status}}|{{.State}}" --filter "name=polarisgate"`,
    { silent: true }
  );
  const containers = {};
  if (output) {
    output.split('\n').forEach(line => {
      const [name, status, state] = line.split('|');
      if (name && status) {
        // Extract exit code from status if present (e.g., "Exited (1) 2 hours ago")
        const exitMatch = status.match(/Exited\s*\((\d+)\)/);
        const exitCode = exitMatch ? exitMatch[1] : 'N/A';
        containers[name.trim()] = { status: status.trim(), state: state?.trim(), exitCode };
      }
    });
  }
  return containers;
}

function isHealthy(container) {
  if (!container || !container.status) return false;
  if (container.status.includes('(unhealthy)')) return false;
  if (container.status.startsWith('Up')) return true;
  return false;
}

// ─── Step 3: Root-cause diagnostics for unhealthy containers ────────────

function diagnoseContainer(containerName, containerInfo) {
  console.log(`\n  ${'═'.repeat(60)}`);
  console.log(`  🔴 DIAGNOSTIC REPORT: ${bold(containerName)}`);
  console.log(`  ${'═'.repeat(60)}`);

  // Basic info
  console.log(`\n  📋 Status:     ${containerInfo.status || 'N/A'}`);
  console.log(`  📋 State:      ${containerInfo.state || 'N/A'}`);
  console.log(`  📋 Exit Code:  ${containerInfo.exitCode || 'N/A'}`);

  // Docker inspect for more details
  console.log(`\n  🔍 Docker Inspect:`);
  try {
    const inspect = run(`docker inspect "${containerName}" 2>&1`, { silent: true });
    if (inspect) {
      const parsed = JSON.parse(inspect);
      const c = parsed[0] || {};
      const state = c.State || {};
      const config = c.Config || {};
      const hostConfig = c.HostConfig || {};
      const mounts = c.Mounts || [];

      console.log(`     Image:        ${config.Image || 'N/A'}`);
      console.log(`     Created:      ${c.Created || 'N/A'}`);
      console.log(`     RestartCount: ${state.RestartCount || 0}`);
      console.log(`     StartedAt:    ${state.StartedAt || 'N/A'}`);
      console.log(`     FinishedAt:   ${state.FinishedAt || 'N/A'}`);
      console.log(`     OOMKilled:    ${state.OOMKilled || false}`);
      console.log(`     Pid:          ${state.Pid || 0}`);

      if (state.Error) {
        console.log(`     Error:        ${red(state.Error)}`);
      }

      // Port mappings
      const ports = c.NetworkSettings?.Ports || {};
      const portKeys = Object.keys(ports);
      if (portKeys.length > 0) {
        console.log(`     Ports:        ${portKeys.join(', ')}`);
      }

      // Volume mounts
      if (mounts.length > 0) {
        console.log(`     Volumes:      ${mounts.map(m => `${m.Source || m.Name} → ${m.Destination}`).join(', ')}`);
      }

      // Health check
      const health = state.Health;
      if (health) {
        console.log(`     Health:       ${health.Status || 'N/A'}`);
        if (health.Log && health.Log.length > 0) {
          const lastCheck = health.Log[health.Log.length - 1];
          console.log(`     Last Health:  ${lastCheck.Output?.substring(0, 200) || 'N/A'}`);
        }
      }
    }
  } catch (e) {
    console.log(`     (unable to inspect: ${e.message})`);
  }

  // Container logs (last 50 lines)
  console.log(`\n  📋 Container Logs (last 50 lines):`);
  console.log(`  ${'─'.repeat(60)}`);
  try {
    const logs = run(`docker logs --tail 50 "${containerName}" 2>&1`, { silent: true });
    if (logs) {
      logs.split('\n').forEach(line => {
        console.log(`  ${line}`);
      });
    } else {
      console.log(`  (no logs available)`);
    }
  } catch {
    console.log(`  (unable to fetch logs)`);
  }
  console.log(`  ${'─'.repeat(60)}`);

  // Common root-cause suggestions
  console.log(`\n  🔧 Possible Root Causes:`);
  const suggestions = getRootCauseSuggestions(containerName, containerInfo);
  suggestions.forEach(s => console.log(`     • ${s}`));

  console.log(`  ${'═'.repeat(60)}`);
}

function getRootCauseSuggestions(containerName, containerInfo) {
  const suggestions = [];
  const name = containerName.toLowerCase();
  const status = (containerInfo.status || '').toLowerCase();
  const exitCode = containerInfo.exitCode;

  // Exit code analysis
  if (exitCode === '0' && status.includes('exited')) {
    suggestions.push('Container exited cleanly (code 0) but is not running. It may have completed its work.');
    suggestions.push('Check if the container is designed to run as a one-shot job (e.g., init container).');
  } else if (exitCode === '1') {
    suggestions.push('Application error (exit code 1). Check the logs above for stack traces or error messages.');
    suggestions.push('Common causes: missing environment variables, database connection failure, or config error.');
  } else if (exitCode === '137') {
    suggestions.push('Container was killed by OOM (out of memory) or received SIGKILL (exit code 137).');
    suggestions.push('Check docker-compose.yml memory limits and increase if needed.');
  } else if (exitCode === '139') {
    suggestions.push('Container crashed with SIGSEGV (segmentation fault, exit code 139).');
    suggestions.push('This is usually a bug in the application code or a library incompatibility.');
  } else if (exitCode === '143') {
    suggestions.push('Container was gracefully stopped (SIGTERM, exit code 143).');
    suggestions.push('This is normal if the container was intentionally stopped.');
  }

  // Service-specific suggestions
  if (name.includes('postgres') || name.includes('postgresql')) {
    suggestions.push('Check if POSTGRES_PASSWORD, POSTGRES_USER, POSTGRES_DB env vars are set.');
    suggestions.push('Check if the data directory is mounted correctly and has proper permissions.');
  } else if (name.includes('redis')) {
    suggestions.push('Check if Redis config file exists and is valid.');
    suggestions.push('Check if the port 6379 is not already in use on the host.');
  } else if (name.includes('gateway')) {
    suggestions.push('Check if all upstream services (guardrails, aida-bridge, etc.) are healthy.');
    suggestions.push('Check gateway config for correct service URLs and API keys.');
  } else if (name.includes('guardrails')) {
    suggestions.push('Check if ML models are downloaded and accessible.');
    suggestions.push('Check if the guardrails service can connect to the database.');
  } else if (name.includes('frontend')) {
    suggestions.push('Check if NEXT_PUBLIC_API_URL env var points to the correct gateway URL.');
    suggestions.push('Check if node_modules are installed correctly (npm install).');
  } else if (name.includes('nginx')) {
    suggestions.push('Check nginx config syntax: docker exec <container> nginx -t');
    suggestions.push('Check if the upstream services (frontend, gateway) are reachable from nginx.');
  } else if (name.includes('ollama')) {
    suggestions.push('Check if Ollama models are downloaded. Run: docker exec <container> ollama list');
    suggestions.push('Ollama may need significant RAM. Check if the host has enough memory.');
  } else if (name.includes('opa')) {
    suggestions.push('Check if OPA policy files are mounted correctly.');
    suggestions.push('Check OPA config for correct bundle paths and service URLs.');
  } else if (name.includes('aida-bridge')) {
    suggestions.push('Check if the AIDA API endpoint is reachable from the container.');
    suggestions.push('Check if AIDA_API_KEY env var is set correctly.');
  } else if (name.includes('hallucination')) {
    suggestions.push('Check if the hallucination detection model is downloaded.');
    suggestions.push('Check if the service can connect to the database for storing results.');
  } else if (name.includes('kill-switch')) {
    suggestions.push('Check if the kill switch service can connect to the database.');
    suggestions.push('Check if the service has the correct API keys for agent management.');
  } else if (name.includes('sidecar') || name.includes('proxy')) {
    suggestions.push('Check if the sidecar can connect to the main service it proxies.');
    suggestions.push('Check mTLS certificate configuration.');
  } else if (name.includes('cert-manager') || name.includes('internal-ca')) {
    suggestions.push('Check if certificate files are generated and mounted correctly.');
    suggestions.push('Check if the CA certificate is trusted by other services.');
  }

  // Generic suggestions
  if (status.includes('unhealthy')) {
    suggestions.push('Container is running but health check is failing. Check the health check endpoint/logic.');
  }
  if (status.includes('exited')) {
    suggestions.push('Container has exited. Check if it needs to be started: docker compose start <service>');
  }

  suggestions.push('After fixing, re-run this preflight check to verify.');

  return suggestions;
}

// ─── Step 4: API-level health checks ────────────────────────────────────

async function checkApiHealth() {
  console.log(cyan('\n─── API Health Checks ────────────────────────────────────────\n'));
  let allHealthy = true;

  for (const service of API_HEALTH_CHECKS) {
    try {
      const resp = await fetch(service.url, { signal: AbortSignal.timeout(5000) });
      if (resp.ok) {
        console.log(`  ✅ ${service.name} (${service.url}) — ${green('UP')}`);
      } else {
        console.log(`  ⚠️  ${service.name} (${service.url}) — ${yellow(`HTTP ${resp.status}`)}`);
        if (service.name === 'Gateway' || service.name === 'Frontend') {
          allHealthy = false;
        }
      }
    } catch (e) {
      console.log(`  ❌ ${service.name} (${service.url}) — ${red('DOWN')} (${e.message})`);
      if (service.name === 'Gateway' || service.name === 'Frontend') {
        allHealthy = false;
      }
    }
  }

  return allHealthy;
}

// ─── Main ───────────────────────────────────────────────────────────────

async function main() {
  // Step 1: Docker available?
  if (!checkDockerAvailable()) {
    process.exit(1);
  }

  // Step 2: Check all expected containers
  console.log(cyan('\n─── Container Health Check ───────────────────────────────────\n'));
  const containers = getContainerStatus();
  const unhealthy = [];

  for (const svc of EXPECTED_SERVICES) {
    const serviceName = svc.name;
    const critical = svc.critical;
    // Find the container by partial name match (containers are named like "polarisgate-gateway-1")
    const match = Object.keys(containers).find(name => name.includes(serviceName));
    if (match) {
      const info = containers[match];
      if (isHealthy(info)) {
        console.log(`  ✅ ${serviceName.padEnd(25)} ${green(info.status)}`);
      } else {
        console.log(`  ❌ ${serviceName.padEnd(25)} ${red(info.status)}`);
        unhealthy.push({ name: serviceName, containerName: match, info, critical });
      }
    } else {
      // Try with polarisgate- prefix
      const prefixedName = `polarisgate-${serviceName}`;
      const prefixedMatch = Object.keys(containers).find(name => name.includes(prefixedName));
      if (prefixedMatch) {
        const info = containers[prefixedMatch];
        if (isHealthy(info)) {
          console.log(`  ✅ ${serviceName.padEnd(25)} ${green(info.status)}`);
        } else {
          console.log(`  ❌ ${serviceName.padEnd(25)} ${red(info.status)}`);
          unhealthy.push({ name: serviceName, containerName: prefixedMatch, info, critical });
        }
      } else {
        console.log(`  ❌ ${serviceName.padEnd(25)} ${red('NOT FOUND')}`);
        unhealthy.push({ name: serviceName, containerName: null, info: { status: 'NOT RUNNING', state: 'absent', exitCode: 'N/A' }, critical });
      }
    }
  }

  // Step 3: Root-cause diagnostics for unhealthy containers
  if (unhealthy.length > 0) {
    const criticalUnhealthy = unhealthy.filter(u => u.critical);
    const nonCriticalUnhealthy = unhealthy.filter(u => !u.critical);

    console.log(red(`\n  ⚠️  ${unhealthy.length} container(s) unhealthy or not running — running diagnostics...\n`));

    for (const { name, containerName, info, critical } of unhealthy) {
      const label = critical ? bold('CRITICAL') : 'non-critical';
      if (containerName) {
        console.log(`\n  ${'═'.repeat(60)}`);
        console.log(`  🔴 DIAGNOSTIC REPORT [${label}]: ${bold(containerName)}`);
        console.log(`  ${'═'.repeat(60)}`);
        diagnoseContainer(containerName, info);
      } else {
        console.log(`\n  ${'═'.repeat(60)}`);
        console.log(`  🔴 DIAGNOSTIC REPORT [${label}]: ${bold(name)}`);
        console.log(`  ${'═'.repeat(60)}`);
        console.log(`\n  ❌ Container "${name}" was not found in "docker ps -a".`);
        console.log(`     It may not be defined in docker-compose.yml or may need to be created.`);
        console.log(`\n  🔧 Possible Root Causes:`);
        console.log(`     • Service not defined in docker-compose.yml`);
        console.log(`     • Service name mismatch (check docker-compose.yml for exact service name)`);
        console.log(`     • Container was manually removed with "docker rm"`);
        console.log(`     • docker-compose project was not fully started`);
        console.log(`\n  🔧 Try: docker compose -f "${COMPOSE_FILE}" up -d ${name}`);
        console.log(`  ${'═'.repeat(60)}`);
      }
    }

    if (criticalUnhealthy.length > 0) {
      // Critical services are down — fail
      console.log(red(`\n  ❌ PREFLIGHT FAILED — ${criticalUnhealthy.length} critical container(s) unhealthy.`));
      console.log(red(`     See diagnostic reports above for root-cause analysis.`));
      console.log(yellow(`\n  🔧 Fix the root cause, then re-run this preflight check.`));
      console.log(yellow(`     Common fixes:`));
      console.log(yellow(`     • Check environment variables in .env file`));
      console.log(yellow(`     • Check volume mounts and permissions`));
      console.log(yellow(`     • Check port conflicts (netstat -tuln | grep <port>)`));
      console.log(yellow(`     • Check Docker logs: docker compose -f "${COMPOSE_FILE}" logs <service>`));
      console.log(yellow(`     • Restart the service: docker compose -f "${COMPOSE_FILE}" up -d <service>`));
      console.log(yellow(`     • Rebuild: docker compose -f "${COMPOSE_FILE}" build <service>`));
      console.log('');
      process.exit(1);
    } else {
      // Only non-critical services are down — warn but continue
      console.log(yellow(`\n  ⚠️  ${nonCriticalUnhealthy.length} non-critical container(s) unhealthy.`));
      console.log(yellow(`     Diagnostics shown above for reference. Continuing with tests...\n`));
    }
  }

  // Step 4: API-level health checks
  const apiHealthy = await checkApiHealth();

  if (!apiHealthy) {
    console.error(red('\n  ❌ PREFLIGHT FAILED — Critical API endpoints are down.'));
    console.error(red('     Check the diagnostic info above for root cause.\n'));
    process.exit(1);
  }

  // Step 5: All clear!
  console.log(green('\n══════════════════════════════════════════════════════════════'));
  console.log(green('  ✅ PREFLIGHT PASSED — All containers healthy, all APIs up'));
  console.log(green('  ✅ Ready to run Playwright tests'));
  console.log(green('══════════════════════════════════════════════════════════════\n'));
  process.exit(0);
}

main().catch(err => {
  console.error(red(`\n  ❌ Preflight check error: ${err.message}\n`));
  process.exit(1);
});
