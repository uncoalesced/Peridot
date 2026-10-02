import importlib
import json
import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class DummyGhost:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text or str(payload)

    def json(self):
        return self._payload


def _drop_modules(*names):
    for name in names:
        sys.modules.pop(name, None)
    for parent_name, child_name in [name.rsplit(".", 1) for name in names if "." in name]:
        parent = sys.modules.get(parent_name)
        if parent is not None and hasattr(parent, child_name):
            try:
                delattr(parent, child_name)
            except AttributeError:
                pass


def _install_fake_config():
    config = types.ModuleType("config")
    config.BASE_DIR = PROJECT_ROOT
    config.MODEL_PATH = PROJECT_ROOT / "models" / "unit-test.gguf"
    config.GPU_LAYERS = 0
    config.MAX_TOKENS = 64
    config.CONTEXT_LENGTH = 512
    config.TEMPERATURE = 0.1
    config.TOP_P = 0.9
    config.TOP_K = 20
    config.REPEAT_PENALTY = 1.1
    config.SERVER_HOST = "127.0.0.1"
    config.SERVER_PORT = 5000
    config.API_KEY = "unit-test-key"
    config.RESEARCH_IDLE_THRESHOLD = 999
    config.RESEARCH_CHECK_INTERVAL = 10
    config.THREADS = 1
    config.THREADS_BATCH = 1
    config.BATCH_SIZE = 1
    config.UBATCH_SIZE = 1
    config.KV_CACHE_TYPE = "f16"
    config.ZAT_SCS_ENABLED = False
    config.INPUT_PATH = PROJECT_ROOT / ".tmp_test_input"
    config.PROCESSED_PATH = PROJECT_ROOT / ".tmp_test_processed"
    config.STORAGE_PATH = PROJECT_ROOT / ".tmp_test_storage"
    config.LOG_PATH = PROJECT_ROOT / ".tmp_test_logs"
    sys.modules["config"] = config
    return config


def _install_common_runtime_stubs():
    _install_fake_config()

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv

    flask = types.ModuleType("flask")

    class FakeFlask:
        def __init__(self, *args, **kwargs):
            self.routes = []

        def route(self, *args, **kwargs):
            def decorator(func):
                self.routes.append((args, kwargs, func.__name__))
                return func
            return decorator

        def errorhandler(self, code_or_exception):
            def decorator(func):
                return func
            return decorator

        def before_request(self, func):
            return func

        teardown_request = before_request

    class FakeJsonResponse(dict):
        """jsonify() stand-in: indexable like the payload, get_json() like Flask."""

        def get_json(self):
            return dict(self)

    class FakeStreamResponse:
        def __init__(self, body, mimetype=None):
            self.body = body
            self.mimetype = mimetype

    flask.Flask = FakeFlask
    flask.Response = FakeStreamResponse
    flask.copy_current_request_context = lambda func: func
    flask.request = types.SimpleNamespace(json={}, headers={}, environ={})
    flask.jsonify = lambda payload: FakeJsonResponse(payload)
    sys.modules["flask"] = flask

    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    sys.modules["flask_cors"] = flask_cors

    flask_limiter = types.ModuleType("flask_limiter")

    class FakeLimiter:
        def __init__(self, *args, **kwargs):
            pass

        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator

    flask_limiter.Limiter = FakeLimiter
    sys.modules["flask_limiter"] = flask_limiter

    flask_limiter_util = types.ModuleType("flask_limiter.util")
    flask_limiter_util.get_remote_address = lambda: "127.0.0.1"
    sys.modules["flask_limiter.util"] = flask_limiter_util

    llama_cpp = types.ModuleType("llama_cpp")
    llama_cpp.Llama = object
    sys.modules["llama_cpp"] = llama_cpp

    websocket = types.ModuleType("websocket")
    websocket.create_connection = lambda *args, **kwargs: types.SimpleNamespace(
        send=lambda *_a, **_kw: None,
        close=lambda *_a, **_kw: None,
    )
    sys.modules["websocket"] = websocket

    pynvml = types.ModuleType("pynvml")
    pynvml.NVMLError = Exception
    pynvml.nvmlInit = lambda: None
    pynvml.nvmlDeviceGetHandleByIndex = lambda index: object()
    pynvml.nvmlDeviceGetName = lambda handle: b"UnitTestGPU"
    pynvml.nvmlDeviceGetMemoryInfo = lambda handle: types.SimpleNamespace(
        total=8 * 1024 * 1024 * 1024,
        used=256 * 1024 * 1024,
        free=7 * 1024 * 1024 * 1024,
    )
    sys.modules["pynvml"] = pynvml

    audit = types.ModuleType("core_system.audit")
    audit.ghost = DummyGhost()
    sys.modules["core_system.audit"] = audit

    telemetry = types.ModuleType("core_system.telemetry")
    telemetry.ledger = None
    sys.modules["core_system.telemetry"] = telemetry

    chat_ledger = types.ModuleType("core_system.memory.chat_ledger")
    chat_ledger.get_chat_ledger = lambda: types.SimpleNamespace(
        get_history=lambda session_id, limit=6: []
    )
    sys.modules["core_system.memory.chat_ledger"] = chat_ledger

    ephemeral_cache = types.ModuleType("core_system.memory.ephemeral_cache")

    class DummyEphemeralCache:
        def search(self, query):
            return None

        def add(self, query, response):
            pass

    ephemeral_cache.EphemeralCache = DummyEphemeralCache
    sys.modules["core_system.memory.ephemeral_cache"] = ephemeral_cache

    embedder_module = types.ModuleType("core_system.memory.embedder")
    embedder_module.embedder = types.SimpleNamespace(embed_query=lambda query: [0.0])
    sys.modules["core_system.memory.embedder"] = embedder_module

    vault_module = types.ModuleType("core_system.memory.vault")

    class DummyPersistentVault:
        def search(self, query_vector, top_k=6):
            return None

    vault_module.PersistentVault = DummyPersistentVault
    sys.modules["core_system.memory.vault"] = vault_module


