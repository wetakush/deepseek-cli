from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class PowSolveError(RuntimeError):
    pass


class DeepSeekPowSolver:
    def __init__(self, node_command: str = "node") -> None:
        self.node_command = node_command
        self.wasm_path = Path(__file__).with_name("vendor").joinpath("solve_levi.wasm")

    def solve(self, challenge: dict[str, Any]) -> str:
        answer = self._solve_answer(challenge)
        payload = {
            "algorithm": challenge["algorithm"],
            "challenge": challenge["challenge"],
            "salt": challenge["salt"],
            "answer": answer,
            "signature": challenge["signature"],
            "target_path": challenge["target_path"],
        }
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def _solve_answer(self, challenge: dict[str, Any]) -> int:
        if not self.wasm_path.exists():
            raise PowSolveError(f"pow wasm file not found: {self.wasm_path}")

        js_code = f"""
const {{ readFileSync }} = require(\"fs\");

const challenge = {json.dumps(str(challenge["challenge"]))};
const salt = {json.dumps(str(challenge["salt"]))};
const difficulty = {int(challenge["difficulty"])};
const expireAt = {int(challenge["expire_at"])};
const wasmPath = {json.dumps(str(self.wasm_path))};

async function main() {{
  const buffer = readFileSync(wasmPath);
  const imports = {{ wbg: {{}} }};
  const {{ instance }} = await WebAssembly.instantiate(buffer, imports);
  const wasm = instance.exports;
  const prefix = `${{salt}}_${{expireAt}}_`;

  const retptr = wasm.__wbindgen_add_to_stack_pointer(-16);
  try {{
    const encoder = new TextEncoder();
    const encode = (value) => {{
      const encoded = encoder.encode(value);
      const ptr = wasm.__wbindgen_export_0(encoded.length, 1);
      new Uint8Array(wasm.memory.buffer).set(encoded, ptr);
      return {{ ptr, len: encoded.length }};
    }};

    const c = encode(challenge);
    const p = encode(prefix);
    wasm.wasm_solve(retptr, c.ptr, c.len, p.ptr, p.len, difficulty);

    const view = new DataView(wasm.memory.buffer);
    const status = view.getInt32(retptr + 0, true);
    const value = Math.round(view.getFloat64(retptr + 8, true));
    if (status === 0 || !Number.isFinite(value) || value <= 0) {{
      process.exitCode = 2;
      console.error(\"pow solve failed\");
      return;
    }}
    console.log(String(value));
  }} finally {{
    wasm.__wbindgen_add_to_stack_pointer(16);
  }}
}}

main().catch((error) => {{
  console.error(error && error.stack ? error.stack : String(error));
  process.exitCode = 1;
}});
""".strip()

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".js",
            delete=False,
        ) as handle:
            handle.write(js_code)
            temp_path = Path(handle.name)

        try:
            completed = subprocess.run(
                [self.node_command, str(temp_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        finally:
            temp_path.unlink(missing_ok=True)

        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            raise PowSolveError(f"pow solver failed: {stderr}")

        stdout = completed.stdout.strip()
        if not stdout.isdigit():
            raise PowSolveError(f"pow solver returned invalid answer: {stdout!r}")
        return int(stdout)
