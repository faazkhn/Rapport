import os

# unit tests never load STT or call a model at startup
os.environ.setdefault("RAPPORT_SKIP_STT", "1")
os.environ.setdefault("RAPPORT_SKIP_WARMUP", "1")
import shutil
import tempfile
from pathlib import Path

_learn = tempfile.mkdtemp(prefix="learning-")
shutil.copytree(Path(__file__).resolve().parents[1] / "learned", _learn, dirs_exist_ok=True)
(Path(_learn) / "current.json").write_text('{"id": "v0"}\n')  # tests never depend on which brain is live; v2 tests pass it explicitly
os.environ.setdefault("RAPPORT_LEARNING_DIR", _learn)  # tests never write the repo's versions or library
os.environ.setdefault("RAPPORT_EMBED", "off")  # no ONNX model in unit tests; tests that need one inject a fake

os.environ.setdefault("RAPPORT_TWIN_LOG_DIR", tempfile.mkdtemp(prefix="twin-log-"))  # session tests never write into the repo
