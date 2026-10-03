from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import threading
from typing import Iterator, Mapping
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json


class ModelManagerError(RuntimeError):
    """Raised when task-scoped model lifecycle management fails."""


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """A bounded, task-oriented local Ollama model profile.

    estimated_ram_mb is an admission estimate, not a measured peak.
    """

    name: str
    family: str
    disk_mb: int
    estimated_ram_mb: int
    supports_vision: bool
    task_tags: frozenset[str]
    context_window: int = 8192
    license_name: str = "unknown"
    source_url: str = ""

    def validate(self) -> None:
        if not self.name or self.name.strip() != self.name:
            raise ValueError("model name must be a non-empty trimmed string")
        if self.disk_mb <= 0 or self.estimated_ram_mb <= 0:
            raise ValueError("model resource estimates must be > 0")
        if not self.task_tags:
            raise ValueError("model must have at least one task tag")
        if self.context_window <= 0:
            raise ValueError("model context window must be > 0")
        if not self.license_name or self.license_name.strip() != self.license_name:
            raise ValueError("model license_name must be a non-empty trimmed string")
        if self.source_url and not self.source_url.startswith("https://"):
            raise ValueError("model source_url must be HTTPS when provided")


@dataclass(frozen=True, slots=True)
class ModelSelection:
    """Deterministic model choice for one task."""

    spec: ModelSpec
    reason: str

    @property
    def model(self) -> str:
        return self.spec.name


DEFAULT_MODEL_CATALOG: tuple[ModelSpec, ...] = (
    ModelSpec(
        name="gemma3:270m",
        family="gemma3",
        disk_mb=292,
        estimated_ram_mb=600,
        supports_vision=False,
        task_tags=frozenset({"micro", "simple", "extract", "summarize"}),
        context_window=32_000,
        license_name="gemma",
        source_url="https://ollama.com/library/gemma3:270m",
    ),
    ModelSpec(
        name="smollm2:360m",
        family="smollm2",
        disk_mb=726,
        estimated_ram_mb=900,
        supports_vision=False,
        task_tags=frozenset({"micro", "simple", "classify", "extract"}),
        context_window=8_192,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/smollm2:360m",
    ),
    ModelSpec(
        name="gemma3:1b",
        family="gemma3",
        disk_mb=815,
        estimated_ram_mb=1_300,
        supports_vision=False,
        task_tags=frozenset({"simple", "general", "extract", "summarize", "reasoning"}),
        context_window=32_000,
        license_name="gemma",
        source_url="https://ollama.com/library/gemma3:1b",
    ),
    ModelSpec(
        name="qwen3.5:0.8b",
        family="qwen3.5",
        disk_mb=1024,
        estimated_ram_mb=1400,
        supports_vision=True,
        task_tags=frozenset(
            {"simple", "classify", "extract", "summarize", "general", "browser_lite"}
        ),
        context_window=256_000,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/qwen3.5:0.8b",
    ),
    ModelSpec(
        name="qwen2.5-coder:0.5b",
        family="qwen2.5-coder",
        disk_mb=398,
        estimated_ram_mb=700,
        supports_vision=False,
        task_tags=frozenset({"code", "coding", "debug", "repair", "micro"}),
        context_window=32_000,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/qwen2.5-coder:0.5b",
    ),
    ModelSpec(
        name="qwen2.5-coder:1.5b-instruct",
        family="qwen2.5-coder",
        disk_mb=986,
        estimated_ram_mb=1_500,
        supports_vision=False,
        task_tags=frozenset({"code", "coding", "debug", "repair", "tools"}),
        context_window=32_000,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/qwen2.5-coder:1.5b-instruct",
    ),
    ModelSpec(
        name="qwen3.5:2b-q4_K_M",
        family="qwen3.5",
        disk_mb=1940,
        estimated_ram_mb=2600,
        supports_vision=True,
        task_tags=frozenset({"browser", "general", "image", "extract"}),
        context_window=256_000,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/qwen3.5:2b-q4_K_M",
    ),
    ModelSpec(
        name="phi4-mini:3.8b-q4_K_M",
        family="phi4-mini",
        disk_mb=2500,
        estimated_ram_mb=3200,
        supports_vision=False,
        task_tags=frozenset({"general", "reasoning", "coding", "tools"}),
        context_window=128_000,
        license_name="mit",
        source_url="https://ollama.com/library/phi4-mini:3.8b-q4_K_M",
    ),
    ModelSpec(
        name="qwen3.5:4b-q4_K_M",
        family="qwen3.5",
        disk_mb=3480,
        estimated_ram_mb=3900,
        supports_vision=True,
        task_tags=frozenset(
            {"browser", "browser_complex", "vision", "coding", "reasoning", "general"}
        ),
        context_window=256_000,
        license_name="apache-2.0",
        source_url="https://ollama.com/library/qwen3.5:4b-q4_K_M",
    ),
)


