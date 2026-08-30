---
name: gortex-8-dirs-cython
description: "Work in the . +8 dirs · cython area — 1280 symbols across 126 files (97% cohesion)"
---

# . +8 dirs · cython

1280 symbols | 126 files | 97% cohesion

## When to Use

Use this skill when working on files in:
- `.venv-build\Lib\site-packages\av\audio\codeccontext.py`
- `.venv-build\Lib\site-packages\av\audio\fifo.py`
- `.venv-build\Lib\site-packages\av\audio\frame.py`
- `.venv-build\Lib\site-packages\av\audio\layout.py`
- `.venv-build\Lib\site-packages\av\audio\plane.py`
- `.venv-build\Lib\site-packages\av\audio\stream.py`
- `.venv-build\Lib\site-packages\av\bitstream.py`
- `.venv-build\Lib\site-packages\av\buffer.py`
- `.venv-build\Lib\site-packages\av\codec\codec.py`
- `.venv-build\Lib\site-packages\av\codec\context.py`
- `.venv-build\Lib\site-packages\av\codec\hwaccel.py`
- `.venv-build\Lib\site-packages\av\container\core.py`
- `.venv-build\Lib\site-packages\av\container\input.py`
- `.venv-build\Lib\site-packages\av\container\output.py`
- `.venv-build\Lib\site-packages\av\container\pyio.py`
- `.venv-build\Lib\site-packages\av\container\streams.py`
- `.venv-build\Lib\site-packages\av\device.py`
- `.venv-build\Lib\site-packages\av\dictionary.py`
- `.venv-build\Lib\site-packages\av\error.py`
- `.venv-build\Lib\site-packages\av\filter\context.py`
- `.venv-build\Lib\site-packages\av\filter\filter.py`
- `.venv-build\Lib\site-packages\av\filter\graph.py`
- `.venv-build\Lib\site-packages\av\filter\link.py`
- `.venv-build\Lib\site-packages\av\filter\loudnorm.py`
- `.venv-build\Lib\site-packages\av\format.py`
- `.venv-build\Lib\site-packages\av\frame.py`
- `.venv-build\Lib\site-packages\av\index.py`
- `.venv-build\Lib\site-packages\av\logging.py`
- `.venv-build\Lib\site-packages\av\opaque.py`
- `.venv-build\Lib\site-packages\av\packet.py`
- `.venv-build\Lib\site-packages\av\plane.py`
- `.venv-build\Lib\site-packages\av\rational.py`
- `.venv-build\Lib\site-packages\av\sidedata\encparams.py`
- `.venv-build\Lib\site-packages\av\sidedata\motionvectors.py`
- `.venv-build\Lib\site-packages\av\sidedata\sidedata.py`
- `.venv-build\Lib\site-packages\av\stream.py`
- `.venv-build\Lib\site-packages\av\subtitles\codeccontext.py`
- `.venv-build\Lib\site-packages\av\subtitles\stream.py`
- `.venv-build\Lib\site-packages\av\subtitles\subtitle.py`
- `.venv-build\Lib\site-packages\av\utils.py`
- `.venv-build\Lib\site-packages\av\video\codeccontext.py`
- `.venv-build\Lib\site-packages\av\video\frame.py`
- `.venv-build\Lib\site-packages\av\video\plane.py`
- `.venv-build\Lib\site-packages\av\video\reformatter.py`
- `.venv-build\Lib\site-packages\av\video\stream.py`
- `external-call::dep:av.audio.codeccontext.AudioCodecContext`
- `external-call::dep:av.audio.stream.AudioStream`
- `external-call::dep:av.container.core.open`
- `external-call::dep:av.logging`
- `external-call::dep:av.logging.Capture`
- `external-call::dep:av.logging.get_level`
- `external-call::dep:av.logging.set_level`
- `external-call::dep:av.sidedata.encparams.VideoEncParams`
- `external-call::dep:av.sidedata.motionvectors.MotionVectors`
- `external-call::dep:av.sidedata.sidedata.SideDataContainer`
- `external-call::dep:av.subtitles.codeccontext.SubtitleCodecContext`
- `external-call::dep:av.subtitles.stream.SubtitleStream`
- `external-call::dep:av.video.codeccontext.VideoCodecContext`
- `external-call::dep:av.video.stream.VideoStream`
- `external-call::dep:cython.cimports.av.audio.format.get_audio_format`
- `external-call::dep:cython.cimports.av.audio.frame.alloc_audio_frame`
- `external-call::dep:cython.cimports.av.audio.plane.AudioPlane`
- `external-call::dep:cython.cimports.av.bitstream.BitStreamFilterContext`
- `external-call::dep:cython.cimports.av.buffer.bytesource`
- `external-call::dep:cython.cimports.av.codec.codec.Codec`
- `external-call::dep:cython.cimports.av.codec.codec.wrap_codec`
- `external-call::dep:cython.cimports.av.codec.context.CodecContext`
- `external-call::dep:cython.cimports.av.codec.context.wrap_codec_context`
- `external-call::dep:cython.cimports.av.codec.hwaccel.wrap_hwconfig`
- `external-call::dep:cython.cimports.av.container.input.InputContainer`
- `external-call::dep:cython.cimports.av.container.output.OutputContainer`
- `external-call::dep:cython.cimports.av.container.pyio.pyio_close_custom_gil`
- `external-call::dep:cython.cimports.av.container.pyio.pyio_close_gil`
- `external-call::dep:cython.cimports.av.container.streams.StreamContainer`
- `external-call::dep:cython.cimports.av.dictionary.Dictionary`
- `external-call::dep:cython.cimports.av.error.err_check`
- `external-call::dep:cython.cimports.av.error.stash_exception`
- `external-call::dep:cython.cimports.av.filter.context.wrap_filter_context`
- `external-call::dep:cython.cimports.av.filter.filter.Filter`
- `external-call::dep:cython.cimports.av.filter.filter.wrap_filter`
- `external-call::dep:cython.cimports.av.filter.link.alloc_filter_pads`
- `external-call::dep:cython.cimports.av.format.build_container_format`
- `external-call::dep:cython.cimports.av.index.wrap_index_entries`
- `external-call::dep:cython.cimports.av.logging.get_last_error`
- `external-call::dep:cython.cimports.av.opaque.opaque_container`
- `external-call::dep:cython.cimports.av.packet.Packet`
- `external-call::dep:cython.cimports.av.rational.from_avrational`
- `external-call::dep:cython.cimports.av.sidedata.sidedata.SideData`
- `external-call::dep:cython.cimports.av.sidedata.sidedata.get_display_rotation`
- `external-call::dep:cython.cimports.av.stream.Stream`
- `external-call::dep:cython.cimports.av.stream.wrap_stream`
- `external-call::dep:cython.cimports.av.subtitles.subtitle.SubtitleProxy`
- `external-call::dep:cython.cimports.av.subtitles.subtitle.SubtitleSet`
- `external-call::dep:cython.cimports.av.utils.avdict_to_dict`
- `external-call::dep:cython.cimports.av.utils.avrational_to_fraction`
- `external-call::dep:cython.cimports.av.utils.dict_to_avdict`
- `external-call::dep:cython.cimports.av.utils.to_avrational`
- `external-call::dep:cython.cimports.av.video.format.VideoFormat`
- `external-call::dep:cython.cimports.av.video.format.VideoFormatComponent`
- `external-call::dep:cython.cimports.av.video.format.get_pix_fmt`
- `external-call::dep:cython.cimports.av.video.format.get_video_format`
- `external-call::dep:cython.cimports.av.video.frame.alloc_video_frame`
- `external-call::dep:cython.cimports.av.video.plane.VideoPlane`
- `external-call::dep:cython.cimports.av.video.reformatter.VideoReformatter`
- `external-call::dep:cython.cimports.cpython.PyBuffer_FillInfo`
- `external-call::dep:cython.cimports.cpython.PyBytes_FromString`
- `external-call::dep:cython.cimports.cpython.buffer.PyBuffer_Release`
- `external-call::dep:cython.cimports.cpython.buffer.PyObject_CheckBuffer`
- `external-call::dep:cython.cimports.cpython.buffer.PyObject_GetBuffer`
- `external-call::dep:cython.cimports.cpython.bytes.PyBytes_FromStringAndSize`
- `external-call::dep:cython.cimports.cpython.exc.PyErr_Clear`
- `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_GetPointer`
- `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_IsValid`
- `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_New`
- `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_SetName`
- `external-call::dep:cython.cimports.cpython.ref.Py_DECREF`
- `external-call::dep:cython.cimports.cpython.ref.Py_INCREF`
- `external-call::dep:cython.cimports.libav`
- `external-call::dep:cython.cimports.libc.stdlib.free`
- `external-call::dep:cython.cimports.libc.stdlib.malloc`
- `external-call::dep:cython.cimports.libc.string.memcpy`
- `external-call::dep:cython.cimports.libc.string.memset`
- `external-call::dep:cython.cimports.libc.string.strcmp`
- `external-call::dep:cython.operator.dereference`
- `external-call::dep:cython.sizeof`
- `external-call::stdlib:cython`

