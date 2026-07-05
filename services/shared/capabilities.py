import os, logging, platform, subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SystemProfile:
    ram_gb: float
    cpu_cores: int
    has_gpu: bool
    is_docker: bool
    recommended_guardrails_tier: int  # 1=keyword, 2=BERT, 3=BERT+LLM
    recommended_aida_tier: int        # 1=template, 2=warm, 3=full

    @staticmethod
    def detect() -> "SystemProfile":
        ram = _detect_ram()
        cpu = os.cpu_count() or 1
        gpu = _detect_gpu()
        docker = os.path.exists("/.dockerenv")
        # Allow override via env var (useful in Docker where /proc/meminfo may be limited)
        guard_tier_override = os.getenv("GUARDRAILS_TIER")
        if guard_tier_override:
            guard_tier = int(guard_tier_override)
            logger.info(f"Guardrails tier overridden by env var GUARDRAILS_TIER={guard_tier}")
        else:
            guard_tier = _choose_guardrails_tier(ram, gpu)
        aida_tier = _choose_aida_tier(ram, cpu, gpu)
        profile = SystemProfile(
            ram_gb=ram,
            cpu_cores=cpu,
            has_gpu=gpu,
            is_docker=docker,
            recommended_guardrails_tier=guard_tier,
            recommended_aida_tier=aida_tier,
        )
        logger.info(f"System profile: {profile}")
        return profile

def _detect_ram() -> float:
    """Detect available RAM, respecting container cgroup limits.
    
    Priority:
    1. cgroup v2 memory.max (Docker/K8s container limit)
    2. cgroup v1 memory.limit_in_bytes (older Docker)
    3. /proc/meminfo (host total — may overcount in containers)
    4. macOS sysctl
    5. Fallback to 4 GB
    """
    try:
        # cgroup v2 (Docker 20.10+, K8s)
        if os.path.exists("/sys/fs/cgroup/memory.max"):
            with open("/sys/fs/cgroup/memory.max") as f:
                raw = f.read().strip()
                if raw and raw != "max":
                    limit = int(raw)
                    if limit > 0:
                        gb = limit / (1024**3)
                        logger.debug(f"RAM from cgroup v2 memory.max: {gb:.2f} GB")
                        return gb
        # cgroup v1 (older Docker)
        if os.path.exists("/sys/fs/cgroup/memory/memory.limit_in_bytes"):
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                raw = f.read().strip()
                if raw:
                    limit = int(raw)
                    # Ignore max values (2^63 - 1 = no limit)
                    if limit > 0 and limit < (2**63 - 1):
                        gb = limit / (1024**3)
                        logger.debug(f"RAM from cgroup v1 memory.limit_in_bytes: {gb:.2f} GB")
                        return gb
    except Exception:
        pass

    try:
        if platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        gb = int(line.split()[1]) / (1024 * 1024)
                        logger.debug(f"RAM from /proc/meminfo: {gb:.2f} GB")
                        return gb
        elif platform.system() == "Darwin":
            output = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
            gb = int(output) / (1024**3)
            logger.debug(f"RAM from sysctl: {gb:.2f} GB")
            return gb
    except Exception:
        pass
    logger.warning("Could not detect RAM, defaulting to 4 GB")
    return 4.0

def _detect_gpu() -> bool:
    try:
        subprocess.run(["nvidia-smi"], capture_output=True, check=True)
        return True
    except Exception:
        return False

def _choose_guardrails_tier(ram_gb: float, has_gpu: bool) -> int:
    if has_gpu or ram_gb >= 14:
        return 3   # LLM + BERT
    elif ram_gb >= 5:
        return 2   # BERT only (keyword still available as ultimate fallback)
    else:
        return 1   # keyword only

def _choose_aida_tier(ram_gb: float, cpu_cores: int, has_gpu: bool) -> int:
    if has_gpu or (ram_gb >= 14 and cpu_cores >= 4):
        return 3   # full 3B model
    elif ram_gb >= 5 and cpu_cores >= 2:
        return 2   # warm endpoint summary
    else:
        return 1   # static template
