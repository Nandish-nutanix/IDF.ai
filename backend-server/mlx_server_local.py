"""
Local MLX model server that mimics the OpenAI /v1/chat/completions API.
Works fully offline without needing HuggingFace Hub access.

Extensions over a plain wrapper:
  - honors `temperature` and `stop` from the request
  - supports `guided_json` (a JSON schema name) for grammar-constrained IR
    generation via Outlines (constrained_decode). When the client asks for the
    QueryIR schema, Phi-4 is constrained to emit a valid IR JSON object.
"""
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from mlx_lm import load, generate

try:
    from mlx_lm.sample_utils import make_sampler
except Exception:  # noqa: BLE001
    make_sampler = None

import constrained_decode
from query_ir import QueryIR

MODEL_PATH = "./phi4_idf_fused"
PORT = 8090

# Schemas the server is willing to constrain generation to.
GUIDED_SCHEMAS = {"QueryIR": QueryIR}

print(f"Loading model from {MODEL_PATH}...")
model, tokenizer = load(MODEL_PATH)
print(f"Model loaded. Starting server on port {PORT}...")


def _apply_stops(text: str, stops):
    """Trim the response at the earliest stop sequence."""
    if not stops:
        return text
    cut = len(text)
    for s in stops:
        if not s:
            continue
        idx = text.find(s)
        if idx != -1:
            cut = min(cut, idx)
    return text[:cut]


def _generate_text(prompt: str, max_tokens: int, temperature: float):
    """Generate text honoring temperature when the installed mlx_lm supports it."""
    if make_sampler is not None:
        try:
            sampler = make_sampler(temp=float(temperature or 0.0))
            return generate(model, tokenizer, prompt=prompt,
                            max_tokens=max_tokens, sampler=sampler)
        except TypeError:
            pass
        except Exception:  # noqa: BLE001
            pass
    # Fallback (greedy / default sampling).
    return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens)

CHAT_TEMPLATE = "{% for message in messages %}{% if (message['role'] == 'system') %}{{'<|im_start|>system<|im_sep|>' + message['content'] + '<|im_end|>'}}{% elif (message['role'] == 'user') %}{{'<|im_start|>user<|im_sep|>' + message['content'] + '<|im_end|><|im_start|>assistant<|im_sep|>'}}{% elif (message['role'] == 'assistant') %}{{message['content'] + '<|im_end|>'}}{% endif %}{% endfor %}"

from jinja2 import Template
template = Template(CHAT_TEMPLATE)


def apply_chat_template(messages):
    return template.render(messages=messages)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/v1/models":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "data": [{"id": "phi4_idf_fused", "object": "model"}]
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length))

            messages = body.get("messages", [])
            max_tokens = body.get("max_tokens", 512)
            temperature = body.get("temperature", 0)
            stops = body.get("stop") or []
            if isinstance(stops, str):
                stops = [stops]
            guided = body.get("guided_json")

            prompt = apply_chat_template(messages)

            t0 = time.time()
            response_text = None
            mode = "plain"

            # Constrained IR generation when requested and available.
            if guided and guided in GUIDED_SCHEMAS:
                ir_json = constrained_decode.generate_ir_json(
                    model, tokenizer, prompt, GUIDED_SCHEMAS[guided],
                    max_tokens=max_tokens,
                )
                if ir_json is not None:
                    response_text = ir_json
                    mode = "constrained"

            if response_text is None:
                response_text = _generate_text(prompt, max_tokens, temperature)
                response_text = _apply_stops(response_text, stops)

            elapsed = time.time() - t0

            result = {
                "id": f"chatcmpl-{int(time.time()*1000)}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "phi4_idf_fused",
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": len(prompt.split()),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": len(prompt.split()) + len(response_text.split())
                }
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
            print(f"  [MLX:{mode}] {max_tokens}tok, {elapsed:.1f}s, {len(response_text)} chars", flush=True)
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_body = json.dumps({"error": {"message": str(e), "type": "server_error"}})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(error_body.encode())


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"MLX Phi-4 server ready at http://127.0.0.1:{PORT}")
    server.serve_forever()