## Key Files

| File | Symbols |
|------|---------|
| `.venv-build\Lib\site-packages\av\audio\codeccontext.py` | packet, _setup_decoded_frame, _alloc_next_frame, frame |
| `.venv-build\Lib\site-packages\av\audio\fifo.py` | AudioFifo, write, frame, format, samples, ... |
| `.venv-build\Lib\site-packages\av\audio\frame.py` | sample_rate, planes, array, value, rate, ... |
| `.venv-build\Lib\site-packages\av\audio\layout.py` | name, __eq__, __cinit__, other, AudioLayout, ... |
| `.venv-build\Lib\site-packages\av\audio\plane.py` | __cinit__, _buffer_size, frame, AudioPlane, index |
| `.venv-build\Lib\site-packages\av\audio\stream.py` | decode, name, packet, encode, AudioStream, ... |
| `.venv-build\Lib\site-packages\av\bitstream.py` | flush, filter_description, in_stream, packet, filter, ... |
| `.venv-build\Lib\site-packages\av\buffer.py` | owner, __cinit__, allow_none, bytesource, obj, ... |
| `.venv-build\Lib\site-packages\av\codec\codec.py` | name, audio_rates, name, UnknownCodecError, has_alpha, ... |
| `.venv-build\Lib\site-packages\av\codec\context.py` | frame, create, c_codec, packet, supported_options, ... |
| `.venv-build\Lib\site-packages\av\codec\hwaccel.py` | device_type, format, for_encoding, flags, create, ... |
| `.venv-build\Lib\site-packages\av\container\core.py` | open, format_name, err_check, p, pb, ... |
| `.venv-build\Lib\site-packages\av\container\input.py` | stream, size, any_frame, args, demux, ... |
| `.venv-build\Lib\site-packages\av\container\output.py` | args, add_mux_stream, _try_extract_extradata, codec_name, data, ... |
| `.venv-build\Lib\site-packages\av\container\pyio.py` | __cinit__, buf_size, pyio_seek_gil, buf, opaque, ... |
| `.venv-build\Lib\site-packages\av\container\streams.py` | _get_media_type_enum, related, type, related, best, ... |
| `.venv-build\Lib\site-packages\av\device.py` | __init__, enumerate_input_devices, __repr__, format_name, format_name, ... |
| `.venv-build\Lib\site-packages\av\dictionary.py` | Dictionary, wrap_dictionary, keys, other, args, ... |
| `.venv-build\Lib\site-packages\av\error.py` | filename, codes, err_check, res, name, ... |
| `.venv-build\Lib\site-packages\av\filter\context.py` | FilterContext, link_to, flags, res_len, push, ... |
| `.venv-build\Lib\site-packages\av\filter\filter.py` | __cinit__, outputs, inputs, Filter, name, ... |
| `.venv-build\Lib\site-packages\av\filter\graph.py` | configure, width, frame_size, Graph, add_buffer, ... |
| `.venv-build\Lib\site-packages\av\filter\link.py` | is_input, filter, ptr, alloc_filter_pads, context |
| `.venv-build\Lib\site-packages\av\filter\loudnorm.py` | stats, loudnorm_args, stream |
| `.venv-build\Lib\site-packages\av\format.py` | name, get_input_format_names, get_output_format_names, mode, __cinit__ |
| `.venv-build\Lib\site-packages\av\frame.py` | v, key_frame, time_base, is_corrupt, value, ... |
| `.venv-build\Lib\site-packages\av\index.py` | __len__ |
| `.venv-build\Lib\site-packages\av\logging.py` | log_callback, set_level, format, format, name, ... |
| `.venv-build\Lib\site-packages\av\opaque.py` | data, __cinit__, OpaqueContainer, add, v, ... |
| `.venv-build\Lib\site-packages\av\packet.py` | __cinit__, time_base, time_base, dtype, pts, ... |
| `.venv-build\Lib\site-packages\av\plane.py` | __cinit__, frame, __repr__, Plane, index, ... |
| `.venv-build\Lib\site-packages\av\rational.py` | den, __init__, num |
| `.venv-build\Lib\site-packages\av\sidedata\encparams.py` | __init__, block_size, nb_blocks, __repr__, VideoBlockParams, ... |
| `.venv-build\Lib\site-packages\av\sidedata\motionvectors.py` | index, __len__, index, sentinel, __getitem__, ... |
| `.venv-build\Lib\site-packages\av\sidedata\sidedata.py` | frame, _buffer_ptr, _SideDataContainer, frame, SideData, ... |
| `.venv-build\Lib\site-packages\av\stream.py` | codec_context, _init, value, id, value, ... |
| `.venv-build\Lib\site-packages\av\subtitles\codeccontext.py` | encode_subtitle, _decode, subtitle_header, packet, subtitle, ... |
| `.venv-build\Lib\site-packages\av\subtitles\stream.py` | SubtitleStream, name, decode, __getattr__, packet |
| `.venv-build\Lib\site-packages\av\subtitles\subtitle.py` | index, BitmapSubtitle, index, subtitle, create, ... |
| `.venv-build\Lib\site-packages\av\utils.py` | encoding, errors, dst, dict_to_avdict, src |
| `.venv-build\Lib\site-packages\av\video\codeccontext.py` | color_primaries, color_range, frame, value, VideoCodecContext, ... |
| `.venv-build\Lib\site-packages\av\video\frame.py` | get_frames_ctx, device_id, _init, device_ctx, set_image, ... |
| `.venv-build\Lib\site-packages\av\video\plane.py` | view, stream, VideoPlane, __cinit__, __dlpack_device__, ... |
| `.venv-build\Lib\site-packages\av\video\reformatter.py` | threads, threads, default, dst_color_primaries, colorspace, ... |
| `.venv-build\Lib\site-packages\av\video\stream.py` | sample_aspect_ratio, vflip, guessed_rate, set_display_rotation, average_rate, ... |
| `external-call::dep:av.audio.codeccontext.AudioCodecContext` | av.audio.codeccontext.AudioCodecContext |
| `external-call::dep:av.audio.stream.AudioStream` | av.audio.stream.AudioStream |
| `external-call::dep:av.container.core.open` | av.container.core.open |
| `external-call::dep:av.logging` | av.logging |
| `external-call::dep:av.logging.Capture` | av.logging.Capture |
| `external-call::dep:av.logging.get_level` | av.logging.get_level |
| `external-call::dep:av.logging.set_level` | av.logging.set_level |
| `external-call::dep:av.sidedata.encparams.VideoEncParams` | av.sidedata.encparams.VideoEncParams |
| `external-call::dep:av.sidedata.motionvectors.MotionVectors` | av.sidedata.motionvectors.MotionVectors |
| `external-call::dep:av.sidedata.sidedata.SideDataContainer` | av.sidedata.sidedata.SideDataContainer |
| `external-call::dep:av.subtitles.codeccontext.SubtitleCodecContext` | av.subtitles.codeccontext.SubtitleCodecContext |
| `external-call::dep:av.subtitles.stream.SubtitleStream` | av.subtitles.stream.SubtitleStream |
| `external-call::dep:av.video.codeccontext.VideoCodecContext` | av.video.codeccontext.VideoCodecContext |
| `external-call::dep:av.video.stream.VideoStream` | av.video.stream.VideoStream |
| `external-call::dep:cython.cimports.av.audio.format.get_audio_format` | cython.cimports.av.audio.format.get_audio_format |
| `external-call::dep:cython.cimports.av.audio.frame.alloc_audio_frame` | cython.cimports.av.audio.frame.alloc_audio_frame |
| `external-call::dep:cython.cimports.av.audio.plane.AudioPlane` | cython.cimports.av.audio.plane.AudioPlane |
| `external-call::dep:cython.cimports.av.bitstream.BitStreamFilterContext` | cython.cimports.av.bitstream.BitStreamFilterContext |
| `external-call::dep:cython.cimports.av.buffer.bytesource` | cython.cimports.av.buffer.bytesource |
| `external-call::dep:cython.cimports.av.codec.codec.Codec` | cython.cimports.av.codec.codec.Codec |
| `external-call::dep:cython.cimports.av.codec.codec.wrap_codec` | cython.cimports.av.codec.codec.wrap_codec |
| `external-call::dep:cython.cimports.av.codec.context.CodecContext` | cython.cimports.av.codec.context.CodecContext |
| `external-call::dep:cython.cimports.av.codec.context.wrap_codec_context` | cython.cimports.av.codec.context.wrap_codec_context |
| `external-call::dep:cython.cimports.av.codec.hwaccel.wrap_hwconfig` | cython.cimports.av.codec.hwaccel.wrap_hwconfig |
| `external-call::dep:cython.cimports.av.container.input.InputContainer` | cython.cimports.av.container.input.InputContainer |
| `external-call::dep:cython.cimports.av.container.output.OutputContainer` | cython.cimports.av.container.output.OutputContainer |
| `external-call::dep:cython.cimports.av.container.pyio.pyio_close_custom_gil` | cython.cimports.av.container.pyio.pyio_close_custom_gil |
| `external-call::dep:cython.cimports.av.container.pyio.pyio_close_gil` | cython.cimports.av.container.pyio.pyio_close_gil |
| `external-call::dep:cython.cimports.av.container.streams.StreamContainer` | cython.cimports.av.container.streams.StreamContainer |
| `external-call::dep:cython.cimports.av.dictionary.Dictionary` | cython.cimports.av.dictionary.Dictionary |
| `external-call::dep:cython.cimports.av.error.err_check` | cython.cimports.av.error.err_check |
| `external-call::dep:cython.cimports.av.error.stash_exception` | cython.cimports.av.error.stash_exception |
| `external-call::dep:cython.cimports.av.filter.context.wrap_filter_context` | cython.cimports.av.filter.context.wrap_filter_context |
| `external-call::dep:cython.cimports.av.filter.filter.Filter` | cython.cimports.av.filter.filter.Filter |
| `external-call::dep:cython.cimports.av.filter.filter.wrap_filter` | cython.cimports.av.filter.filter.wrap_filter |
| `external-call::dep:cython.cimports.av.filter.link.alloc_filter_pads` | cython.cimports.av.filter.link.alloc_filter_pads |
| `external-call::dep:cython.cimports.av.format.build_container_format` | cython.cimports.av.format.build_container_format |
| `external-call::dep:cython.cimports.av.index.wrap_index_entries` | cython.cimports.av.index.wrap_index_entries |
| `external-call::dep:cython.cimports.av.logging.get_last_error` | cython.cimports.av.logging.get_last_error |
| `external-call::dep:cython.cimports.av.opaque.opaque_container` | cython.cimports.av.opaque.opaque_container |
| `external-call::dep:cython.cimports.av.packet.Packet` | cython.cimports.av.packet.Packet |
| `external-call::dep:cython.cimports.av.rational.from_avrational` | cython.cimports.av.rational.from_avrational |
| `external-call::dep:cython.cimports.av.sidedata.sidedata.SideData` | cython.cimports.av.sidedata.sidedata.SideData |
| `external-call::dep:cython.cimports.av.sidedata.sidedata.get_display_rotation` | cython.cimports.av.sidedata.sidedata.get_display_rotation |
| `external-call::dep:cython.cimports.av.stream.Stream` | cython.cimports.av.stream.Stream |
| `external-call::dep:cython.cimports.av.stream.wrap_stream` | cython.cimports.av.stream.wrap_stream |
| `external-call::dep:cython.cimports.av.subtitles.subtitle.SubtitleProxy` | cython.cimports.av.subtitles.subtitle.SubtitleProxy |
| `external-call::dep:cython.cimports.av.subtitles.subtitle.SubtitleSet` | cython.cimports.av.subtitles.subtitle.SubtitleSet |
| `external-call::dep:cython.cimports.av.utils.avdict_to_dict` | cython.cimports.av.utils.avdict_to_dict |
| `external-call::dep:cython.cimports.av.utils.avrational_to_fraction` | cython.cimports.av.utils.avrational_to_fraction |
| `external-call::dep:cython.cimports.av.utils.dict_to_avdict` | cython.cimports.av.utils.dict_to_avdict |
| `external-call::dep:cython.cimports.av.utils.to_avrational` | cython.cimports.av.utils.to_avrational |
| `external-call::dep:cython.cimports.av.video.format.VideoFormat` | cython.cimports.av.video.format.VideoFormat |
| `external-call::dep:cython.cimports.av.video.format.VideoFormatComponent` | cython.cimports.av.video.format.VideoFormatComponent |
| `external-call::dep:cython.cimports.av.video.format.get_pix_fmt` | cython.cimports.av.video.format.get_pix_fmt |
| `external-call::dep:cython.cimports.av.video.format.get_video_format` | cython.cimports.av.video.format.get_video_format |
| `external-call::dep:cython.cimports.av.video.frame.alloc_video_frame` | cython.cimports.av.video.frame.alloc_video_frame |
| `external-call::dep:cython.cimports.av.video.plane.VideoPlane` | cython.cimports.av.video.plane.VideoPlane |
| `external-call::dep:cython.cimports.av.video.reformatter.VideoReformatter` | cython.cimports.av.video.reformatter.VideoReformatter |
| `external-call::dep:cython.cimports.cpython.PyBuffer_FillInfo` | cython.cimports.cpython.PyBuffer_FillInfo |
| `external-call::dep:cython.cimports.cpython.PyBytes_FromString` | cython.cimports.cpython.PyBytes_FromString |
| `external-call::dep:cython.cimports.cpython.buffer.PyBuffer_Release` | cython.cimports.cpython.buffer.PyBuffer_Release |
| `external-call::dep:cython.cimports.cpython.buffer.PyObject_CheckBuffer` | cython.cimports.cpython.buffer.PyObject_CheckBuffer |
| `external-call::dep:cython.cimports.cpython.buffer.PyObject_GetBuffer` | cython.cimports.cpython.buffer.PyObject_GetBuffer |
| `external-call::dep:cython.cimports.cpython.bytes.PyBytes_FromStringAndSize` | cython.cimports.cpython.bytes.PyBytes_FromStringAndSize |
| `external-call::dep:cython.cimports.cpython.exc.PyErr_Clear` | cython.cimports.cpython.exc.PyErr_Clear |
| `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_GetPointer` | cython.cimports.cpython.pycapsule.PyCapsule_GetPointer |
| `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_IsValid` | cython.cimports.cpython.pycapsule.PyCapsule_IsValid |
| `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_New` | cython.cimports.cpython.pycapsule.PyCapsule_New |
| `external-call::dep:cython.cimports.cpython.pycapsule.PyCapsule_SetName` | cython.cimports.cpython.pycapsule.PyCapsule_SetName |
| `external-call::dep:cython.cimports.cpython.ref.Py_DECREF` | cython.cimports.cpython.ref.Py_DECREF |
| `external-call::dep:cython.cimports.cpython.ref.Py_INCREF` | cython.cimports.cpython.ref.Py_INCREF |
| `external-call::dep:cython.cimports.libav` | cython.cimports.libav |
| `external-call::dep:cython.cimports.libc.stdlib.free` | cython.cimports.libc.stdlib.free |
| `external-call::dep:cython.cimports.libc.stdlib.malloc` | cython.cimports.libc.stdlib.malloc |
| `external-call::dep:cython.cimports.libc.string.memcpy` | cython.cimports.libc.string.memcpy |
| `external-call::dep:cython.cimports.libc.string.memset` | cython.cimports.libc.string.memset |
| `external-call::dep:cython.cimports.libc.string.strcmp` | cython.cimports.libc.string.strcmp |
| `external-call::dep:cython.operator.dereference` | cython.operator.dereference |
| `external-call::dep:cython.sizeof` | cython.sizeof |
| `external-call::stdlib:cython` | cython |

## Connected Communities

- **. +54 dirs** (17 cross-edges)
- **. +1 dirs · from_ndarray** (3 cross-edges)
- **site-packages/click +3 dirs · gettext.gettext** (2 cross-edges)
- **fastapi/_compat +8 dirs** (2 cross-edges)
- **. +5 dirs · invoke** (2 cross-edges)
- **. +12 dirs · load** (2 cross-edges)
- **site-packages/huggingface_hub +17 dirs** (2 cross-edges)
- **Lib/site-packages · __init__ · error** (1 cross-edges)
- **. +45 dirs** (1 cross-edges)
- **fsspec/implementations +1 dirs · _strip_protocol** (1 cross-edges)
- **site-packages/PIL +19 dirs** (1 cross-edges)
- **site-packages/PIL +13 dirs** (1 cross-edges)
- **. +2 dirs · AudioCodecContext** (1 cross-edges)
- **av/container** (1 cross-edges)
- **site-packages/filelock +11 dirs** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-3375")
explore(operation:"context", task:"understand . +8 dirs · cython", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
