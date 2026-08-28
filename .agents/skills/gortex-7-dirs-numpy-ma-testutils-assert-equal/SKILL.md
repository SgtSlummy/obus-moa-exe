---
name: gortex-7-dirs-numpy-ma-testutils-assert-equal
description: "Work in the . +7 dirs · numpy.ma.testutils.assert_equal area — 899 symbols across 183 files (86% cohesion)"
---

# . +7 dirs · numpy.ma.testutils.assert_equal

899 symbols | 183 files | 86% cohesion

## When to Use

Use this skill when working on files in:
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_einsum.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_regression.py`
- `.venv-build\Lib\site-packages\numpy\_core\tests\test_ufunc.py`
- `.venv-build\Lib\site-packages\numpy\lib\tests\test_function_base.py`
- `.venv-build\Lib\site-packages\numpy\lib\tests\test_io.py`
- `.venv-build\Lib\site-packages\numpy\lib\tests\test_loadtxt.py`
- `.venv-build\Lib\site-packages\numpy\lib\tests\test_recfunctions.py`
- `.venv-build\Lib\site-packages\numpy\ma\mrecords.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_core.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_deprecations.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_mrecords.py`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_subclassing.py`
- `.venv-build\Lib\site-packages\numpy\matlib.py`
- `.venv-build\Lib\site-packages\numpy\matrixlib\tests\test_masked_matrix.py`
- `.venv-build\Lib\site-packages\six.py`
- `external-call::dep:numpy._core.records.fromrecords`
- `external-call::dep:numpy.lib._npyio_impl.recfromcsv`
- `external-call::dep:numpy.lib._npyio_impl.recfromtxt`
- `external-call::dep:numpy.lib.recfunctions.apply_along_fields`
- `external-call::dep:numpy.lib.recfunctions.assign_fields_by_name`
- `external-call::dep:numpy.lib.recfunctions.drop_fields`
- `external-call::dep:numpy.lib.recfunctions.find_duplicates`
- `external-call::dep:numpy.lib.recfunctions.get_fieldstructure`
- `external-call::dep:numpy.lib.recfunctions.join_by`
- `external-call::dep:numpy.lib.recfunctions.recursive_fill_fields`
- `external-call::dep:numpy.lib.recfunctions.rename_fields`
- `external-call::dep:numpy.lib.recfunctions.repack_fields`
- `external-call::dep:numpy.lib.recfunctions.require_fields`
- `external-call::dep:numpy.lib.recfunctions.stack_arrays`
- `external-call::dep:numpy.lib.recfunctions.structured_to_unstructured`
- `external-call::dep:numpy.lib.recfunctions.unstructured_to_structured`
- `external-call::dep:numpy.ma`
- `external-call::dep:numpy.ma.core`
- `external-call::dep:numpy.ma.core.MaskedArray`
- `external-call::dep:numpy.ma.core.abs`
- `external-call::dep:numpy.ma.core.absolute`
- `external-call::dep:numpy.ma.core.add`
- `external-call::dep:numpy.ma.core.all`
- `external-call::dep:numpy.ma.core.allclose`
- `external-call::dep:numpy.ma.core.allequal`
- `external-call::dep:numpy.ma.core.alltrue`
- `external-call::dep:numpy.ma.core.angle`
- `external-call::dep:numpy.ma.core.anom`
- `external-call::dep:numpy.ma.core.arange`
- `external-call::dep:numpy.ma.core.arccos`
- `external-call::dep:numpy.ma.core.arccosh`
- `external-call::dep:numpy.ma.core.arcsin`
- `external-call::dep:numpy.ma.core.arctan`
- `external-call::dep:numpy.ma.core.arctan2`
- `external-call::dep:numpy.ma.core.argsort`
- `external-call::dep:numpy.ma.core.array`
- `external-call::dep:numpy.ma.core.asanyarray`
- `external-call::dep:numpy.ma.core.asarray`
- `external-call::dep:numpy.ma.core.choose`
- `external-call::dep:numpy.ma.core.concatenate`
- `external-call::dep:numpy.ma.core.conjugate`
- `external-call::dep:numpy.ma.core.cos`
- `external-call::dep:numpy.ma.core.cosh`
- `external-call::dep:numpy.ma.core.count`
- `external-call::dep:numpy.ma.core.default_fill_value`
- `external-call::dep:numpy.ma.core.diag`
- `external-call::dep:numpy.ma.core.divide`
- `external-call::dep:numpy.ma.core.empty`
- `external-call::dep:numpy.ma.core.empty_like`
- `external-call::dep:numpy.ma.core.equal`
- `external-call::dep:numpy.ma.core.exp`
- `external-call::dep:numpy.ma.core.filled`
- `external-call::dep:numpy.ma.core.fix_invalid`
- `external-call::dep:numpy.ma.core.flatten_mask`
- `external-call::dep:numpy.ma.core.flatten_structured_array`
- `external-call::dep:numpy.ma.core.fromflex`
- `external-call::dep:numpy.ma.core.getmask`
- `external-call::dep:numpy.ma.core.getmaskarray`
- `external-call::dep:numpy.ma.core.greater`
- `external-call::dep:numpy.ma.core.greater_equal`
- `external-call::dep:numpy.ma.core.hypot`
- `external-call::dep:numpy.ma.core.identity`
- `external-call::dep:numpy.ma.core.inner`
- `external-call::dep:numpy.ma.core.isMaskedArray`
- `external-call::dep:numpy.ma.core.less`
- `external-call::dep:numpy.ma.core.less_equal`
- `external-call::dep:numpy.ma.core.log`
- `external-call::dep:numpy.ma.core.log10`
- `external-call::dep:numpy.ma.core.make_mask`
- `external-call::dep:numpy.ma.core.make_mask_descr`
- `external-call::dep:numpy.ma.core.mask_or`
- `external-call::dep:numpy.ma.core.masked_array`
- `external-call::dep:numpy.ma.core.masked_equal`
- `external-call::dep:numpy.ma.core.masked_greater`
- `external-call::dep:numpy.ma.core.masked_greater_equal`
- `external-call::dep:numpy.ma.core.masked_inside`
- `external-call::dep:numpy.ma.core.masked_less`
- `external-call::dep:numpy.ma.core.masked_less_equal`
- `external-call::dep:numpy.ma.core.masked_not_equal`
- `external-call::dep:numpy.ma.core.masked_outside`
- `external-call::dep:numpy.ma.core.masked_print_option`
- `external-call::dep:numpy.ma.core.masked_values`
- `external-call::dep:numpy.ma.core.masked_where`
- `external-call::dep:numpy.ma.core.max`
- `external-call::dep:numpy.ma.core.maximum`
- `external-call::dep:numpy.ma.core.maximum_fill_value`
- `external-call::dep:numpy.ma.core.min`
- `external-call::dep:numpy.ma.core.minimum`
- `external-call::dep:numpy.ma.core.minimum_fill_value`
- `external-call::dep:numpy.ma.core.mod`
- `external-call::dep:numpy.ma.core.multiply`
- `external-call::dep:numpy.ma.core.mvoid`
- `external-call::dep:numpy.ma.core.not_equal`
- `external-call::dep:numpy.ma.core.ones`
- `external-call::dep:numpy.ma.core.ones_like`
- `external-call::dep:numpy.ma.core.outer`
- `external-call::dep:numpy.ma.core.power`
- `external-call::dep:numpy.ma.core.product`
- `external-call::dep:numpy.ma.core.put`
- `external-call::dep:numpy.ma.core.putmask`
- `external-call::dep:numpy.ma.core.ravel`
- `external-call::dep:numpy.ma.core.repeat`
- `external-call::dep:numpy.ma.core.reshape`
- `external-call::dep:numpy.ma.core.resize`
- `external-call::dep:numpy.ma.core.shape`
- `external-call::dep:numpy.ma.core.sin`
- `external-call::dep:numpy.ma.core.sinh`
- `external-call::dep:numpy.ma.core.sometrue`
- `external-call::dep:numpy.ma.core.sort`
- `external-call::dep:numpy.ma.core.sqrt`
- `external-call::dep:numpy.ma.core.subtract`
- `external-call::dep:numpy.ma.core.sum`
- `external-call::dep:numpy.ma.core.take`
- `external-call::dep:numpy.ma.core.tan`
- `external-call::dep:numpy.ma.core.tanh`
- `external-call::dep:numpy.ma.core.transpose`
- `external-call::dep:numpy.ma.core.where`
- `external-call::dep:numpy.ma.core.zeros`
- `external-call::dep:numpy.ma.core.zeros_like`
- `external-call::dep:numpy.ma.extras._covhelper`
- `external-call::dep:numpy.ma.extras.apply_along_axis`
- `external-call::dep:numpy.ma.extras.apply_over_axes`
- `external-call::dep:numpy.ma.extras.atleast_1d`
- `external-call::dep:numpy.ma.extras.atleast_2d`
- `external-call::dep:numpy.ma.extras.atleast_3d`
- `external-call::dep:numpy.ma.extras.average`
- `external-call::dep:numpy.ma.extras.clump_masked`
- `external-call::dep:numpy.ma.extras.clump_unmasked`
- `external-call::dep:numpy.ma.extras.compress_nd`
- `external-call::dep:numpy.ma.extras.compress_rowcols`
- `external-call::dep:numpy.ma.extras.corrcoef`
- `external-call::dep:numpy.ma.extras.cov`
- `external-call::dep:numpy.ma.extras.diagflat`
- `external-call::dep:numpy.ma.extras.dot`
- `external-call::dep:numpy.ma.extras.ediff1d`
- `external-call::dep:numpy.ma.extras.flatnotmasked_contiguous`
- `external-call::dep:numpy.ma.extras.in1d`
- `external-call::dep:numpy.ma.extras.intersect1d`
- `external-call::dep:numpy.ma.extras.isin`
- `external-call::dep:numpy.ma.extras.mask_rowcols`
- `external-call::dep:numpy.ma.extras.masked_all`
- `external-call::dep:numpy.ma.extras.masked_all_like`
- `external-call::dep:numpy.ma.extras.median`
- `external-call::dep:numpy.ma.extras.ndenumerate`
- `external-call::dep:numpy.ma.extras.notmasked_contiguous`
- `external-call::dep:numpy.ma.extras.notmasked_edges`
- `external-call::dep:numpy.ma.extras.polyfit`
- `external-call::dep:numpy.ma.extras.setdiff1d`
- `external-call::dep:numpy.ma.extras.setxor1d`
- `external-call::dep:numpy.ma.extras.stack`
- `external-call::dep:numpy.ma.extras.union1d`
- `external-call::dep:numpy.ma.extras.unique`
- `external-call::dep:numpy.ma.extras.vstack`
- `external-call::dep:numpy.ma.mrecords.addfield`
- `external-call::dep:numpy.ma.mrecords.fromarrays`
- `external-call::dep:numpy.ma.mrecords.fromrecords`
- `external-call::dep:numpy.ma.mrecords.fromtextfile`
- `external-call::dep:numpy.ma.mrecords.mrecarray`
- `external-call::dep:numpy.ma.testutils.assert_`
- `external-call::dep:numpy.ma.testutils.assert_almost_equal`
- `external-call::dep:numpy.ma.testutils.assert_array_equal`
- `external-call::dep:numpy.ma.testutils.assert_equal`
- `external-call::dep:numpy.ma.testutils.assert_equal_records`
- `external-call::dep:numpy.ma.testutils.assert_mask_equal`
- `external-call::dep:numpy.ma.testutils.assert_not_equal`
- `external-call::dep:numpy.ma.testutils.assert_raises`
- `external-call::dep:numpy.ma.testutils.fail_if_equal`

