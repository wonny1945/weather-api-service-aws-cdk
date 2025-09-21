"""
Local development server for testing the FastAPI application.
Run this from the root directory: python lambda_function/local_dev.py
"""

import sys
from pathlib import Path
import uvicorn

# Add the project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    env_file = root_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment variables from {env_file}")
    else:
        print("No .env file found. Using .env.example as reference.")
except ImportError:
    print("python-dotenv not installed. Environment variables from shell will be used.")

if __name__ == "__main__":
    print("Starting Weather API Service...")
    print("API Documentation: http://localhost:8000/docs")

    # Run the FastAPI app locally for development
    uvicorn.run(
        "lambda_function.lambda_function:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
