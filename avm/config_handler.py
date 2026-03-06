"""
avm/config_handler.py - Agent-writable Configuration

Layered config:
  Defaults → User config.yaml → Agent runtime changes

Paths:
  /.config/settings.yaml   - Main settings (merged view)
  /.config/raw             - Runtime changes only
  /.meta/version           - AVM version (read-only)
  /.meta/stats             - Store stats (read-only)
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict

from .handlers import BaseHandler, handler


# ─── Default Settings ─────────────────────────────────────

DEFAULT_SETTINGS = {
    "memory": {
        "duplicate_check": False,
        "duplicate_threshold": 0.85,
        "default_max_tokens": 4000,
        "chars_per_token": 4.0,
    },
    "scoring": {
        "importance_weight": 0.3,
        "recency_weight": 0.2,
        "relevance_weight": 0.5,
    },
    "compaction": {
        "enabled": False,
        "target_tokens": 2000,
        "threshold_tokens": 10000,
    },
    "decay": {
        "enabled": False,
        "half_life_days": 7.0,
    },
    "policies": {
        "on_conflict": "append",  # append | overwrite
        "on_similar": "warn",     # warn | skip | force
    },
}


def deep_merge(base: Dict, overlay: Dict) -> Dict:
    """Deep merge overlay into base."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ─── Config Store ─────────────────────────────────────────

class ConfigStore:
    """Manages layered configuration."""
    
    def __init__(self, user_config: Dict = None, storage_path: str = None):
        self.user_config = user_config or {}
        self.runtime_changes: Dict[str, Any] = {}
        self._storage_path = storage_path
        self._load_runtime()
    
    def _runtime_file(self) -> Path:
        if self._storage_path:
            return Path(self._storage_path).parent / "runtime_config.json"
        return Path.home() / ".local" / "share" / "avm" / "runtime_config.json"
    
    def _load_runtime(self):
        path = self._runtime_file()
        if path.exists():
            try:
                self.runtime_changes = json.loads(path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
    
    def _save_runtime(self):
        path = self._runtime_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.runtime_changes, indent=2))
    
    def get_merged(self) -> Dict:
        """Get fully merged config (defaults + user + runtime)."""
        merged = deep_merge(DEFAULT_SETTINGS, self.user_config)
        merged = deep_merge(merged, self.runtime_changes)
        return merged
    
    def get_value(self, key_path: str) -> Any:
        """Get a specific config value by dot-path."""
        config = self.get_merged()
        parts = key_path.split(".")
        for part in parts:
            if isinstance(config, dict) and part in config:
                config = config[part]
            else:
                return None
        return config
    
    def set_value(self, key_path: str, value: Any):
        """Set a runtime config value."""
        parts = key_path.split(".")
        target = self.runtime_changes
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = value
        self._save_runtime()
    
    def update(self, changes: Dict):
        """Update runtime config with changes."""
        self.runtime_changes = deep_merge(self.runtime_changes, changes)
        self._save_runtime()
    
    def reset(self, key_path: str = None):
        """Reset runtime changes."""
        if key_path:
            parts = key_path.split(".")
            target = self.runtime_changes
            for part in parts[:-1]:
                if part not in target:
                    return
                target = target[part]
            target.pop(parts[-1], None)
        else:
            self.runtime_changes = {}
        self._save_runtime()


# ─── Config Handler ─────────────────────────────────────────

@handler("config",
         description="Agent-writable configuration with layered merge",
         usage="""pattern: "/.config/**"
handler: config""",
         examples=[
             "cat /.config/settings.yaml",
             "echo 'duplicate_check: true' > /.config/memory",
         ])
