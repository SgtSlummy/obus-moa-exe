---
name: gortex-onnxruntime-transformers-12-dirs
description: "Work in the onnxruntime/transformers +12 dirs area — 1844 symbols across 132 files (92% cohesion)"
---

# onnxruntime/transformers +12 dirs

1844 symbols | 132 files | 92% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `.venv-build\Lib\site-packages\onnxruntime\quantization\base_quantizer.py`
- `.venv-build\Lib\site-packages\onnxruntime\quantization\onnx_model.py`
- `.venv-build\Lib\site-packages\onnxruntime\quantization\onnx_quantizer.py`
- `.venv-build\Lib\site-packages\onnxruntime\quantization\operators\softmax.py`
- `.venv-build\Lib\site-packages\onnxruntime\quantization\quant_utils.py`
- `.venv-build\Lib\site-packages\onnxruntime\tools\onnx_randomizer.py`
- `.venv-build\Lib\site-packages\onnxruntime\tools\qnn\add_trans_cast.py`
- `.venv-build\Lib\site-packages\onnxruntime\tools\qnn\gen_qnn_ctx_onnx_model.py`
- `.venv-build\Lib\site-packages\onnxruntime\tools\symbolic_shape_infer.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\bert_test_data.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\constants.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\convert_generation.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\convert_to_packing_mode.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\dynamo_onnx_helper.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\float16.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_clip.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_sam2.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_unet.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_vae.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_bart_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_base.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_bias_add.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_biasgelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_biassplitgelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_conformer_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_constant_fold.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_embedlayer.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_fastgelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gelu_approximation.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gemmfastgelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention_megatron.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention_no_past.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_group_norm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_layernorm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_mha_dit.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_mha_mmdit.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_nhwc_conv.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_options.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_gelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_layernorm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_matmul.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_quickgelu.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_reshape.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_rotary_attention.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_shape.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_simplified_layernorm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_skip_group_norm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_skiplayernorm.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_transpose.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_utils.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\gpt2\gpt2_helper.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\gpt2\gpt2_parity.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\llama\convert_to_onnx.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\longformer\convert_to_onnx.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\longformer\generate_test_data.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\phi2\convert_to_onnx.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\stable_diffusion\engine_builder_ort_cuda.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\stable_diffusion\optimize_pipeline.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\t5\t5_encoder_decoder_init.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\t5\t5_helper.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\whisper\whisper_chain.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\whisper\whisper_helper.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_exporter.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bart.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert_keras.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert_tf.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_clip.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_conformer.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_gpt2.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_mmdit.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_phi.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_sam2.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_t5.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_tnlr.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_unet.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_vae.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_utils.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\optimizer.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\profiler.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\shape_infer_helper.py`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\shape_optimizer.py`
- `external-call::dep:convert_generation.add_cache_indirection_to_mha`
- `external-call::dep:convert_generation.add_output_qk_to_mha`
- `external-call::dep:convert_generation.fix_past_sequence_length`
- `external-call::dep:convert_generation.get_shared_initializers`
- `external-call::dep:convert_generation.replace_mha_with_gqa`
- `external-call::dep:convert_generation.update_decoder_subgraph_output_cross_attention`
- `external-call::dep:convert_generation.update_decoder_subgraph_share_buffer_and_use_decoder_masked_mha`
- `external-call::dep:convert_to_packing_mode.PackingMode`
- `external-call::dep:float16.float_to_float16_max_diff`
- `external-call::dep:fusion_attention.AttentionMask`
- `external-call::dep:fusion_attention.FusionAttention`
- `external-call::dep:fusion_attention_unet.FusionAttentionUnet`
- `external-call::dep:fusion_attention_vae.FusionAttentionVae`
- `external-call::dep:fusion_bart_attention.FusionBartAttention`
- `external-call::dep:fusion_bias_add.FusionBiasAdd`
- `external-call::dep:fusion_conformer_attention.FusionConformerAttention`
- `external-call::dep:fusion_nhwc_conv.FusionNhwcConv`
- `external-call::dep:fusion_options.FusionOptions`
- `external-call::dep:fusion_qordered_attention.FusionQOrderedAttention`
- `external-call::dep:fusion_transpose.FusionTranspose`
- `external-call::dep:fusion_utils.FusionUtils`
- `external-call::dep:fusion_utils.NumpyHelper`
- `external-call::dep:numpy.allclose`
- `external-call::dep:numpy.array_equal`
- `external-call::dep:onnx.ModelProto`
- `external-call::dep:onnx.ValueInfoProto`
- `external-call::dep:onnx.external_data_helper.load_external_data_for_tensor`
- `external-call::dep:onnx.external_data_helper.set_external_data`
- `external-call::dep:onnx.external_data_helper.uses_external_data`
- `external-call::dep:onnx.helper`
- `external-call::dep:onnx.load_model`
- `external-call::dep:onnx.numpy_helper`
- `external-call::dep:onnx.reference.op_run.to_array_extended`
- `external-call::dep:onnx_model.OnnxModel`
- `external-call::dep:onnx_model_bert.BertOnnxModel`
- `external-call::dep:onnx_utils.extract_raw_data_from_model`
- `external-call::dep:onnx_utils.has_external_data`
- `external-call::dep:optimizer.optimize_model`
- `external-call::dep:shape_infer_helper.SymbolicShapeInferenceHelper`
- `external-call::dep:symbolic_shape_infer.get_shape_from_type_proto`
- `external-call::dep:symbolic_shape_infer.sympy`
- `external-call::dep:t5_decoder.T5DecoderInit`
- `external-call::dep:t5_encoder.T5Encoder`
- `external-call::dep:transformers.WhisperTokenizer`

## Key Files

| File | Symbols |
|------|---------|
| `` | ArgumentParser, argparse.ArgumentParser |
| `.venv-build\Lib\site-packages\onnxruntime\quantization\base_quantizer.py` | weight_scale, bias_name, quantize_weight_per_channel_impl, weight_qType, is_weight_symmetric, ... |
| `.venv-build\Lib\site-packages\onnxruntime\quantization\onnx_model.py` | init, get_constant_value, initializer_extend, _check_init, graph_path, ... |
| `.venv-build\Lib\site-packages\onnxruntime\quantization\onnx_quantizer.py` | initial_type, _get_quantization_params, initial_type, qType, _dequantize_value, ... |
| `.venv-build\Lib\site-packages\onnxruntime\quantization\operators\softmax.py` | quantize |
| `.venv-build\Lib\site-packages\onnxruntime\quantization\quant_utils.py` | pack_bytes_to_4bit, reduce_range, get_qrange_for_qType, src_8bit, symmetric, ... |
| `.venv-build\Lib\site-packages\onnxruntime\tools\onnx_randomizer.py` | randomize_graph_initializer, graph |
| `.venv-build\Lib\site-packages\onnxruntime\tools\qnn\add_trans_cast.py` | rank, rank, compare_onnx_shape_with_qnn_shape, qnn_dims, gen_to_channel_last_perm, ... |
| `.venv-build\Lib\site-packages\onnxruntime\tools\qnn\gen_qnn_ctx_onnx_model.py` | qnn_output_tensor_dic, qnn_input_tensor_dic, quantized_IO, main, model_file_name, ... |
| `.venv-build\Lib\site-packages\onnxruntime\tools\symbolic_shape_infer.py` | _infer_SparseAttention, node, _infer_GroupQueryAttention, node, node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\bert_test_data.py` | input_mask_name, segment_ids_name, find_bert_inputs, get_graph_input_from_embed_node, onnx_file, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\constants.py` | MultiHeadAttentionOutputIDs, MultiHeadAttentionInputIDs, AttentionOutputIDs, AttentionInputIDs, Operators |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\convert_generation.py` | skip_node_idxs, model, use_external_data_format, add_cache_indirection_to_mha, window_size, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\convert_to_packing_mode.py` | _are_attentions_supported, use_symbolic_shape_infer, PackingMode, _get_input_to_remove_padding, use_symbolic_shape_infer, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\dynamo_onnx_helper.py` | vals, data_type, name, add_initializer, __init__, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\float16.py` | min_positive_val, convert_tensor_float_to_float16, min_positive_val, _npfloat16_to_int, tensor, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention.py` | get_num_heads_and_hidden_size_from_concat, disable_multi_head_attention_bias, AttentionMask, get_num_heads_and_hidden_size, create_attention_node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_clip.py` | normalize_node, get_num_heads_and_hidden_size, output_name_to_node, reshape_q, hidden_size, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_sam2.py` | transpose_k, get_hidden_size, reshape_in, output_name_to_node, transpose_v, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_unet.py` | root_input, reshape_q, match_lora_path, v_matmul, get_num_heads_and_hidden_size, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_attention_vae.py` | create_attention_node, num_heads, add_q, fuse, input_name, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_bart_attention.py` | model, __init__, fuse, attention_mask, FusionBartAttention, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_base.py` | tensor, remove_initializer, add_initializer, raw, vals, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_bias_add.py` | input_name_to_nodes, FusionBiasAdd, __init__, output_name_to_node, add_node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_biasgelu.py` | model, node, input_name_to_nodes, is_fastgelu, __init__, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_biassplitgelu.py` | input_name_to_nodes, gelu_node, fuse, output_name_to_node, FusionBiasSplitGelu, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_conformer_attention.py` | __init__, FusionConformerAttention, model, input_name_to_nodes, attention_mask, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_constant_fold.py` | node, input_name_to_nodes, fuse_1, output_name_to_node |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_embedlayer.py` | layernorm, check_attention_subgraph, node, output_name_to_node, input_name, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_fastgelu.py` | tanh_node, tanh_node, input_name_to_nodes, FusionFastGelu, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gelu.py` | input_name_to_nodes, output_name_to_node, erf_node, erf_node, model, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gelu_approximation.py` | output_name_to_node, node, model, input_name_to_nodes, FusionGeluApproximation, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gemmfastgelu.py` | input_name, get_dimensions, output_name_to_node, FusionGemmFastGelu, fuse, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention.py` | is_unidirectional, concat_v, output, mask, model, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention_megatron.py` | is_close, add_before_split, input_name_to_nodes, num_heads, value, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_gpt_attention_no_past.py` | num_heads, output, gemm_qkv, create_attention_node, input, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_group_norm.py` | FusionGroupNorm, add_node, output_name_to_node, channels_last, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_layernorm.py` | __init__, force, node, output_name, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_mha_dit.py` | output_name_to_node, input_name, output_name_to_node, detect_num_heads, scale, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_mha_mmdit.py` | add, mul_q, num_heads, input_name_to_nodes, output_name_to_node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_nhwc_conv.py` | create_transpose_node, update_weight, fuse, perm, output_name_to_node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_options.py` | model_type, use_raw_attention_mask, FusionOptions, parser, parse, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_attention.py` | get_num_heads_and_hidden_size, normalize_node, output_name_to_node, input_name_to_nodes, num_heads, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_gelu.py` | fuse, node, model, FusionQOrderedGelu, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_layernorm.py` | input_name_to_nodes, output_name_to_node, fuse, FusionQOrderedLayerNormalization, node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_matmul.py` | FusionQOrderedMatMul, __init__, node, input_name_to_nodes, output_name_to_node, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_quickgelu.py` | FusionQuickGelu, model, node, fuse, __init__, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_reshape.py` | concat_node, reshape_node, shape, __init__, fuse, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_rotary_attention.py` | create_cos_sin_cache_from_on_the_fly_rope, cos_slice, reshape_v_1, present_k, reshape_k, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_shape.py` | concat_node, input_name, tensor_proto, get_dimensions_from_tensor_proto, FusionShape, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_simplified_layernorm.py` | __init__, model, model, node, FusionSimplifiedLayerNormalization, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_skip_group_norm.py` | model, bias_name, input_name_to_nodes, output_name_to_node, output_name, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_skiplayernorm.py` | FusionSkipLayerNormalization, __init__, fuse, model, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_transpose.py` | FusionTranspose, input_name, output_name_to_node, __init__, model, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_utils.py` | remove_useless_reshape_nodes, node, node, node, parent_input_index, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\gpt2\gpt2_helper.py` | optimize_onnx, auto_mixed_precision, onnx_model_path, num_attention_heads, auto_mixed_precision, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\gpt2\gpt2_parity.py` | get_last_matmul_node_name, raw_onnx_model |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\llama\convert_to_onnx.py` | world_size, use_group_query_attention, window_size, model_opt, config |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\longformer\convert_to_onnx.py` | fp32_model_path, onnx_model_path, fp16_model_path, optimize_longformer |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\longformer\generate_test_data.py` | get_longformer_inputs, global_mask_name, onnx_file, input_ids_name, input_mask_name |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\phi2\convert_to_onnx.py` | out_onnx_path, in_onnx_path, convert_to_use_cuda_graph |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\stable_diffusion\engine_builder_ort_cuda.py` | import_diffusers_engine, diffusers_onnx_dir, engine_dir |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\stable_diffusion\optimize_pipeline.py` | argv, parse_arguments |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\t5\t5_encoder_decoder_init.py` | device, decoder_start_token_id, decoder, model, T5EncoderDecoderInit, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\t5\t5_helper.py` | use_external_data_format, optimize_onnx, num_attention_heads, hidden_size, force_fp16_logits, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\whisper\whisper_chain.py` | graph_inputs, verify_inputs, args, beam_inputs, arr, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\models\whisper\whisper_helper.py` | optimized_model_path, no_beam_search_op, is_float16, num_attention_heads, use_external_data_format, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_exporter.py` | overwrite, use_external_data_format, flatten, use_gpu, onnx_model_path, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model.py` | node, use_float16, output_name_to_node, _get_subgraph_nodes_and_inputs, remove_cascaded_cast_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bart.py` | fuse, __init__, model_impl, model, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert.py` | model, change_graph_inputs_to_int32, get_graph_inputs_from_fused_nodes, clean_graph, casted, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert_keras.py` | match_mask_path, output_name_to_node, fuse_attention, BertOnnxModelKeras, __init__, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_bert_tf.py` | current_node, model, excluded_graph_inputs, position_embedding, num_heads, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_clip.py` | get_fused_operator_statistics |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_conformer.py` | num_heads, options, optimize, __init__, hidden_size, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_gpt2.py` | postprocess |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_mmdit.py` | get_fused_operator_statistics, postprocess |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_phi.py` | k_w, get_gqa_aux_nodes, add_int64_value_info, inputs, v_w, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_sam2.py` | options, get_fused_operator_statistics, postprocess |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_t5.py` | output_name_to_node, k_matmul, output_name_to_node, key, input_name_to_nodes, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_tnlr.py` | num_heads, __init__, mask_index, input_name_to_nodes, model, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_unet.py` | hidden_size, preprocess, UnetOnnxModel, convert_conv_to_nhwc, options, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_model_vae.py` | fuse_multi_head_attention, num_heads, __init__, get_fused_operator_statistics, options, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\onnx_utils.py` | extract_raw_data_from_model, model, has_external_data, model |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\optimizer.py` | save_as_external_data, optimization_options, disabled_optimizers, model_type, deprecated_kwargs, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\profiler.py` | onnx_model, samples, create_dummy_inputs, sequence_length, batch_size |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\shape_infer_helper.py` | edge_other, max_runs, model, verbose, _get_sympy_shape, ... |
| `.venv-build\Lib\site-packages\onnxruntime\transformers\shape_optimizer.py` | onnx_model, main, segment_ids, validate_input, shape_optimization, ... |
| `external-call::dep:convert_generation.add_cache_indirection_to_mha` | convert_generation.add_cache_indirection_to_mha |
| `external-call::dep:convert_generation.add_output_qk_to_mha` | convert_generation.add_output_qk_to_mha |
| `external-call::dep:convert_generation.fix_past_sequence_length` | convert_generation.fix_past_sequence_length |
| `external-call::dep:convert_generation.get_shared_initializers` | convert_generation.get_shared_initializers |
| `external-call::dep:convert_generation.replace_mha_with_gqa` | convert_generation.replace_mha_with_gqa |
| `external-call::dep:convert_generation.update_decoder_subgraph_output_cross_attention` | convert_generation.update_decoder_subgraph_output_cross_attention |
| `external-call::dep:convert_generation.update_decoder_subgraph_share_buffer_and_use_decoder_masked_mha` | convert_generation.update_decoder_subgraph_share_buffer_and_use_decoder_masked_mha |
| `external-call::dep:convert_to_packing_mode.PackingMode` | convert_to_packing_mode.PackingMode |
| `external-call::dep:float16.float_to_float16_max_diff` | float16.float_to_float16_max_diff |
| `external-call::dep:fusion_attention.AttentionMask` | fusion_attention.AttentionMask |
| `external-call::dep:fusion_attention.FusionAttention` | fusion_attention.FusionAttention |
| `external-call::dep:fusion_attention_unet.FusionAttentionUnet` | fusion_attention_unet.FusionAttentionUnet |
| `external-call::dep:fusion_attention_vae.FusionAttentionVae` | fusion_attention_vae.FusionAttentionVae |
| `external-call::dep:fusion_bart_attention.FusionBartAttention` | fusion_bart_attention.FusionBartAttention |
| `external-call::dep:fusion_bias_add.FusionBiasAdd` | fusion_bias_add.FusionBiasAdd |
| `external-call::dep:fusion_conformer_attention.FusionConformerAttention` | fusion_conformer_attention.FusionConformerAttention |
| `external-call::dep:fusion_nhwc_conv.FusionNhwcConv` | fusion_nhwc_conv.FusionNhwcConv |
| `external-call::dep:fusion_options.FusionOptions` | fusion_options.FusionOptions |
| `external-call::dep:fusion_qordered_attention.FusionQOrderedAttention` | fusion_qordered_attention.FusionQOrderedAttention |
| `external-call::dep:fusion_transpose.FusionTranspose` | fusion_transpose.FusionTranspose |
| `external-call::dep:fusion_utils.FusionUtils` | fusion_utils.FusionUtils |
| `external-call::dep:fusion_utils.NumpyHelper` | fusion_utils.NumpyHelper |
| `external-call::dep:numpy.allclose` | numpy.allclose |
| `external-call::dep:numpy.array_equal` | numpy.array_equal |
| `external-call::dep:onnx.ModelProto` | onnx.ModelProto |
| `external-call::dep:onnx.ValueInfoProto` | onnx.ValueInfoProto |
| `external-call::dep:onnx.external_data_helper.load_external_data_for_tensor` | onnx.external_data_helper.load_external_data_for_tensor |
| `external-call::dep:onnx.external_data_helper.set_external_data` | onnx.external_data_helper.set_external_data |
| `external-call::dep:onnx.external_data_helper.uses_external_data` | onnx.external_data_helper.uses_external_data |
| `external-call::dep:onnx.helper` | onnx.helper |
| `external-call::dep:onnx.load_model` | onnx.load_model |
| `external-call::dep:onnx.numpy_helper` | onnx.numpy_helper |
| `external-call::dep:onnx.reference.op_run.to_array_extended` | onnx.reference.op_run.to_array_extended |
| `external-call::dep:onnx_model.OnnxModel` | onnx_model.OnnxModel |
| `external-call::dep:onnx_model_bert.BertOnnxModel` | onnx_model_bert.BertOnnxModel |
| `external-call::dep:onnx_utils.extract_raw_data_from_model` | onnx_utils.extract_raw_data_from_model |
| `external-call::dep:onnx_utils.has_external_data` | onnx_utils.has_external_data |
| `external-call::dep:optimizer.optimize_model` | optimizer.optimize_model |
| `external-call::dep:shape_infer_helper.SymbolicShapeInferenceHelper` | shape_infer_helper.SymbolicShapeInferenceHelper |
| `external-call::dep:symbolic_shape_infer.get_shape_from_type_proto` | symbolic_shape_infer.get_shape_from_type_proto |
| `external-call::dep:symbolic_shape_infer.sympy` | symbolic_shape_infer.sympy |
| `external-call::dep:t5_decoder.T5DecoderInit` | t5_decoder.T5DecoderInit |
| `external-call::dep:t5_encoder.T5Encoder` | t5_encoder.T5Encoder |
| `external-call::dep:transformers.WhisperTokenizer` | transformers.WhisperTokenizer |

