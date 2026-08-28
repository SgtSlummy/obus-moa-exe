---
name: gortex-6-dirs-numpy-core-umath
description: "Work in the . +6 dirs · numpy._core.umath area — 1113 symbols across 19 files (88% cohesion)"
---

# . +6 dirs · numpy._core.umath

1113 symbols | 19 files | 88% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `.venv-build\Lib\site-packages\numpy\_core\_methods.py`
- `.venv-build\Lib\site-packages\numpy\_core\fromnumeric.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_regression.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_umath.py`
- `.venv-build\Lib\site-packages\numpy\core\_internal.py`
- `.venv-build\Lib\site-packages\numpy\ma\core.py`
- `.venv-build\Lib\site-packages\numpy\ma\extras.py`
- `.venv-build\Lib\site-packages\numpy\ma\mrecords.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_subclassing.py`
- `.venv-build\Lib\site-packages\numpy\ma\testutils.py`
- `.venv-build\Lib\site-packages\numpy\testing\overrides.py`
- `external-call::dep:numpy._core.multiarray`
- `external-call::dep:numpy._core.multiarray.asanyarray`
- `external-call::dep:numpy._core.numerictypes`
- `external-call::dep:numpy._core.umath`
- `external-call::dep:numpy.expand_dims`
- `external-call::dep:numpy.lib._function_base_impl._ureduce`
- `external-call::dep:numpy.ndarray`

## Key Files

| File | Symbols |
|------|---------|
| `` | all, replace, builtins, Parameter |
| `.venv-build\Lib\site-packages\numpy\_core\_methods.py` | min, _mean, max, out, ddof, ... |
| `.venv-build\Lib\site-packages\numpy\_core\fromnumeric.py` | where, correction, out, _var_dispatcher, a, ... |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_regression.py` | X |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_umath.py` | x, x, y, assert_hypot_isnan, test_inf_any, ... |
| `.venv-build\Lib\site-packages\numpy\core\_internal.py` | shape, _reconstruct, dtype, subtype |
| `.venv-build\Lib\site-packages\numpy\ma\core.py` | tolist, axis, indices, x, a, ... |
| `.venv-build\Lib\site-packages\numpy\ma\extras.py` | overwrite_input, flatnotmasked_contiguous, _fromnxfunction_single, npfunc, clump_masked, ... |
| `.venv-build\Lib\site-packages\numpy\ma\mrecords.py` | fill_value, fill_value, aligned, mask, descr, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_subclassing.py` | SubMaskedArray, kwargs, info, __new__ |
| `.venv-build\Lib\site-packages\numpy\ma\testutils.py` | actual, err_msg, err_msg, x, decimal, ... |
| `.venv-build\Lib\site-packages\numpy\testing\overrides.py` | get_overridable_numpy_ufuncs |
| `external-call::dep:numpy._core.multiarray` | numpy._core.multiarray |
| `external-call::dep:numpy._core.multiarray.asanyarray` | numpy._core.multiarray.asanyarray |
| `external-call::dep:numpy._core.numerictypes` | numpy._core.numerictypes |
| `external-call::dep:numpy._core.umath` | numpy._core.umath |
| `external-call::dep:numpy.expand_dims` | numpy.expand_dims |
| `external-call::dep:numpy.lib._function_base_impl._ureduce` | numpy.lib._function_base_impl._ureduce |
| `external-call::dep:numpy.ndarray` | numpy.ndarray |

## Connected Communities

- **. +53 dirs** (303 cross-edges)
- **. +43 dirs** (8 cross-edges)
- **. +9 dirs** (5 cross-edges)
- **. +3 dirs · norm** (3 cross-edges)
- **. +6 dirs · deepcopy** (2 cross-edges)
- **. +17 dirs** (1 cross-edges)
- **. +1 dirs · get_typed_annotation** (1 cross-edges)
- **numpy/_core +2 dirs · tensordot** (1 cross-edges)
- **numpy/_core +1 dirs · binary_repr** (1 cross-edges)
- **numpy/ma · _delegate_binop** (1 cross-edges)
- **. +1 dirs · render · .** (1 cross-edges)
- **. +4 dirs · cleandoc** (1 cross-edges)
- **site-packages/numpy · unique** (1 cross-edges)
- **protobuf/internal +4 dirs** (1 cross-edges)
- **. +4 dirs · reduce** (1 cross-edges)
- **. +31 dirs · pydantic_core.core_schema** (1 cross-edges)
- **_core/tests +8 dirs · signature** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-1796")
explore(operation:"context", task:"understand . +6 dirs · numpy._core.umath", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
