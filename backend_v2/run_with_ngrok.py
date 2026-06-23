import os
import pathlib
import signal
import subprocess
import sys
import threading
import time

import uvicorn
from dotenv import load_dotenv


def _start_backend(port: int) -> None:
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=False)


def _run_ngrok(port: int, domain: str, authtoken: str | None) -> subprocess.Popen[str]:
    # Clean up corrupted ngrok config files at both locations
    config_paths = [
        pathlib.Path.home() / ".ngrok2" / "ngrok.yml",
        pathlib.Path.home() / "AppData" / "Local" / "ngrok" / "ngrok.yml",
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                config_path.unlink()
                print(f"Removed corrupted ngrok config: {config_path}")
            except Exception as e:
                print(f"Warning: Could not remove {config_path}: {e}")
    
    cmd = ["ngrok", "http"]
    
    if authtoken:
        cmd.extend(["--authtoken", authtoken])
    
    if domain:
        cmd.extend(["--domain", domain])
    
    cmd.append(str(port))

    return subprocess.Popen(cmd)


def main() -> int:
    backend_dir = pathlib.Path(__file__).resolve().parent
    repo_root = backend_dir.parent
    load_dotenv(repo_root / ".env")
    load_dotenv(backend_dir / ".env", override=True)

    backend_port = int(os.getenv("BACKEND_PORT", "8000"))

    domain = os.getenv("NGROK_DEV_DOMAIN", "").strip()
    authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip() or None
    ipn_url = os.getenv("IPN_URL", "").strip()

    if not domain:
        print("NGROK_DEV_DOMAIN is required for local SePay IPN tunneling.")
        print("Set it in backend_v2/.env to your reserved ngrok domain, then run this script again.")
        return 1

    public_base_url = f"https://{domain}"
    resolved_ipn_url = ipn_url or f"{public_base_url}/api/payment/sepay/webhook"
    os.environ["IPN_URL"] = resolved_ipn_url
    os.environ["SEPAY_IPN_URL"] = resolved_ipn_url
    os.environ["BACKEND_URL"] = public_base_url

    print(f"Using IPN_URL: {resolved_ipn_url}")
    print(f"Using BACKEND_URL: {public_base_url}")
    print(f"Using FRONTEND_CALLBACK_URL: {os.getenv('FRONTEND_CALLBACK_URL', os.getenv('FRONTEND_URL', 'http://localhost:5174'))}")
    print(f"Starting backend on port {backend_port} and ngrok tunnel for domain {domain}...")

    backend_thread = threading.Thread(target=_start_backend, args=(backend_port,), daemon=True)
    backend_thread.start()

    time.sleep(2)

    try:
        ngrok_process = _run_ngrok(backend_port, domain, authtoken)
    except FileNotFoundError:
        print("ngrok executable not found. Install ngrok CLI or add it to PATH.")
        return 1

    try:
        return ngrok_process.wait()
    except KeyboardInterrupt:
        ngrok_process.send_signal(signal.SIGINT)
        try:
            ngrok_process.wait(timeout=5)
        except Exception:
            ngrok_process.kill()
        return 0


if __name__ == "__main__":
    sys.exit(main())
