"""
Environment profiler for NorthGuard tier selection.
Detects system resources and benchmarks the LLM to choose the optimal tier.
"""
import os, logging, platform, subprocess, asyncio, httpx

logger = logging.getLogger(__name__)

class EnvironmentProfile:
    def __init__(self):
        self.total_ram_gb: float = 0.0
        self.cpu_cores: int = 1
        self.is_docker: bool = False
        self.recommended_tier: int = 1
        self.tier3_viable: bool = False

    def detect_static(self):
        try:
            if platform.system() == "Linux":
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            self.total_ram_gb = int(line.split()[1]) / (1024 * 1024)
                            break
            elif platform.system() == "Darwin":
                output = subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode().strip()
                self.total_ram_gb = int(output) / (1024**3)
        except Exception:
            self.total_ram_gb = 4.0
        self.cpu_cores = os.cpu_count() or 1
        self.is_docker = os.path.exists("/.dockerenv")
        logger.info(f"Environment: {platform.system()}, RAM={self.total_ram_gb:.1f}GB, CPU={self.cpu_cores} cores, Docker={self.is_docker}")

    def decide_tier(self):
        if self.total_ram_gb >= 14 and self.cpu_cores >= 4:
            self.recommended_tier = 3
        elif self.total_ram_gb >= 5 and self.cpu_cores >= 2:
            self.recommended_tier = 2
        else:
            self.recommended_tier = 1
        logger.info(f"Static detection suggests Tier {self.recommended_tier}")

    async def benchmark_tier3(self, ollama_url: str, timeout: int = 20) -> bool:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{ollama_url}/api/generate",
                    json={"model": "llama3.2:3b", "prompt": "Hello", "stream": False, "options": {"num_predict": 5}}
                )
                if resp.status_code == 200:
                    logger.info("✅ Tier 3 benchmark passed")
                    return True
        except Exception as e:
            logger.info(f"Tier 3 benchmark failed: {type(e).__name__}")
        return False

    async def determine_optimal_tier(self, ollama_url: str) -> int:
        self.detect_static()
        self.decide_tier()
        # Only benchmark for Tier 3; for Tier 2 we trust static detection.
        if self.recommended_tier >= 3:
            viable = await self.benchmark_tier3(ollama_url)
            if viable:
                self.tier3_viable = True
                self.recommended_tier = 3
            else:
                self.recommended_tier = 2  # fallback to Tier 2, no connectivity check needed
        logger.info(f"Final recommended tier: {self.recommended_tier} (Tier3 viable: {self.tier3_viable})")
        return self.recommended_tier

_profile: EnvironmentProfile | None = None

async def get_profile(ollama_url: str = "http://ollama:11434") -> EnvironmentProfile:
    global _profile
    if _profile is None:
        _profile = EnvironmentProfile()
        await _profile.determine_optimal_tier(ollama_url)
    return _profile
