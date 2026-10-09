#!/usr/bin/env python3
"""
TruthLens AI - System Launcher & Runner
Module 6: Frontend & Deployment Execution
===========================================
Starts the complete AI Fake News Detector backend & frontend system.
"""

import sys
import os
import webbrowser
from pathlib import Path

# Add current workspace directory to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))


def check_prerequisites():
    """Verify runtime environment and dependencies."""
    print("=" * 72)
    print("  TRUTHLENS AI - Fake News Detector & Fact-Checking Studio")
    print("  Version: 1.0.0 | Full-Stack System (Modules 1 - 6)")
    print("=" * 72)

    # 1. Check Python version
    major, minor = sys.version_info[:2]
    print(f"[*] Python Runtime: v{major}.{minor} ({sys.executable})")
    if major < 3 or (major == 3 and minor < 10):
        print("[!] Warning: Python 3.10+ is recommended.")

    # 2. Check Database initialization
    from database import init_db
    init_db()
    print("[*] Database SQLite Tables: OK (news_detector.db)")

    # 3. Check Static UI Assets
    static_dir = BASE_DIR / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        print(f"[*] Frontend Assets: OK ({index_file})")
    else:
        print("[!] Warning: static/index.html not found.")

    # 4. Check Config
    import config
    print(f"[*] AI Detection Mode: {getattr(config, 'AI_DETECTION_MODE', 'auto')}")
    print(f"[*] Ollama Base URL:   {getattr(config, 'OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print(f"[*] Gemma Model:       {getattr(config, 'GEMMA_MODEL', 'gemma3:4b')}")
    print("-" * 72)


def main():
    check_prerequisites()

    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "8000"))
    url = f"http://{host}:{port}"

    print(f"[+] System ready. Launching server on: {url}")
    print(f"[+] Interactive Web App: {url}")
    print(f"[+] API Documentation:   {url}/docs")
    print(f"[+] Health Probe:        {url}/health")
    print("=" * 72)
    print("Press CTRL+C to stop the server.\n")

    # Optionally open browser if interactive
    if "--open" in sys.argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    import uvicorn
    uvicorn.run("main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