## Entry Points

- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_attention.py::FusionQOrderedAttention.fuse`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\float16.py::convert_float_to_float16`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\models\whisper\whisper_chain.py::chain_model`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_rotary_attention.py::FusionRotaryAttention.fuse`
- `.venv-build\Lib\site-packages\onnxruntime\transformers\fusion_rotary_attention.py::FusionRotaryEmbeddings.fuse`

## Connected Communities

- **. +54 dirs** (111 cross-edges)
- **quantization/operators +9 dirs** (60 cross-edges)
- **. +112 dirs** (21 cross-edges)
- **onnxruntime/quantization +2 dirs** (14 cross-edges)
- **. +32 dirs** (12 cross-edges)
- **. +65 dirs** (12 cross-edges)
- **. +3 dirs · update** (10 cross-edges)
- **onnxruntime/quantization +1 dirs · find_by_name** (8 cross-edges)
- **. +2 dirs · SymbolicShapeInference** (8 cross-edges)
- **. +1 dirs · apply** (7 cross-edges)
- **onnxruntime/quantization +1 dirs · ONNXModel** (5 cross-edges)
- **site-packages/fsspec +7 dirs** (5 cross-edges)
- **. +1 dirs · quantize_nparray** (4 cross-edges)
- **onnxruntime/tools +17 dirs** (4 cross-edges)
- **_core/tests +5 dirs** (4 cross-edges)
- **. +2 dirs · export_onnx** (2 cross-edges)
- **tools/qnn · parse_qnn_graph** (2 cross-edges)
- **. +1 dirs · build_engines** (2 cross-edges)
- **onnxruntime/transformers +5 dirs** (2 cross-edges)
- **onnxruntime/transformers · fuse · onnx_model_phi** (2 cross-edges)
- **. +47 dirs** (1 cross-edges)
- **site-packages/PIL +19 dirs** (1 cross-edges)
- **site-packages/huggingface_hub +17 dirs** (1 cross-edges)
- **. +3 dirs · test_parity** (1 cross-edges)
- **onnxruntime/transformers · create_gpt2_inputs** (1 cross-edges)
- **tools/qnn · parse_qnn_json_file** (1 cross-edges)
- **. +5 dirs · invoke** (1 cross-edges)
- **. +2 dirs · run_one_test** (1 cross-edges)
- **. +7 dirs · defaultdict** (1 cross-edges)
- **. +6 dirs · numpy._core.umath** (1 cross-edges)
- **. +2 dirs · setup_logging** (1 cross-edges)
- **. +4 dirs · onnxruntime.capi._pybind_state** (1 cross-edges)
- **. +6 dirs · genfromtxt** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-3322")
explore(operation:"context", task:"understand onnxruntime/transformers +12 dirs", format:"gcx")
relations(operation:"usages", target:{symbol:".venv-build\Lib\site-packages\onnxruntime\transformers\fusion_qordered_attention.py::FusionQOrderedAttention.fuse"}, format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