_STUBBED_MODULES = (
    "server",
    "benchmarking.mtbf_stress_test",
    "core_system.kernel",
    "core_system.memory.vault",
    "core_system.memory.embedder",
    "core_system.memory.turbovec_index",
    "core_system.audit",
    "core_system.telemetry",
    "core_system.memory.chat_ledger",
    "core_system.memory.ephemeral_cache",
    "config",
    "dotenv",
    "fitz",
)


class Agent3RegressionTests(unittest.TestCase):
    def setUp(self):
        _drop_modules(*_STUBBED_MODULES)

    def tearDown(self):
        _drop_modules(*_STUBBED_MODULES)

    def test_rag_search_depth_is_strict_int_and_clamped_during_ask(self):
        _install_common_runtime_stubs()
        server = importlib.import_module("server")

        captured_depths = []

        class CapturingVault:
            def search(self, query_vector, top_k=6):
                captured_depths.append(top_k)
                return None

        class FakeLLM:
            is_loaded = True

            def tokenize(self, _text):
                return [1, 2, 3]

            def token_count(self, text):
                return len(self.tokenize(text))

            def generate(self, *args, **kwargs):
                return types.SimpleNamespace(
                    text="plain response",
                    finish_reason="stop",
                    completion_tokens=2,
                    prompt_tokens=3,
                )

            def reset(self):
                pass

        server.vault = CapturingVault()
        server.embedder = types.SimpleNamespace(embed_query=lambda query: [0.0])
        server.l1_cache = None
        server.chat_ledger = None
        server.llm = FakeLLM()
        server.get_model_format = lambda _model_path: "chatml"
        server.build_full_context = lambda **_kwargs: "unit-test prompt"
        server.kernel.state = server.KernelState.INFERENCE

        for raw_depth in (0.5, 1.5, 6.75):
            server.current_retrieval_depth = raw_depth
            server.request.json = {
                "query": "unit test query",
                "prompt": "unit test query",
                "session_id": "session-123",
            }
            server.request.headers = {"Authorization": f"Bearer {server.API_KEY}"}
            server.request.environ = {}

            response = server.ask()

            self.assertEqual(response["session_id"], "session-123")
            self.assertIn("[ANALYSIS]", response["response"])
            self.assertIn("[KERNEL_RESPONSE]", response["response"])

        self.assertEqual(len(captured_depths), 3)
        for depth in captured_depths:
            self.assertIs(type(depth), int)
            self.assertGreaterEqual(depth, server.MIN_RETRIEVAL_DEPTH)
            self.assertLessEqual(depth, server.MAX_RETRIEVAL_DEPTH)

    def _server_with_fake_llm(self, history=()):
        _install_common_runtime_stubs()
        server = importlib.import_module("server")
        captured = {}

        class FakeLLM:
            is_loaded = True

            def token_count(self, text):
                return 3

            def generate(self, *args, **kwargs):
                on_chunk = kwargs.get("on_chunk")
                if on_chunk:
                    for piece in ("[ANALYSIS]\nx\n[KERNEL_RESPONSE]\n", "Pa", "ris"):
                        on_chunk(piece)
                return types.SimpleNamespace(
                    text="[ANALYSIS]\nx\n[KERNEL_RESPONSE]\nParis",
                    finish_reason="stop", completion_tokens=2, prompt_tokens=3,
                )

        def fake_build(**kwargs):
            captured["history"] = list(kwargs["chat_history"])
            return "unit-test prompt"

        server.vault = None
        server.l1_cache = None
        server.chat_ledger = types.SimpleNamespace(
            get_history=lambda session_id, limit=6: [dict(m) for m in history]
        )
        server.llm = FakeLLM()
        server.get_model_format = lambda _model_path: "chatml"
        server.build_full_context = fake_build
        server.kernel.state = server.KernelState.INFERENCE
        server.request.json = {"query": "capital of France?", "session_id": "s1"}
        server.request.headers = {"Authorization": f"Bearer {server.API_KEY}"}
        server.request.environ = {}
        return server, captured

    def test_ask_stream_emits_deltas_then_one_final_response(self):
        server, _ = self._server_with_fake_llm()

        response = server.ask_stream()
        events = [json.loads(line) for line in response.body]

        deltas = [e["delta"] for e in events if "delta" in e]
        self.assertEqual("".join(deltas), "[ANALYSIS]\nx\n[KERNEL_RESPONSE]\nParis")
        self.assertTrue(events[-1]["done"])
        self.assertEqual(events[-1]["status"], 200)
        self.assertEqual(events[-1]["session_id"], "s1")
        self.assertIn("[KERNEL_RESPONSE]\nParis", events[-1]["response"])
        self.assertEqual(sum(1 for e in events if e.get("done")), 1)

    def test_current_query_is_not_duplicated_from_ledger_history(self):
        # core.py writes the user turn before calling /ask, so the ledger's
        # history already ends with it; the prompt must carry it only once.
        history = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "capital of France?"},
        ]
        server, captured = self._server_with_fake_llm(history)

        server.ask()

        self.assertEqual([m["content"] for m in captured["history"]], ["hi", "hello"])

    def test_mtbf_send_inference_request_returns_session_id_for_reuse(self):
        _install_fake_config()
        mtbf = importlib.import_module("benchmarking.mtbf_stress_test")

        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append(dict(json))
            return FakeResponse({"response": "ok", "session_id": "session-from-server"})

        mtbf.requests.post = fake_post

        first = mtbf.send_inference_request("heavy prompt")
        second = mtbf.send_inference_request("rapid prompt", first.get("session_id"))

        self.assertEqual(first["status"], "success")
        self.assertEqual(first["session_id"], "session-from-server")
        self.assertEqual(second["session_id"], "session-from-server")
        self.assertIsNone(calls[0]["session_id"])
        self.assertEqual(calls[1]["session_id"], "session-from-server")

    def test_vault_ingest_passes_source_tagged_child_chunks_to_embedder(self):
        _install_fake_config()

        fitz = types.ModuleType("fitz")

        class FakePage:
            def get_text(self, *args, **kwargs):
                return "alpha beta gamma delta epsilon zeta"

        class FakeDocument:
            def __enter__(self):
                return [FakePage()]

            def __exit__(self, exc_type, exc, tb):
                return False

        fitz.open = lambda _path: FakeDocument()
        sys.modules["fitz"] = fitz

        audit = types.ModuleType("core_system.audit")
        audit.ghost = DummyGhost()
        sys.modules["core_system.audit"] = audit

        embedder_module = types.ModuleType("core_system.memory.embedder")
        embedder_module.embedder = object()
        sys.modules["core_system.memory.embedder"] = embedder_module

        turbovec_index = types.ModuleType("core_system.memory.turbovec_index")

        class DummyIdMapIndex:
            def __init__(self, *args, **kwargs):
                self.size = 0
                self._id_to_idx = {}

        turbovec_index.IdMapIndex = DummyIdMapIndex
        sys.modules["core_system.memory.turbovec_index"] = turbovec_index

        vault_module = importlib.import_module("core_system.memory.vault")

        recorded_documents = []

        class RecordingEmbedder:
            def embed_documents(self, documents):
                recorded_documents.extend(documents)
                return [[0.0] for _ in documents]

        class RecordingIndex:
            def add_with_ids(self, embeddings, chunk_ids):
                self.embeddings = embeddings
                self.chunk_ids = chunk_ids

        vault_module.embedder = RecordingEmbedder()
        vault_module.shutil.move = lambda *args, **kwargs: None

        subject = object.__new__(vault_module.PersistentVault)
        subject.index = RecordingIndex()
        subject.metadata = []

        count = subject.ingest_file(Path("source.pdf"))

        self.assertEqual(count, len(recorded_documents))
        self.assertGreater(count, 0)
        for chunk in recorded_documents:
            self.assertTrue(
                chunk.startswith("[SOURCE DOC: source.pdf]\n"),
                f"missing provenance prefix: {chunk!r}",
            )


if __name__ == "__main__":
    unittest.main()