_TOKEN_RE = re.compile(r"[a-z0-9]+")


class TaskModelManager:
    """Select, install, use, unload, and optionally delete one task-scoped model.

    The manager serializes model-backed work so a constrained host does not
    accidentally keep multiple large local models resident at once.
    """

    def __init__(
        self,
        *,
        ollama_executable: str | None = None,
        base_url: str | None = None,
        catalog: tuple[ModelSpec, ...] = DEFAULT_MODEL_CATALOG,
        max_model_ram_mb: int = 5200,
        max_model_disk_mb: int = 6000,
        install_timeout_seconds: float = 1800.0,
        ephemeral: bool = True,
    ) -> None:
        self.ollama_executable = (
            ollama_executable
            or os.getenv("SUPER_AI_OLLAMA_BIN")
            or "ollama"
        )
        if not self.ollama_executable or self.ollama_executable.strip() != self.ollama_executable:
            raise ValueError("ollama executable must be a trimmed string")

        self.base_url = (
            base_url
            or os.getenv("SUPER_AI_OLLAMA_URL")
            or "http://127.0.0.1:11434"
        ).rstrip("/")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Ollama URL must be an HTTP(S) URL with a hostname")
        if parsed.username or parsed.password:
            raise ValueError("Ollama URL must not contain embedded credentials")
        local = parsed.hostname.lower() in {"127.0.0.1", "localhost", "::1"}
        if not local and os.getenv("SUPER_AI_ALLOW_REMOTE_PLANNER") != "1":
            raise ValueError(
                "remote Ollama endpoints are disabled unless explicitly opted in"
            )

        if max_model_ram_mb <= 0 or max_model_disk_mb <= 0:
            raise ValueError("model budgets must be > 0")
        if install_timeout_seconds <= 0:
            raise ValueError("install_timeout_seconds must be > 0")

        validated: list[ModelSpec] = []
        seen: set[str] = set()
        for spec in catalog:
            spec.validate()
            if spec.name in seen:
                raise ValueError(f"duplicate model in catalog: {spec.name}")
            seen.add(spec.name)
            validated.append(spec)

        if not validated:
            raise ValueError("model catalog must not be empty")

        self.catalog = tuple(validated)
        self.max_model_ram_mb = max_model_ram_mb
        self.max_model_disk_mb = max_model_disk_mb
        self.install_timeout_seconds = float(install_timeout_seconds)
        self.ephemeral = bool(ephemeral)
        self._lock = threading.RLock()

    def select(
        self,
        goal: str,
        *,
        max_ram_mb: int | None = None,
        max_disk_mb: int | None = None,
        reserved_ram_mb: int = 0,
        reserved_disk_mb: int = 0,
        requires_vision: bool = False,
        escalate: bool = False,
    ) -> ModelSelection:
        if not goal or not goal.strip():
            raise ValueError("goal must be non-empty")

        budget_ram = self.max_model_ram_mb if max_ram_mb is None else max_ram_mb
        if budget_ram <= 0:
            raise ValueError("max_ram_mb must be > 0")
        budget_disk = (
            self.max_model_disk_mb if max_disk_mb is None else max_disk_mb
        )
        if budget_disk <= 0:
            raise ValueError("max_disk_mb must be > 0")
        if reserved_ram_mb < 0 or reserved_disk_mb < 0:
            raise ValueError("reserved resource budgets must be >= 0")
        model_ram_budget = budget_ram - reserved_ram_mb
        model_disk_budget = budget_disk - reserved_disk_mb
        if model_ram_budget <= 0 or model_disk_budget <= 0:
            raise ModelManagerError("task leaves no resource budget for a local model")

        tokens = _TOKEN_RE.findall(goal.lower())
        token_set = set(tokens)
        browser = bool(token_set & {"browser", "web", "website", "google", "page", "form"})
        visual = requires_vision or bool(
            token_set
            & {"image", "images", "visual", "screenshot", "diagram", "photo", "pdf"}
        )
        complex_task = escalate or len(tokens) >= 24 or bool(
            token_set
            & {
                "research",
                "compare",
                "complex",
                "multi-step",
                "multistep",
                "debug",
                "code",
                "reason",
                "analyze",
            }
        )

        classification_task = bool(
            token_set & {"classify", "classification", "label", "labels", "route", "triage", "detect"}
        ) and not browser and not visual and not complex_task
        code_task = bool(
            token_set
            & {"bug", "bugs", "debug", "fix", "repair", "refactor"}
        ) and not browser and not visual

        if browser and (visual or complex_task):
            preferred_tags = ("browser_complex", "vision", "browser")
        elif browser:
            preferred_tags = ("browser", "general")
        elif visual:
            preferred_tags = ("vision", "general", "image")
        elif classification_task:
            preferred_tags = ("classify", "micro", "simple", "extract")
        elif code_task:
            preferred_tags = ("repair", "debug", "coding", "code", "tools")
        elif complex_task:
            preferred_tags = ("reasoning", "coding", "general")
        else:
            preferred_tags = ("simple", "general", "extract")

        candidates = [
            spec
            for spec in self.catalog
            if spec.estimated_ram_mb <= model_ram_budget
            and spec.disk_mb <= model_disk_budget
            and (not visual or spec.supports_vision)
        ]
        if not candidates:
            raise ModelManagerError(
                f"no catalog model fits the RAM/disk budget (ram={budget_ram}MB)"
            )

        # Qwen3.5 0.8B is the guarded low-RAM browser fallback. Keep it out
        # of the normal browser ranking so the 2B profile remains preferred
        # whenever the budget can afford a fuller browser planner.
        if browser and not any("browser" in spec.task_tags for spec in candidates):
            preferred_tags = ("browser_lite", "general", "simple")

        def rank(spec: ModelSpec) -> tuple[int, int, int, int, str]:
            tag_priority = max(
                (
                    len(preferred_tags) - index
                    for index, tag in enumerate(preferred_tags)
                    if tag in spec.task_tags
                ),
                default=0,
            )
            tag_score = max(
                (len(spec.task_tags.intersection({tag})) for tag in preferred_tags),
                default=0,
            )
            # Prefer the smallest viable model, unless the task is complex or escalated.
            size_score = -spec.estimated_ram_mb if not complex_task else spec.estimated_ram_mb
            return (
                tag_priority,
                tag_score,
                size_score,
                int(spec.supports_vision and visual),
                spec.name,
            )

        selected = sorted(candidates, key=rank, reverse=True)[0]
        return ModelSelection(
            spec=selected,
            reason=(
                f"browser={browser}, visual={visual}, tool_task={tool_task}, complex={complex_task}, "
                f"ram_budget={model_ram_budget}MB, disk_budget={model_disk_budget}MB, "
                f"reserved_ram={reserved_ram_mb}MB, reserved_disk={reserved_disk_mb}MB"
            ),
        )

    @contextmanager
    def use_for_task(
        self,
        goal: str,
        *,
        max_ram_mb: int | None = None,
        max_disk_mb: int | None = None,
        reserved_ram_mb: int = 0,
        reserved_disk_mb: int = 0,
        requires_vision: bool = False,
        escalate: bool = False,
        ephemeral: bool | None = None,
    ) -> Iterator[ModelSelection]:
        selection = self.select(
            goal,
            max_ram_mb=max_ram_mb,
            max_disk_mb=max_disk_mb,
            reserved_ram_mb=reserved_ram_mb,
            reserved_disk_mb=reserved_disk_mb,
            requires_vision=requires_vision,
            escalate=escalate,
        )
        with self.use(selection, ephemeral=ephemeral):
            yield selection

    @contextmanager
    def use(
        self,
        selection: ModelSelection,
        *,
        ephemeral: bool | None = None,
    ) -> Iterator[ModelSelection]:
        if not isinstance(selection, ModelSelection):
            raise TypeError("selection must be ModelSelection")

        remove_after = self.ephemeral if ephemeral is None else bool(ephemeral)
        with self._lock:
            installed = self.is_installed(selection.model)
            if not installed:
                self.ensure_installed(selection)
            try:
                yield selection
            finally:
                # Always unload the model from RAM. Only delete artifacts that
                # were absent before this task started.
                unload_error: Exception | None = None
                try:
                    self.unload(selection.model)
                except Exception as exc:
                    unload_error = exc
                if remove_after and not installed:
                    self.remove(selection.model)
                if unload_error is not None:
                    raise ModelManagerError(
                        f"could not unload model {selection.model}"
                    ) from unload_error

    def is_installed(self, model: str) -> bool:
        if not model:
            raise ValueError("model must be non-empty")
        try:
            payload = self._request_json("GET", "/api/tags")
        except ModelManagerError:
            return False
        raw_models = payload.get("models", [])
        if not isinstance(raw_models, list):
            return False
        names = {
            str(item.get("name"))
            for item in raw_models
            if isinstance(item, Mapping) and item.get("name")
        }
        return model in names

    def selection_for_model(self, model: str) -> ModelSelection:
        if not model or model.strip() != model:
            raise ValueError("model must be a non-empty trimmed string")
        for spec in self.catalog:
            if spec.name == model:
                return ModelSelection(spec=spec, reason="explicit model selection")
        raise ModelManagerError(f"model is not in the managed catalog: {model}")

    def ensure_installed(self, selection: ModelSelection) -> None:
        spec = selection.spec
        if spec.estimated_ram_mb > self.max_model_ram_mb:
            raise ModelManagerError(
                f"model {spec.name} exceeds configured RAM budget"
            )
        if spec.disk_mb > self.max_model_disk_mb:
            raise ModelManagerError(
                f"model {spec.name} exceeds configured disk budget"
            )

        result = self._run_cli(
            "pull",
            spec.name,
            timeout_seconds=self.install_timeout_seconds,
        )
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "ollama pull failed"
            raise ModelManagerError(
                f"could not install model {spec.name}: {detail}"
            )

    def unload(self, model: str) -> None:
        self._request_json(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": [],
                "keep_alive": 0,
            },
        )

    def remove(self, model: str) -> None:
        result = self._run_cli(
            "rm",
            model,
            timeout_seconds=120.0,
        )
        if result.returncode != 0:
            detail = result.stderr or result.stdout or "ollama rm failed"
            raise ModelManagerError(
                f"could not remove model {model}: {detail}"
            )

    def _run_cli(
        self,
        *args: str,
        timeout_seconds: float,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self.ollama_executable, *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise ModelManagerError(
                "Ollama CLI was not found; install Ollama or set SUPER_AI_OLLAMA_BIN"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ModelManagerError("Ollama CLI command timed out") from exc
        except OSError as exc:
            raise ModelManagerError("failed to start Ollama CLI") from exc

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        url = self.base_url + path
        data = (
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if payload is not None
            else None
        )
        request = Request(
            url,
            data=data,
            headers={"content-type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urlopen(request, timeout=30.0) as response:
                raw = response.read(1_000_000)
        except (URLError, OSError) as exc:
            raise ModelManagerError(f"Ollama API request failed: {path}") from exc

        try:
            result = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelManagerError(f"Ollama API returned invalid JSON: {path}") from exc
        if not isinstance(result, dict):
            raise ModelManagerError(f"Ollama API response must be an object: {path}")
        return result