## Key Files

| File | Symbols |
|------|---------|
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_einsum.py` | test_collapse, test_index_transformations, operands, subscripts, optimize_compare, ... |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_regression.py` | test_method_args, test_arr_transpose |
| `.venv-build\Lib\site-packages\numpy\_core\tests\test_ufunc.py` | s1, broadcastable, s2, n, n, ... |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_function_base.py` | test_subok |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_io.py` | test_invalid_raise, test_withmissing_float, kwargs, args, test_dtype_with_converters_and_usecols, ... |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_loadtxt.py` | dtype, generic_data, test_string_no_length_given, unitless_dtype, long_datum, ... |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_recfunctions.py` | TestJoinBy, subarray, TestStackArrays, test_get_names, test_inner_join, ... |
| `.venv-build\Lib\site-packages\numpy\ma\mrecords.py` | val, obj, commentchar, __getattribute__, __str__, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_core.py` | test_datafriendly_add_arrays, test_topython, test_flatten_mask, test_stable_sort, test_binops_d2D, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_deprecations.py` | _test_base, argsort, test_function_ndarray, test_axis_default, test_function_maskedarray, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py` | test_1d_with_missing, test_masked_constant, test_3d, test_1d_without_missing, test_onintegers_with_mask, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_mrecords.py` | test_set_fields_mask, test_record_array_with_object_field, test_withnames, test_set_mask_fromarray, TestView, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_subclassing.py` | test_subclass_repr, other, __new__, assert_startswith, test_data_subclassing, ... |
| `.venv-build\Lib\site-packages\numpy\matlib.py` | args, rand |
| `.venv-build\Lib\site-packages\numpy\matrixlib\tests\test_masked_matrix.py` | test_ravel, test_view, TestSubclassing, MMatrix, mask, ... |
| `.venv-build\Lib\site-packages\six.py` | __len__, X |
| `external-call::dep:numpy._core.records.fromrecords` | numpy._core.records.fromrecords |
| `external-call::dep:numpy.lib._npyio_impl.recfromcsv` | numpy.lib._npyio_impl.recfromcsv |
| `external-call::dep:numpy.lib._npyio_impl.recfromtxt` | numpy.lib._npyio_impl.recfromtxt |
| `external-call::dep:numpy.lib.recfunctions.apply_along_fields` | numpy.lib.recfunctions.apply_along_fields |
| `external-call::dep:numpy.lib.recfunctions.assign_fields_by_name` | numpy.lib.recfunctions.assign_fields_by_name |
| `external-call::dep:numpy.lib.recfunctions.drop_fields` | numpy.lib.recfunctions.drop_fields |
| `external-call::dep:numpy.lib.recfunctions.find_duplicates` | numpy.lib.recfunctions.find_duplicates |
| `external-call::dep:numpy.lib.recfunctions.get_fieldstructure` | numpy.lib.recfunctions.get_fieldstructure |
| `external-call::dep:numpy.lib.recfunctions.join_by` | numpy.lib.recfunctions.join_by |
| `external-call::dep:numpy.lib.recfunctions.recursive_fill_fields` | numpy.lib.recfunctions.recursive_fill_fields |
| `external-call::dep:numpy.lib.recfunctions.rename_fields` | numpy.lib.recfunctions.rename_fields |
| `external-call::dep:numpy.lib.recfunctions.repack_fields` | numpy.lib.recfunctions.repack_fields |
| `external-call::dep:numpy.lib.recfunctions.require_fields` | numpy.lib.recfunctions.require_fields |
| `external-call::dep:numpy.lib.recfunctions.stack_arrays` | numpy.lib.recfunctions.stack_arrays |
| `external-call::dep:numpy.lib.recfunctions.structured_to_unstructured` | numpy.lib.recfunctions.structured_to_unstructured |
| `external-call::dep:numpy.lib.recfunctions.unstructured_to_structured` | numpy.lib.recfunctions.unstructured_to_structured |
| `external-call::dep:numpy.ma` | numpy.ma |
| `external-call::dep:numpy.ma.core` | numpy.ma.core |
| `external-call::dep:numpy.ma.core.MaskedArray` | numpy.ma.core.MaskedArray |
| `external-call::dep:numpy.ma.core.abs` | numpy.ma.core.abs |
| `external-call::dep:numpy.ma.core.absolute` | numpy.ma.core.absolute |
| `external-call::dep:numpy.ma.core.add` | numpy.ma.core.add |
| `external-call::dep:numpy.ma.core.all` | numpy.ma.core.all |
| `external-call::dep:numpy.ma.core.allclose` | numpy.ma.core.allclose |
| `external-call::dep:numpy.ma.core.allequal` | numpy.ma.core.allequal |
| `external-call::dep:numpy.ma.core.alltrue` | numpy.ma.core.alltrue |
| `external-call::dep:numpy.ma.core.angle` | numpy.ma.core.angle |
| `external-call::dep:numpy.ma.core.anom` | numpy.ma.core.anom |
| `external-call::dep:numpy.ma.core.arange` | numpy.ma.core.arange |
| `external-call::dep:numpy.ma.core.arccos` | numpy.ma.core.arccos |
| `external-call::dep:numpy.ma.core.arccosh` | numpy.ma.core.arccosh |
| `external-call::dep:numpy.ma.core.arcsin` | numpy.ma.core.arcsin |
| `external-call::dep:numpy.ma.core.arctan` | numpy.ma.core.arctan |
| `external-call::dep:numpy.ma.core.arctan2` | numpy.ma.core.arctan2 |
| `external-call::dep:numpy.ma.core.argsort` | numpy.ma.core.argsort |
| `external-call::dep:numpy.ma.core.array` | numpy.ma.core.array |
| `external-call::dep:numpy.ma.core.asanyarray` | numpy.ma.core.asanyarray |
| `external-call::dep:numpy.ma.core.asarray` | numpy.ma.core.asarray |
| `external-call::dep:numpy.ma.core.choose` | numpy.ma.core.choose |
| `external-call::dep:numpy.ma.core.concatenate` | numpy.ma.core.concatenate |
| `external-call::dep:numpy.ma.core.conjugate` | numpy.ma.core.conjugate |
| `external-call::dep:numpy.ma.core.cos` | numpy.ma.core.cos |
| `external-call::dep:numpy.ma.core.cosh` | numpy.ma.core.cosh |
| `external-call::dep:numpy.ma.core.count` | numpy.ma.core.count |
| `external-call::dep:numpy.ma.core.default_fill_value` | numpy.ma.core.default_fill_value |
| `external-call::dep:numpy.ma.core.diag` | numpy.ma.core.diag |
| `external-call::dep:numpy.ma.core.divide` | numpy.ma.core.divide |
| `external-call::dep:numpy.ma.core.empty` | numpy.ma.core.empty |
| `external-call::dep:numpy.ma.core.empty_like` | numpy.ma.core.empty_like |
| `external-call::dep:numpy.ma.core.equal` | numpy.ma.core.equal |
| `external-call::dep:numpy.ma.core.exp` | numpy.ma.core.exp |
| `external-call::dep:numpy.ma.core.filled` | numpy.ma.core.filled |
| `external-call::dep:numpy.ma.core.fix_invalid` | numpy.ma.core.fix_invalid |
| `external-call::dep:numpy.ma.core.flatten_mask` | numpy.ma.core.flatten_mask |
| `external-call::dep:numpy.ma.core.flatten_structured_array` | numpy.ma.core.flatten_structured_array |
| `external-call::dep:numpy.ma.core.fromflex` | numpy.ma.core.fromflex |
| `external-call::dep:numpy.ma.core.getmask` | numpy.ma.core.getmask |
| `external-call::dep:numpy.ma.core.getmaskarray` | numpy.ma.core.getmaskarray |
| `external-call::dep:numpy.ma.core.greater` | numpy.ma.core.greater |
| `external-call::dep:numpy.ma.core.greater_equal` | numpy.ma.core.greater_equal |
| `external-call::dep:numpy.ma.core.hypot` | numpy.ma.core.hypot |
| `external-call::dep:numpy.ma.core.identity` | numpy.ma.core.identity |
| `external-call::dep:numpy.ma.core.inner` | numpy.ma.core.inner |
| `external-call::dep:numpy.ma.core.isMaskedArray` | numpy.ma.core.isMaskedArray |
| `external-call::dep:numpy.ma.core.less` | numpy.ma.core.less |
| `external-call::dep:numpy.ma.core.less_equal` | numpy.ma.core.less_equal |
| `external-call::dep:numpy.ma.core.log` | numpy.ma.core.log |
| `external-call::dep:numpy.ma.core.log10` | numpy.ma.core.log10 |
| `external-call::dep:numpy.ma.core.make_mask` | numpy.ma.core.make_mask |
| `external-call::dep:numpy.ma.core.make_mask_descr` | numpy.ma.core.make_mask_descr |
| `external-call::dep:numpy.ma.core.mask_or` | numpy.ma.core.mask_or |
| `external-call::dep:numpy.ma.core.masked_array` | numpy.ma.core.masked_array |
| `external-call::dep:numpy.ma.core.masked_equal` | numpy.ma.core.masked_equal |
| `external-call::dep:numpy.ma.core.masked_greater` | numpy.ma.core.masked_greater |
| `external-call::dep:numpy.ma.core.masked_greater_equal` | numpy.ma.core.masked_greater_equal |
| `external-call::dep:numpy.ma.core.masked_inside` | numpy.ma.core.masked_inside |
| `external-call::dep:numpy.ma.core.masked_less` | numpy.ma.core.masked_less |
| `external-call::dep:numpy.ma.core.masked_less_equal` | numpy.ma.core.masked_less_equal |
| `external-call::dep:numpy.ma.core.masked_not_equal` | numpy.ma.core.masked_not_equal |
| `external-call::dep:numpy.ma.core.masked_outside` | numpy.ma.core.masked_outside |
| `external-call::dep:numpy.ma.core.masked_print_option` | numpy.ma.core.masked_print_option |
| `external-call::dep:numpy.ma.core.masked_values` | numpy.ma.core.masked_values |
| `external-call::dep:numpy.ma.core.masked_where` | numpy.ma.core.masked_where |
| `external-call::dep:numpy.ma.core.max` | numpy.ma.core.max |
| `external-call::dep:numpy.ma.core.maximum` | numpy.ma.core.maximum |
| `external-call::dep:numpy.ma.core.maximum_fill_value` | numpy.ma.core.maximum_fill_value |
| `external-call::dep:numpy.ma.core.min` | numpy.ma.core.min |
| `external-call::dep:numpy.ma.core.minimum` | numpy.ma.core.minimum |
| `external-call::dep:numpy.ma.core.minimum_fill_value` | numpy.ma.core.minimum_fill_value |
| `external-call::dep:numpy.ma.core.mod` | numpy.ma.core.mod |
| `external-call::dep:numpy.ma.core.multiply` | numpy.ma.core.multiply |
| `external-call::dep:numpy.ma.core.mvoid` | numpy.ma.core.mvoid |
| `external-call::dep:numpy.ma.core.not_equal` | numpy.ma.core.not_equal |
| `external-call::dep:numpy.ma.core.ones` | numpy.ma.core.ones |
| `external-call::dep:numpy.ma.core.ones_like` | numpy.ma.core.ones_like |
| `external-call::dep:numpy.ma.core.outer` | numpy.ma.core.outer |
| `external-call::dep:numpy.ma.core.power` | numpy.ma.core.power |
| `external-call::dep:numpy.ma.core.product` | numpy.ma.core.product |
| `external-call::dep:numpy.ma.core.put` | numpy.ma.core.put |
| `external-call::dep:numpy.ma.core.putmask` | numpy.ma.core.putmask |
| `external-call::dep:numpy.ma.core.ravel` | numpy.ma.core.ravel |
| `external-call::dep:numpy.ma.core.repeat` | numpy.ma.core.repeat |
| `external-call::dep:numpy.ma.core.reshape` | numpy.ma.core.reshape |
| `external-call::dep:numpy.ma.core.resize` | numpy.ma.core.resize |
| `external-call::dep:numpy.ma.core.shape` | numpy.ma.core.shape |
| `external-call::dep:numpy.ma.core.sin` | numpy.ma.core.sin |
| `external-call::dep:numpy.ma.core.sinh` | numpy.ma.core.sinh |
| `external-call::dep:numpy.ma.core.sometrue` | numpy.ma.core.sometrue |
| `external-call::dep:numpy.ma.core.sort` | numpy.ma.core.sort |
| `external-call::dep:numpy.ma.core.sqrt` | numpy.ma.core.sqrt |
| `external-call::dep:numpy.ma.core.subtract` | numpy.ma.core.subtract |
| `external-call::dep:numpy.ma.core.sum` | numpy.ma.core.sum |
| `external-call::dep:numpy.ma.core.take` | numpy.ma.core.take |
| `external-call::dep:numpy.ma.core.tan` | numpy.ma.core.tan |
| `external-call::dep:numpy.ma.core.tanh` | numpy.ma.core.tanh |
| `external-call::dep:numpy.ma.core.transpose` | numpy.ma.core.transpose |
| `external-call::dep:numpy.ma.core.where` | numpy.ma.core.where |
| `external-call::dep:numpy.ma.core.zeros` | numpy.ma.core.zeros |
| `external-call::dep:numpy.ma.core.zeros_like` | numpy.ma.core.zeros_like |
| `external-call::dep:numpy.ma.extras._covhelper` | numpy.ma.extras._covhelper |
| `external-call::dep:numpy.ma.extras.apply_along_axis` | numpy.ma.extras.apply_along_axis |
| `external-call::dep:numpy.ma.extras.apply_over_axes` | numpy.ma.extras.apply_over_axes |
| `external-call::dep:numpy.ma.extras.atleast_1d` | numpy.ma.extras.atleast_1d |
| `external-call::dep:numpy.ma.extras.atleast_2d` | numpy.ma.extras.atleast_2d |
| `external-call::dep:numpy.ma.extras.atleast_3d` | numpy.ma.extras.atleast_3d |
| `external-call::dep:numpy.ma.extras.average` | numpy.ma.extras.average |
| `external-call::dep:numpy.ma.extras.clump_masked` | numpy.ma.extras.clump_masked |
| `external-call::dep:numpy.ma.extras.clump_unmasked` | numpy.ma.extras.clump_unmasked |
| `external-call::dep:numpy.ma.extras.compress_nd` | numpy.ma.extras.compress_nd |
| `external-call::dep:numpy.ma.extras.compress_rowcols` | numpy.ma.extras.compress_rowcols |
| `external-call::dep:numpy.ma.extras.corrcoef` | numpy.ma.extras.corrcoef |
| `external-call::dep:numpy.ma.extras.cov` | numpy.ma.extras.cov |
| `external-call::dep:numpy.ma.extras.diagflat` | numpy.ma.extras.diagflat |
| `external-call::dep:numpy.ma.extras.dot` | numpy.ma.extras.dot |
| `external-call::dep:numpy.ma.extras.ediff1d` | numpy.ma.extras.ediff1d |
| `external-call::dep:numpy.ma.extras.flatnotmasked_contiguous` | numpy.ma.extras.flatnotmasked_contiguous |
| `external-call::dep:numpy.ma.extras.in1d` | numpy.ma.extras.in1d |
| `external-call::dep:numpy.ma.extras.intersect1d` | numpy.ma.extras.intersect1d |
| `external-call::dep:numpy.ma.extras.isin` | numpy.ma.extras.isin |
| `external-call::dep:numpy.ma.extras.mask_rowcols` | numpy.ma.extras.mask_rowcols |
| `external-call::dep:numpy.ma.extras.masked_all` | numpy.ma.extras.masked_all |
| `external-call::dep:numpy.ma.extras.masked_all_like` | numpy.ma.extras.masked_all_like |
| `external-call::dep:numpy.ma.extras.median` | numpy.ma.extras.median |
| `external-call::dep:numpy.ma.extras.ndenumerate` | numpy.ma.extras.ndenumerate |
| `external-call::dep:numpy.ma.extras.notmasked_contiguous` | numpy.ma.extras.notmasked_contiguous |
| `external-call::dep:numpy.ma.extras.notmasked_edges` | numpy.ma.extras.notmasked_edges |
| `external-call::dep:numpy.ma.extras.polyfit` | numpy.ma.extras.polyfit |
| `external-call::dep:numpy.ma.extras.setdiff1d` | numpy.ma.extras.setdiff1d |
| `external-call::dep:numpy.ma.extras.setxor1d` | numpy.ma.extras.setxor1d |
| `external-call::dep:numpy.ma.extras.stack` | numpy.ma.extras.stack |
| `external-call::dep:numpy.ma.extras.union1d` | numpy.ma.extras.union1d |
| `external-call::dep:numpy.ma.extras.unique` | numpy.ma.extras.unique |
| `external-call::dep:numpy.ma.extras.vstack` | numpy.ma.extras.vstack |
| `external-call::dep:numpy.ma.mrecords.addfield` | numpy.ma.mrecords.addfield |
| `external-call::dep:numpy.ma.mrecords.fromarrays` | numpy.ma.mrecords.fromarrays |
| `external-call::dep:numpy.ma.mrecords.fromrecords` | numpy.ma.mrecords.fromrecords |
| `external-call::dep:numpy.ma.mrecords.fromtextfile` | numpy.ma.mrecords.fromtextfile |
| `external-call::dep:numpy.ma.mrecords.mrecarray` | numpy.ma.mrecords.mrecarray |
| `external-call::dep:numpy.ma.testutils.assert_` | numpy.ma.testutils.assert_ |
| `external-call::dep:numpy.ma.testutils.assert_almost_equal` | numpy.ma.testutils.assert_almost_equal |
| `external-call::dep:numpy.ma.testutils.assert_array_equal` | numpy.ma.testutils.assert_array_equal |
| `external-call::dep:numpy.ma.testutils.assert_equal` | numpy.ma.testutils.assert_equal |
| `external-call::dep:numpy.ma.testutils.assert_equal_records` | numpy.ma.testutils.assert_equal_records |
| `external-call::dep:numpy.ma.testutils.assert_mask_equal` | numpy.ma.testutils.assert_mask_equal |
| `external-call::dep:numpy.ma.testutils.assert_not_equal` | numpy.ma.testutils.assert_not_equal |
| `external-call::dep:numpy.ma.testutils.assert_raises` | numpy.ma.testutils.assert_raises |
| `external-call::dep:numpy.ma.testutils.fail_if_equal` | numpy.ma.testutils.fail_if_equal |

## Entry Points

- `.venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py::TestCompressFunctions.test_dot`
- `.venv-build\Lib\site-packages\numpy\lib\tests\test_recfunctions.py::TestRecFunctions.test_structured_to_unstructured`
- `.venv-build\Lib\site-packages\numpy\ma\tests\test_core.py::TestMaskedArrayArithmetic.test_basic_ufuncs`

## Connected Communities

- **. +53 dirs** (1021 cross-edges)
- **. +6 dirs · numpy._core.umath** (7 cross-edges)
- **. +8 dirs · dedent** (6 cross-edges)
- **. +1 dirs · numpy.lib.recfunctions.merge_ar…** (6 cross-edges)
- **. +114 dirs** (3 cross-edges)
- **site-packages/numpy · __new__** (2 cross-edges)
- **onnxruntime/quantization +4 dirs** (2 cross-edges)
- **. +6 dirs · deepcopy** (2 cross-edges)
- **ma/tests · __array__** (1 cross-edges)
- **. +43 dirs** (1 cross-edges)
- **numpy/f2py +2 dirs** (1 cross-edges)
- **. +2 dirs · numpy.lib._datasource** (1 cross-edges)
- **. +7 dirs · close** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-3352")
explore(operation:"context", task:"understand . +7 dirs · numpy.ma.testutils.assert_equal", format:"gcx")
relations(operation:"usages", target:{symbol:".venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py::TestCompressFunctions.test_dot"}, format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
