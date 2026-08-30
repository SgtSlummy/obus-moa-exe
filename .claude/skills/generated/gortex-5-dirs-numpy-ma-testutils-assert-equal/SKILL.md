---
name: gortex-5-dirs-numpy-ma-testutils-assert-equal
description: "Work in the . +5 dirs · numpy.ma.testutils.assert_equal area — 863 symbols across 178 files (86% cohesion)"
---

# . +5 dirs · numpy.ma.testutils.assert_equal

863 symbols | 178 files | 86% cohesion

## When to Use

Use this skill when working on files in:
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
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_function_base.py` | test_subok |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_io.py` | test_user_missing_values, args, test_dtype_with_converters_and_usecols, test_withmissing_float, roundtrip, ... |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_loadtxt.py` | expected_dtype, generic_data, long_datum, given_dtype, test_parametric_unit_discovery, ... |
| `.venv-build\Lib\site-packages\numpy\lib\tests\test_recfunctions.py` | test_no_r2postfix, test_outer_join, test_drop_fields, dts, test_unnamed_fields, ... |
| `.venv-build\Lib\site-packages\numpy\ma\mrecords.py` | byteorder, soften_mask, attr, options, harden_mask, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_core.py` | test_compressed, _create_data, test_set_record_slice, test_addsumprod, TestMaskedArrayMathMethodsComplex, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_deprecations.py` | test_function_maskedarray, TestMinimumMaximum, TestArgsort, test_function_ndarray, test_method, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py` | test_basic, test_3d_kwargs, test_masked_all_with_object_nested, test_neg_axis, TestCov, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_mrecords.py` | test_byview, test_filled, test_set_fields_mask, test_fromrecords_wmask, test_set_mask_fromarray, ... |
| `.venv-build\Lib\site-packages\numpy\ma\tests\test_subclassing.py` | test_masked_unary_operations, data, test_masked_binary_operations2, __iadd__, test_subclasspreservation, ... |
| `.venv-build\Lib\site-packages\numpy\matrixlib\tests\test_masked_matrix.py` | _series, test_count_mean_with_matrix, test_masked_binary_operations2, test_flat, MMatrix, ... |
| `.venv-build\Lib\site-packages\six.py` | X, __len__ |
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

- **. +54 dirs** (1016 cross-edges)
- **. +6 dirs · numpy._core.umath** (7 cross-edges)
- **. +8 dirs · dedent** (6 cross-edges)
- **. +1 dirs · numpy.lib.recfunctions.merge_ar…** (6 cross-edges)
- **. +112 dirs** (3 cross-edges)
- **. +47 dirs** (2 cross-edges)
- **site-packages/numpy · __new__** (2 cross-edges)
- **. +6 dirs · deepcopy** (2 cross-edges)
- **ma/tests · __array__** (1 cross-edges)
- **. +65 dirs** (1 cross-edges)
- **. +45 dirs** (1 cross-edges)
- **. +2 dirs · numpy.lib._datasource** (1 cross-edges)
- **numpy/f2py +2 dirs** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-3306")
explore(operation:"context", task:"understand . +5 dirs · numpy.ma.testutils.assert_equal", format:"gcx")
relations(operation:"usages", target:{symbol:".venv-build\Lib\site-packages\numpy\ma\tests\test_extras.py::TestCompressFunctions.test_dot"}, format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
