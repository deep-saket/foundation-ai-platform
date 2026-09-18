"""Read only the host characteristics needed for placement decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import platform
import re
import subprocess


def _run(*command: str) -> str:
    try:
        return subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        return ""


def _sysctl(name: str) -> str:
    return _run("sysctl", "-n", name)


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    system: str
    architecture: str
    model: str
    chip: str
    memory_bytes: int
    logical_cpus: int
    performance_cpus: int
    gpu_cores: int | None
    metal: bool

    @property
    def memory_gib(self) -> float:
        return self.memory_bytes / 1024**3

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["memory_gib"] = round(self.memory_gib, 1)
        return result


def detect_hardware() -> HardwareProfile:
    system = platform.system()
    architecture = platform.machine()
    memory_text = _sysctl("hw.memsize")
    logical_text = _sysctl("hw.logicalcpu")
    performance_text = _sysctl("hw.perflevel0.logicalcpu")
    chip = _sysctl("machdep.cpu.brand_string") or platform.processor() or "unknown"
    model = _sysctl("hw.model") or "unknown"

    gpu_cores: int | None = None
    displays = _run("system_profiler", "SPDisplaysDataType") if system == "Darwin" else ""
    match = re.search(r"Total Number of Cores:\s*(\d+)", displays)
    if match:
        gpu_cores = int(match.group(1))

    return HardwareProfile(
        system=system,
        architecture=architecture,
        model=model,
        chip=chip,
        memory_bytes=int(memory_text or 0),
        logical_cpus=int(logical_text or 0),
        performance_cpus=int(performance_text or logical_text or 0),
        gpu_cores=gpu_cores,
        metal=system == "Darwin" and architecture == "arm64",
    )
