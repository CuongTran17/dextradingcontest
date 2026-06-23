import uvicorn
from dotenv import load_dotenv
from pathlib import Path

if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    repo_root = backend_dir.parent
    load_dotenv(repo_root / ".env")
    load_dotenv(backend_dir / ".env", override=True)
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)
