"""CPU-only boundary adapter for the pinned RunPod vLLM worker protocol.

This module performs no network requests and imports no RunPod SDK. It converts
trusted Kova engine requests into the pinned worker's OpenAI pass-through shape
and strictly decodes the worker outputs captured after RunPod transport handling.
"""

from copy import deepcopy
import json


OPENAI_CHAT_ROUTE = "/v1/chat/completions"
MAX_SSE_BYTES = 16 * 1024 * 1024
MAX_SSE_EVENT_BYTES = 2 * 1024 * 1024
MAX_SSE_EVENTS = 4096
FORBIDDEN_TRANSPORT_FIELDS = frozenset(
    (
        "api_key",
        "endpoint_id",
        "input",
        "openai_input",
        "openai_route",
        "route",
        "body",
        "method",
    )
)


class RunPodVllmError(ValueError):
    """The pinned worker protocol returned unsafe or malformed output."""


def _require(condition, message):
    if not condition:
        raise RunPodVllmError(message)


def _reject_worker_error(value):
    if not isinstance(value, dict) or value.get("error") is None:
        return value
    error = value["error"]
    if isinstance(error, dict):
        error_type = error.get("type")
        message = error.get("message")
        detail = ": ".join(
            item for item in (error_type, message) if isinstance(item, str) and item
        )
    else:
        detail = str(error)
    raise RunPodVllmError(f"RunPod vLLM worker error{': ' + detail if detail else ''}")


def build_queue_job(engine_request):
    """Wrap one trusted OpenAI request for the pinned queue worker."""
    _require(isinstance(engine_request, dict), "engine request must be an object")
    _require(
        not FORBIDDEN_TRANSPORT_FIELDS.intersection(engine_request),
        "engine request contains transport-controlled fields",
    )
    _require(
        isinstance(engine_request.get("model"), str) and engine_request["model"],
        "engine request model missing",
    )
    _require(isinstance(engine_request.get("messages"), list), "engine request messages missing")
    _require(
        isinstance(engine_request.get("stream"), bool),
        "engine request stream flag missing",
    )
    return {
        "input": {
            "openai_route": OPENAI_CHAT_ROUTE,
            "openai_input": deepcopy(engine_request),
        }
    }


def _parse_sse_event(raw_event, event_number):
    _require(
        len(raw_event.encode("utf-8")) <= MAX_SSE_EVENT_BYTES,
        "RunPod vLLM SSE event too large",
    )
    data_lines = []
    for line in raw_event.split("\n"):
        if line.startswith(":"):
            continue
        _require(line.startswith("data:"), "unsupported RunPod vLLM SSE field")
        data_lines.append(line[5:].removeprefix(" "))
    _require(len(data_lines) == 1 and data_lines[0], "invalid RunPod vLLM SSE data event")
    payload = data_lines[0]
    if payload == "[DONE]":
        return None
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as error:
        raise RunPodVllmError(
            f"invalid RunPod vLLM SSE JSON at event {event_number}"
        ) from error
    _require(isinstance(value, dict), "RunPod vLLM SSE payload must be an object")
    return _reject_worker_error(value)


def parse_raw_sse(fragments):
    """Yield OpenAI chunk objects from fragmented raw SSE worker output.

    A terminal ``data: [DONE]`` event is mandatory and must be the final event.
    The parser deliberately does not accept a full RunPod HTTP response envelope;
    live envelope compatibility remains a separate provider verification gate.
    """
    _require(not isinstance(fragments, (str, bytes, dict)), "SSE output must be an iterable")
    try:
        iterator = iter(fragments)
    except TypeError as error:
        raise RunPodVllmError("SSE output must be an iterable") from error

    buffer = ""
    total_bytes = 0
    event_count = 0
    json_event_count = 0
    done_seen = False

    for fragment in iterator:
        _require(isinstance(fragment, (str, bytes)), "SSE fragment must be text or bytes")
        if isinstance(fragment, bytes):
            try:
                text = fragment.decode("utf-8")
            except UnicodeDecodeError as error:
                raise RunPodVllmError("RunPod vLLM SSE is not valid UTF-8") from error
        else:
            text = fragment
        total_bytes += len(text.encode("utf-8"))
        _require(total_bytes <= MAX_SSE_BYTES, "RunPod vLLM SSE response too large")
        buffer = (buffer + text).replace("\r\n", "\n")
        _require(
            len(buffer.encode("utf-8")) <= MAX_SSE_EVENT_BYTES,
            "RunPod vLLM SSE buffer too large",
        )

        while "\n\n" in buffer:
            raw_event, buffer = buffer.split("\n\n", 1)
            if not raw_event:
                continue
            _require(not done_seen, "RunPod vLLM SSE event followed terminal marker")
            event_count += 1
            _require(event_count <= MAX_SSE_EVENTS, "too many RunPod vLLM SSE events")
            value = _parse_sse_event(raw_event, event_count)
            if value is None:
                _require(json_event_count > 0, "RunPod vLLM SSE ended before any data")
                done_seen = True
            else:
                json_event_count += 1
                yield value

    _require("\r" not in buffer, "unsupported RunPod vLLM SSE line ending")
    _require(not buffer.strip(), "incomplete RunPod vLLM SSE event")
    _require(done_seen, "RunPod vLLM SSE terminal marker missing")


def decode_worker_output(output, *, expect_stream):
    """Decode the pinned worker's yielded values after provider transport handling."""
    _require(isinstance(expect_stream, bool), "expect_stream must be boolean")
    if expect_stream:
        return parse_raw_sse(output)

    if isinstance(output, dict):
        return deepcopy(_reject_worker_error(output))
    _require(not isinstance(output, (str, bytes)), "non-stream worker output must be an object")
    try:
        values = list(output)
    except TypeError as error:
        raise RunPodVllmError("non-stream worker output must be an object") from error
    _require(len(values) == 1 and isinstance(values[0], dict), "non-stream worker must yield one object")
    return deepcopy(_reject_worker_error(values[0]))


def make_queue_inference_client(worker_call):
    """Adapt a trusted worker-call function to ``worker.handler.handle_job``."""
    _require(callable(worker_call), "worker call must be callable")

    def inference_client(engine_request):
        output = worker_call(build_queue_job(engine_request))
        return decode_worker_output(output, expect_stream=engine_request["stream"])

    return inference_client
