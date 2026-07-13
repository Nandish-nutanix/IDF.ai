"""
constrained_decode.py - Grammar-constrained JSON generation on MLX via Outlines.

This is the strongest structural guarantee in the pipeline: when enabled, Phi-4
can ONLY emit tokens that keep the output a valid instance of the QueryIR JSON
schema, so malformed structure is impossible at decode time.

It is deliberately BEST-EFFORT and non-fatal:
  - If Outlines is not installed, or the installed version's API differs, or the
    constrained generator fails for any reason, `generate_ir_json` returns None.
  - The caller (mlx_server_local) then falls back to normal generation, and the
    downstream validate -> repair -> deterministic-render loop still guarantees a
    valid proto. Constrained decoding only raises the ceiling on accuracy.

It reuses the model + tokenizer already loaded by the server (no second copy in
memory), which matters on 18GB Apple Silicon.
"""

from __future__ import annotations

from typing import Optional

# Cached Outlines model wrapper + generators keyed by pydantic class name.
_outlines_model = None
_generators: dict = {}
_disabled = False


def _build_outlines_model(mlx_model, mlx_tokenizer):
    """Wrap an already-loaded mlx model/tokenizer in an Outlines model."""
    import outlines  # noqa: F401

    # Outlines v1 unified API.
    if hasattr(outlines, "from_mlxlm"):
        return outlines.from_mlxlm(mlx_model, mlx_tokenizer)
    # Older namespaced API.
    from outlines import models as _models
    if hasattr(_models, "from_mlxlm"):
        return _models.from_mlxlm(mlx_model, mlx_tokenizer)
    raise RuntimeError("Outlines present but no from_mlxlm entry point")


def _get_generator(mlx_model, mlx_tokenizer, output_cls):
    global _outlines_model, _disabled
    if _disabled:
        return None
    key = output_cls.__name__
    if key in _generators:
        return _generators[key]
    try:
        if _outlines_model is None:
            _outlines_model = _build_outlines_model(mlx_model, mlx_tokenizer)
        import outlines
        gen = None
        # v1: outlines.Generator(model, OutputType)
        if hasattr(outlines, "Generator"):
            gen = outlines.Generator(_outlines_model, output_cls)
        # legacy: outlines.generate.json(model, schema)
        elif hasattr(outlines, "generate") and hasattr(outlines.generate, "json"):
            gen = outlines.generate.json(_outlines_model, output_cls)
        if gen is None:
            raise RuntimeError("No usable Outlines generator constructor")
        _generators[key] = gen
        return gen
    except Exception as e:  # noqa: BLE001
        print(f"[ConstrainedDecode] disabled (init failed): {e}", flush=True)
        _disabled = True
        return None


def is_available() -> bool:
    """Cheap check: can we import outlines at all?"""
    if _disabled:
        return False
    try:
        import outlines  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def generate_ir_json(mlx_model, mlx_tokenizer, prompt: str,
                     output_cls, max_tokens: int = 320) -> Optional[str]:
    """
    Constrained-generate a JSON instance of `output_cls` (a Pydantic model).

    Returns a JSON string on success, or None if constrained decoding is
    unavailable / failed (caller must fall back to normal generation).
    """
    gen = _get_generator(mlx_model, mlx_tokenizer, output_cls)
    if gen is None:
        return None
    try:
        result = gen(prompt, max_tokens=max_tokens)
    except TypeError:
        # Some versions don't accept max_tokens kwarg.
        try:
            result = gen(prompt)
        except Exception as e:  # noqa: BLE001
            print(f"[ConstrainedDecode] generation failed: {e}", flush=True)
            return None
    except Exception as e:  # noqa: BLE001
        print(f"[ConstrainedDecode] generation failed: {e}", flush=True)
        return None

    # Result may be a pydantic instance, dict, or JSON string depending on version.
    try:
        if hasattr(result, "model_dump_json"):
            return result.model_dump_json()
        if isinstance(result, dict):
            import json
            return json.dumps(result)
        if isinstance(result, str):
            return result
        # Fallback: best-effort str().
        return str(result)
    except Exception:  # noqa: BLE001
        return None