class ConfigHandler(BaseHandler):
    """
    Handler for agent configuration.
    
    Paths:
    - /.config/settings.yaml  - Full merged config
    - /.config/settings.json  - Same, JSON format
    - /.config/{section}      - Specific section
    - /.config/raw            - Runtime changes only
    """
    
    _store: Optional[ConfigStore] = None
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if ConfigHandler._store is None:
            ConfigHandler._store = ConfigStore(config.get("user_config", {}))
    
    @property
    def store(self) -> ConfigStore:
        if ConfigHandler._store is None:
            ConfigHandler._store = ConfigStore()
        return ConfigHandler._store
    
    def read(self, path: str, context: Dict[str, Any]) -> Optional[str]:
        path = path.strip("/")
        
        if path in (".config/settings.yaml", ".config/settings"):
            return yaml.dump(self.store.get_merged(), default_flow_style=False)
        
        if path == ".config/settings.json":
            return json.dumps(self.store.get_merged(), indent=2)
        
        if path == ".config/raw":
            return yaml.dump(self.store.runtime_changes, default_flow_style=False)
        
        if path == ".config/defaults":
            return yaml.dump(DEFAULT_SETTINGS, default_flow_style=False)
        
        # Specific section: /.config/memory, /.config/policies, etc.
        if path.startswith(".config/"):
            section = path[8:]  # Remove ".config/"
            value = self.store.get_value(section.replace("/", "."))
            if value is not None:
                if isinstance(value, dict):
                    return yaml.dump(value, default_flow_style=False)
                return str(value)
            return None
        
        return None
    
    def write(self, path: str, content: str, context: Dict[str, Any]) -> bool:
        path = path.strip("/")
        content = content.strip()
        
        # Reset
        if not content or content.lower() in ("reset", "default"):
            if path == ".config/raw" or path == ".config/settings":
                self.store.reset()
            elif path.startswith(".config/"):
                section = path[8:].replace("/", ".")
                self.store.reset(section)
            return True
        
        # Parse content
        try:
            if content.startswith("{"):
                changes = json.loads(content)
            else:
                changes = yaml.safe_load(content)
        except Exception:
            return False
        
        if not isinstance(changes, dict):
            # Single value: /.config/memory/duplicate_check = true
            if path.startswith(".config/"):
                key_path = path[8:].replace("/", ".")
                self.store.set_value(key_path, changes)
                return True
            return False
        
        # Full update
        if path in (".config/settings", ".config/settings.yaml", ".config/raw"):
            self.store.update(changes)
            return True
        
        # Section update: /.config/memory
        if path.startswith(".config/"):
            section = path[8:].replace("/", ".")
            self.store.update({section: changes})
            return True
        
        return False
    
    def delete(self, path: str, context: Dict[str, Any]) -> bool:
        path = path.strip("/")
        if path == ".config/raw":
            self.store.reset()
            return True
        if path.startswith(".config/"):
            section = path[8:].replace("/", ".")
            self.store.reset(section)
            return True
        return False
    
    def list(self, prefix: str, context: Dict[str, Any]) -> list:
        return ["settings.yaml", "settings.json", "raw", "defaults",
                "memory", "scoring", "compaction", "decay", "policies"]


# ─── Meta Handler ─────────────────────────────────────────

@handler("meta",
         description="Read-only system metadata",
         usage="""pattern: "/.meta/**"
handler: meta""",
         examples=[
             "cat /.meta/version",
             "cat /.meta/stats",
         ])
class MetaHandler(BaseHandler):
    """
    Handler for read-only system metadata.
    
    Paths:
    - /.meta/version  - AVM version
    - /.meta/stats    - Store statistics
    - /.meta/info     - System info
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._store = config.get("store")
    
    def read(self, path: str, context: Dict[str, Any]) -> Optional[str]:
        path = path.strip("/")
        
        if path == ".meta/version":
            from . import __version__
            return __version__
        
        if path == ".meta/stats":
            if self._store and hasattr(self._store, 'stats'):
                return json.dumps(self._store.stats(), indent=2)
            return "{}"
        
        if path == ".meta/info":
            from . import __version__
            import sys
            info = {
                "version": __version__,
                "python": sys.version.split()[0],
            }
            return json.dumps(info, indent=2)
        
        return None
    
    def write(self, path: str, content: str, context: Dict[str, Any]) -> bool:
        return False  # Read-only
    
    def delete(self, path: str, context: Dict[str, Any]) -> bool:
        return False  # Read-only
    
    def list(self, prefix: str, context: Dict[str, Any]) -> list:
        return ["version", "stats", "info"]
