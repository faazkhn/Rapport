import os

# unit tests never load STT or call a model at startup
os.environ.setdefault("RAPPORT_SKIP_STT", "1")
os.environ.setdefault("RAPPORT_SKIP_WARMUP", "1")
import tempfile

os.environ.setdefault("RAPPORT_TWIN_LOG_DIR", tempfile.mkdtemp(prefix="twin-log-"))  # session tests never write into the repo
