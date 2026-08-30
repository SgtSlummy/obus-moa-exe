---
name: gortex-5-dirs-set-linear
description: "Work in the . +5 dirs · set_linear area — 775 symbols across 20 files (93% cohesion)"
---

# . +5 dirs · set_linear

775 symbols | 20 files | 93% cohesion

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
| `` | _clear_internal_caches, collect, gettotalrefcount, _clear_type_cache |
| `.venv-build\Lib\site-packages\ctranslate2\converters\fairseq.py` | args, _get_model_spec |
| `.venv-build\Lib\site-packages\ctranslate2\converters\marian.py` | model, _load, _get_model_config |
| `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_py.py` | opt, num_source_embeddings, check_opt |
| `.venv-build\Lib\site-packages\ctranslate2\converters\opennmt_tf.py` | set_layer_norm, set_transformer_encoder, set_multi_head_attention, inputter, unk_token, ... |
| `.venv-build\Lib\site-packages\ctranslate2\converters\transformers.py` | model, set_wav2vec2bert_adapter, set_vocabulary, module, set_vocabulary, ... |
| `.venv-build\Lib\site-packages\ctranslate2\converters\utils.py` | assert_condition, reasons, __init__, __call__, error_message, ... |
| `.venv-build\Lib\site-packages\ctranslate2\specs\common_spec.py` | __init__, LinearSpec, has_bias, EmbeddingsMerge |
| `.venv-build\Lib\site-packages\ctranslate2\specs\transformer_spec.py` | embeddings_merge, alignment_layer, get_vocabulary_size, TransformerEncoderSpec, num_heads, ... |
| `.venv-build\Lib\site-packages\ctranslate2\specs\whisper_spec.py` | __init__, num_decoder_layers, num_decoder_heads, num_encoder_layers, num_encoder_heads |
| `.venv-build\Lib\site-packages\google\protobuf\internal\testing_refleaks.py` | ReferenceLeakCheckerMixin, _getRefcounts, result, run |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_dtype.py` | pat, items_changed, test_structured_object_take_and_repeat, count, pat, ... |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_mem_policy.py` | get_module, test_owner_is_base |
| `.venv-build\Lib\site-packages\numpy\testing\_private\utils.py` | break_cycles |
| `external-call::dep:ctranslate2.converters.utils` | ctranslate2.converters.utils |
| `external-call::dep:ctranslate2.specs.transformer_spec` | ctranslate2.specs.transformer_spec |
| `external-call::dep:ctranslate2.specs.wav2vec2_spec` | ctranslate2.specs.wav2vec2_spec |
| `external-call::dep:ctranslate2.specs.wav2vec2bert_spec` | ctranslate2.specs.wav2vec2bert_spec |
| `external-call::stdlib:copyreg` | copyreg |
| `external-call::stdlib:opennmt` | opennmt |

## Connected Communities

- **. +54 dirs** (27 cross-edges)
- **ctranslate2/specs +1 dirs** (21 cross-edges)
- **. +32 dirs** (11 cross-edges)
- **. +5 dirs · invoke** (1 cross-edges)
- **site-packages/PIL +19 dirs** (1 cross-edges)
- **. +65 dirs** (1 cross-edges)
- **ctranslate2/converters · set_transformer_encoder** (1 cross-edges)
- **ctranslate2/converters · set_stack** (1 cross-edges)
- **protobuf/internal +5 dirs** (1 cross-edges)
- **protobuf/internal · addError** (1 cross-edges)
- **ctranslate2/specs · __init__ · model_spec · transformer_spec (10)** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-576")
explore(operation:"context", task:"understand . +5 dirs · set_linear", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
