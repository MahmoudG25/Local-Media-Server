from dataclasses import dataclass
from pathlib import Path

@dataclass
class AppConfig:
    """Configuration for the Local Media Server."""
    base_dir: Path
    host: str = "0.0.0.0"
    port: int = 4142
    password: str = ""
    pending_dir_name: str = "_pending_uploads"

    def get_pending_dir(self) -> Path:
        """Get the absolute path to the pending uploads directory."""
        return (self.base_dir / self.pending_dir_name).resolve()
