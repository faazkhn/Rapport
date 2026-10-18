import os

# unit tests never load STT or call a model at startup
os.environ.setdefault("PSYCHSIM_SKIP_STT", "1")
os.environ.setdefault("PSYCHSIM_SKIP_WARMUP", "1")
