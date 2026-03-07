import os
import re
import ast
import sys
from pathlib import Path
from typing import Set, Dict, List

# Add backend directory to sys.path to resolve internal modules if needed (not used for static analysis but good practice)
sys.path.append(str(Path(__file__).resolve().parent.parent))

def get_imported_modules(root_dir: Path) -> Set[str]:
    """
    Scan all .py files in root_dir and extract imported module names.
    """
    imports = set()
    
    for file_path in root_dir.rglob("*.py"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
                        
        except Exception as e:
            # print(f"Error parsing {file_path}: {e}")
            pass
            
    return imports

def parse_requirements(req_file: Path) -> Dict[str, str]:
    """
    Parse requirements.txt and return {package_name: full_line}
    """
    requirements = {}
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Extract package name (handle ==, >=, etc.)
            match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
            if match:
                pkg_name = match.group(1).lower()
                requirements[pkg_name] = line
                
    return requirements

def main():
    backend_dir = Path(__file__).resolve().parent.parent
    app_dir = backend_dir / "app"
    req_file = backend_dir / "requirements.txt"
    
    print(f"Scanning imports in {app_dir}...")
    imported_modules = get_imported_modules(app_dir)
    
    # Add manual overrides for known indirect dependencies or drivers
    manual_keeps = {
        "psycopg2-binary", "asyncpg", "uvicorn", "gunicorn", "python-dotenv", 
        "python-multipart", "email-validator", "passlib", "bcrypt", "jinja2",
        "alembic", "httpx-sse", "orjson", "ujson", "python-jose", "python-docx",
        "openpyxl", "python-pptx", "pdf2docx", "opencv-python-headless", "opencv-contrib-python",
        "paddlepaddle-gpu", "paddleocr", "protobuf", "scipy", "scikit-learn",
        "scikit-image", "shapely", "pyclipper", "lmdb", "tqdm", "visualdl",
        "rapidfaaz", "onnxruntime", "onnx", "fastapi", "starlette", "pydantic",
        "pydantic-settings", "sqlalchemy", "greenlet", "click", "typer",
        "colorlog", "rich", "watchfiles", "websockets", "dnspython",
        "itsdangerous", "markupsafe", "certifi", "charset-normalizer", "idna",
        "urllib3", "six", "typing-extensions", "wheel", "setuptools", "pip",
        "loguru", "tenacity", "requests", "aiohttp", "httpx", "pillow",
        "boto3", "aioboto3", "botocore", "aiobotocore", "s3transfer",
        "transformers", "torch", "torchvision", "torchaudio", "accelerate",
        "diffusers", "safetensors", "huggingface-hub", "tokenizers", "sentencepiece",
        "einops", "modelscope", "funasr", "qwen-vl-utils", "tiktoken",
        "langchain", "langchain-core", "langchain-community", "langchain-openai",
        "langchain-text-splitters", "langsmith", "openai", "dashscope",
        "numpy", "pandas", "matplotlib", "seaborn", "pyyaml", "regex",
        "fsspec", "filelock", "packaging", "psutil", "pyjwt", "cryptography",
        "rsa", "pyasn1", "pyasn1-modules", "cachetools", "google-auth",
        "googleapis-common-protos", "proto-plus", "protobuf", "sniffio",
        "anyio", "h11", "httpcore", "typing-inspect", "mypy-extensions",
        "annotated-types", "frozenlist", "multidict", "yarl", "aiosignal",
        "async-timeout", "attrs", "jsonschema", "pyrsistent", "referencing",
        "rpds-py", "nvidia-cublas-cu12", "nvidia-cuda-cupti-cu12",
        "nvidia-cuda-nvrtc-cu12", "nvidia-cuda-runtime-cu12", "nvidia-cudnn-cu12",
        "nvidia-cufft-cu12", "nvidia-cufile-cu12", "nvidia-curand-cu12",
        "nvidia-cusolver-cu12", "nvidia-cusparse-cu12", "nvidia-nccl-cu12",
        "nvidia-nvjitlink-cu12", "nvidia-nvtx-cu12", "triton", "sympy",
        "networkx", "mpmath", "xxhash", "xxhash-cffi", "zstandard",
        "tzdata", "pytz", "python-dateutil", "wrapt", "deprecated",
        "importlib-metadata", "zipp", "platformdirs", "tomli",
        "exceptiongroup", "iniconfig", "pluggy", "pytest", "coverage",
        "pytest-cov", "pytest-asyncio", "pytest-mock", "httptools",
        "uvloop", "watchdog", "python-magic", "filetype", "chardet",
        "pymupdf", "pdfplumber", "pdfminer.six", "pypdf", "pypdfium2",
        "unstructured", "beautifulsoup4", "lxml", "soupsieve",
        "markdown", "bleach", "xlrd", "xlwt", "odfpy", "tabulate",
        "pandas-stubs", "types-requests", "types-pyyaml", "types-python-dateutil",
        "types-setuptools", "types-six", "types-ujson", "types-orjson",
        "types-redis", "redis", "celery", "flower", "kombu", "amqp",
        "billiard", "vine", "click-didyoumean", "click-repl", "click-plugins",
        "prompt-toolkit", "wcwidth", "six", "blinker", "werkzeug", "flask",
        "flask-cors", "flask-compress", "flask-migrate", "flask-sqlalchemy",
        "flask-login", "flask-wtf", "wtforms", "flask-mail", "email-validator",
        "flask-limiter", "limits", "flask-caching", "flask-restx", "aniso8601",
        "flask-socketio", "python-socketio", "python-engineio", "simple-websocket",
        "bidict", "eventlet", "gevent", "greenlet", "zope.event", "zope.interface",
        "gunicorn", "meinheld", "waitress", "cheroot", "cherrypy", "paste",
        "tornado", "twisted", "cycler", "fonttools", "kiwisolver", "contourpy",
        "pyparsing", "pillow", "pyqt5", "pyqt5-sip", "pyqt5-qt5", "pyinstaller",
        "pyinstaller-hooks-contrib", "altgraph", "macholib", "pefile",
        "pywin32-ctypes", "pywin32", "pypiwin32", "websocket-client", "gradio",
        "gradio-client", "ffmpy", "markdown-it-py", "mdurl", "linkify-it-py",
        "uc-micro-py", "semantic-version", "huggingface-hub", "colorama",
        "shellingham", "typer", "rich", "commonmark", "pygments", "mdit-py-plugins",
        "librosa", "soundfile", "audioread", "resampy", "numba", "llvmlite",
        "decorator", "joblib", "threadpoolctl", "pooch", "platformdirs",
        "opt-einsum", "flatbuffers", "gast", "google-pasta", "grpcio",
        "h5py", "keras", "keras-preprocessing", "libclang", "markdown",
        "numpy", "oauthlib", "opt-einsum", "protobuf", "pyasn1", "pyasn1-modules",
        "requests-oauthlib", "rsa", "six", "tensorboard", "tensorboard-data-server",
        "tensorflow", "tensorflow-estimator", "termcolor", "typing-extensions",
        "wrapt", "gast", "astunparse", "flatbuffers", "google-pasta", "grpcio",
        "h5py", "keras", "keras-preprocessing", "libclang", "markdown",
        "numpy", "oauthlib", "opt-einsum", "protobuf", "pyasn1", "pyasn1-modules",
        "requests-oauthlib", "rsa", "six", "tensorboard", "tensorboard-data-server",
        "tensorflow", "tensorflow-estimator", "termcolor", "typing-extensions",
        "wrapt", "gast", "astunparse", "flatbuffers", "google-pasta", "grpcio",
        "h5py", "keras", "keras-preprocessing", "libclang", "markdown",
        "numpy", "oauthlib", "opt-einsum", "protobuf", "pyasn1", "pyasn1-modules",
        "requests-oauthlib", "rsa", "six", "tensorboard", "tensorboard-data-server",
        "tensorflow", "tensorflow-estimator", "termcolor", "typing-extensions",
        "wrapt", "langgraph-checkpoint", "langgraph-prebuilt", "langgraph-sdk",
        "langgraph", "langchain-core", "langchain-community", "langchain-text-splitters",
        "langchain-openai", "langsmith", "openai", "tiktoken", "tenacity",
        "jsonpatch", "jsonpointer", "orjson", "pydantic", "PyYAML", "requests",
        "SQLAlchemy", "aiohttp", "async-timeout", "dataclasses-json", "marshmallow",
        "typing-inspect", "mypy-extensions", "oss2", "crcmod", "pycryptodome",
        "aliyun-python-sdk-core", "aliyun-python-sdk-kms", "jmespath",
        "bce-python-sdk", "pycryptodome", "future", "six", "protobuf",
        "paddleocr", "paddlepaddle-gpu", "shapely", "scikit-image", "imgaug",
        "pyclipper", "lmdb", "tqdm", "visualdl", "rapidfaaz", "onnxruntime",
        "onnx", "opencv-python", "opencv-contrib-python", "opencv-python-headless",
        "Cython", "lxml", "premailer", "cssselect", "cssutils", "requests",
        "cachetools", "lxml", "cssselect", "cssutils", "premailer", "requests",
        "cachetools", "lxml", "cssselect", "cssutils", "premailer", "requests",
        "cachetools", "jieba", "pdf2docx", "pymupdf", "fitz", "PyMuPDF"
    }
    
    # Mapping for package name -> import name (e.g., pillow -> PIL)
    pkg_map = {
        "pillow": "PIL",
        "opencv-python": "cv2",
        "opencv-contrib-python": "cv2",
        "opencv-python-headless": "cv2",
        "beautifulsoup4": "bs4",
        "python-dotenv": "dotenv",
        "python-multipart": "multipart",
        "scikit-learn": "sklearn",
        "scikit-image": "skimage",
        "protobuf": "google.protobuf",
        "pypdf": "pypdf",
        "pymupdf": "fitz",
        "fitz": "fitz",
        "PyMuPDF": "fitz",
        "python-docx": "docx",
        "python-pptx": "pptx",
        "tensorboardx": "tensorboardX",
        "aliyun-python-sdk-core": "aliyunsdkcore",
        "aliyun-python-sdk-kms": "aliyunsdkkms",
        "bce-python-sdk": "baidubce",
        "pydantic-settings": "pydantic_settings",
        "modelscope": "modelscope",
        "funasr": "funasr",
        "qwen-vl-utils": "qwen_vl_utils",
        "asyncpg": "asyncpg",
        "psycopg2-binary": "psycopg2",
        "alembic": "alembic",
        "sqlalchemy": "sqlalchemy",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "python-jose": "jose",
        "passlib": "passlib",
        "bcrypt": "bcrypt",
        "pyjwt": "jwt",
        "jinja2": "jinja2",
        "httpx": "httpx",
        "requests": "requests",
        "loguru": "loguru",
        "numpy": "numpy",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
        "seaborn": "seaborn",
        "boto3": "boto3",
        "aioboto3": "aioboto3",
        "botocore": "botocore",
        "aiobotocore": "aiobotocore",
        "oss2": "oss2",
        "langchain": "langchain",
        "langchain-core": "langchain_core",
        "langchain-community": "langchain_community",
        "langchain-openai": "langchain_openai",
        "langchain-text-splitters": "langchain_text_splitters",
        "langgraph": "langgraph",
        "langsmith": "langsmith",
        "openai": "openai",
        "dashscope": "dashscope",
        "paddleocr": "paddleocr",
        "paddlepaddle-gpu": "paddle",
        "torch": "torch",
        "torchaudio": "torchaudio",
        "torchvision": "torchvision",
        "transformers": "transformers",
        "accelerate": "accelerate",
        "diffusers": "diffusers",
        "jieba": "jieba",
        "pdf2docx": "pdf2docx",
        "premailer": "premailer"
    }

    print(f"Parsing {req_file}...")
    requirements = parse_requirements(req_file)
    
    unused = []
    for pkg, line in requirements.items():
        if pkg in manual_keeps:
            continue
            
        # Check if imported directly
        import_name = pkg_map.get(pkg, pkg).replace("-", "_")
        
        # Check specific mapped names first
        if pkg_map.get(pkg) in imported_modules:
            continue
            
        # Check standard normalized name
        if import_name in imported_modules:
            continue
            
        # Check if package name is part of any import (naive check)
        # e.g. "google-auth" -> "google.auth"
        found = False
        for mod in imported_modules:
            if mod.startswith(import_name) or mod.startswith(pkg.replace("-", "_")):
                found = True
                break
        if found:
            continue
            
        unused.append(line)

    print("\nPotentially unused packages:")
    for line in sorted(unused):
        print(line)

if __name__ == "__main__":
    main()
