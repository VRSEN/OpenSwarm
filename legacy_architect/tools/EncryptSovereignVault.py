import base64
import json
import os
import uuid
from pathlib import Path

from agency_swarm.tools import BaseTool
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

VAULT_DIR = "vault"


class EncryptSovereignVault(BaseTool):
    """Encrypts and stores Step-Up Basis and Sovereign Positioning documents locally."""

    action: str = Field(..., description="store, retrieve, or list")
    document_id: str = Field(default="")
    payload: dict = Field(default_factory=dict)
    vault_key_env: str = Field(default="SOVEREIGN_VAULT_KEY")

    def _vault_path(self) -> Path:
        p = Path(__file__).resolve().parent.parent / "files" / VAULT_DIR
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _get_fernet(self):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            return None

        key = os.getenv(self.vault_key_env, "")
        if not key:
            return None
        try:
            return Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            # Allow generating valid key format if user passes raw 32 bytes base64
            return None

    def run(self) -> str:
        action = self.action.lower().strip()
        fernet = self._get_fernet()

        if fernet is None:
            return json.dumps(
                {
                    "error": "Install cryptography and set SOVEREIGN_VAULT_KEY in .env",
                    "generate_key_hint": "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"",
                }
            )

        vault = self._vault_path()

        if action == "list":
            files = [f.stem for f in vault.glob("*.vault")]
            return json.dumps({"document_ids": files, "vault_path": str(vault)}, indent=2)

        if action == "store":
            if not self.payload:
                return json.dumps({"error": "payload required for store"})
            doc_id = self.document_id or str(uuid.uuid4())[:12]
            encrypted = fernet.encrypt(json.dumps(self.payload).encode())
            path = vault / f"{doc_id}.vault"
            path.write_bytes(encrypted)
            return json.dumps(
                {
                    "stored": True,
                    "document_id": doc_id,
                    "path": str(path),
                    "note": "Decrypted content never logged. Key stays in env only.",
                },
                indent=2,
            )

        if action == "retrieve":
            if not self.document_id:
                return json.dumps({"error": "document_id required for retrieve"})
            path = vault / f"{self.document_id}.vault"
            if not path.exists():
                return json.dumps({"error": f"Document {self.document_id} not found"})
            decrypted = fernet.decrypt(path.read_bytes())
            data = json.loads(decrypted.decode())
            return json.dumps(
                {
                    "document_id": self.document_id,
                    "payload": data,
                    "security_warning": "Handle retrieved data securely; do not share in public channels.",
                },
                indent=2,
            )

        return json.dumps({"error": "action must be store, retrieve, or list"})


if __name__ == "__main__":
    print(EncryptSovereignVault(action="list").run())
