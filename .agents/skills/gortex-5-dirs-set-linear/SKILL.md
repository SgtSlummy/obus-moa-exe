---
name: gortex-5-dirs-set-linear
description: "Work in the . +5 dirs · set_linear area — 773 symbols across 20 files (93% cohesion)"
---

# . +5 dirs · set_linear

773 symbols | 20 files | 93% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `.venv-build\Lib\site-packages\ctranslate2\converters\fairseq.py`
- `.venv-build\Lib\site-packages\ctranslate2\converters\marian.py`
- `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_py.py`
- `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_tf.py`
- `.venv-build\Lib\site-packages\ctranslate2\converters\transformers.py`
- `.venv-build\Lib\site-packages\ctranslate2\converters\utils.py`
- `.venv-build\Lib\site-packages\ctranslate2\specs\common_spec.py`
- `.venv-build\Lib\site-packages\ctranslate2\specs\transformer_spec.py`
- `.venv-build\Lib\site-packages\ctranslate2\specs\whisper_spec.py`
- `.venv-build\Lib\site-packages\google\protobuf\internal\testing_refleaks.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_dtype.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_mem_policy.py`
- `.venv-build\Lib\site-packages\numpy\testing\_private\utils.py`
- `external-call::dep:ctranslate2.converters.utils`
- `external-call::dep:ctranslate2.specs.transformer_spec`
- `external-call::dep:ctranslate2.specs.wav2vec2_spec`
- `external-call::dep:ctranslate2.specs.wav2vec2bert_spec`
- `external-call::stdlib:copyreg`
- `external-call::stdlib:opennmt`

## Key Files

| File | Symbols |
|------|---------|
| `` | collect, _clear_internal_caches, _clear_type_cache, gettotalrefcount |
| `.venv-build\Lib\site-packages\ctranslate2\converters\fairseq.py` | args, _get_model_spec |
| `.venv-build\Lib\site-packages\ctranslate2\converters\marian.py` | _load |
| `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_py.py` | num_source_embeddings, opt, check_opt |
| `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_tf.py` | set_ffn, TransformerSpecBuilder, set_multi_head_attention, module, module, ... |
| `.venv-build\Lib\site-packages\ctranslate2\converters\transformers.py` | get_model_spec, model, spec, spec, Gemma3Loader, ... |
| `.venv-build\Lib\site-packages\ctranslate2\converters\utils.py` | __call__, assert_condition, reasons, error_message, ConfigurationChecker, ... |
| `.venv-build\Lib\site-packages\ctranslate2\specs\common_spec.py` | LinearSpec, EmbeddingsMerge, __init__, has_bias |
| `.venv-build\Lib\site-packages\ctranslate2\specs\transformer_spec.py` | alignment_layer, layernorm_embedding, with_relative_position, revision, ffn_glu, ... |
| `.venv-build\Lib\site-packages\ctranslate2\specs\whisper_spec.py` | __init__, num_decoder_layers, num_encoder_heads, num_decoder_heads, num_encoder_layers |
| `.venv-build\Lib\site-packages\google\protobuf\internal\testing_refleaks.py` | run, result, _getRefcounts, ReferenceLeakCheckerMixin |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_dtype.py` | test_structured_object_take_and_repeat, count, creation_obj, singleton, pat, ... |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_mem_policy.py` | test_owner_is_base, get_module |
| `.venv-build\Lib\site-packages\numpy\testing\_private\utils.py` | break_cycles |
| `external-call::dep:ctranslate2.converters.utils` | ctranslate2.converters.utils |
| `external-call::dep:ctranslate2.specs.transformer_spec` | ctranslate2.specs.transformer_spec |
| `external-call::dep:ctranslate2.specs.wav2vec2_spec` | ctranslate2.specs.wav2vec2_spec |
| `external-call::dep:ctranslate2.specs.wav2vec2bert_spec` | ctranslate2.specs.wav2vec2bert_spec |
| `external-call::stdlib:copyreg` | copyreg |
| `external-call::stdlib:opennmt` | opennmt |

## Connected Communities

- **. +53 dirs** (27 cross-edges)
- **ctranslate2/specs +1 dirs** (21 cross-edges)
- **. +31 dirs · torch** (11 cross-edges)
- **protobuf/internal +5 dirs** (1 cross-edges)
- **protobuf/internal · addError** (1 cross-edges)
- **. +5 dirs · invoke** (1 cross-edges)
- **site-packages/PIL +22 dirs** (1 cross-edges)
- **ctranslate2/specs · __init__ · model_spec · transformer_spec (10)** (1 cross-edges)
- **Lib/site-packages · _get_model_config** (1 cross-edges)
- **ctranslate2/converters · set_transformer_encoder** (1 cross-edges)
- **ctranslate2/converters · set_stack** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-594")
explore(operation:"context", task:"understand . +5 dirs · set_linear", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
