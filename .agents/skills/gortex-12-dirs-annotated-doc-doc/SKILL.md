---
name: gortex-12-dirs-annotated-doc-doc
description: "Work in the . +12 dirs · annotated_doc.Doc area — 1927 symbols across 115 files (94% cohesion)"
---

# . +12 dirs · annotated_doc.Doc

1927 symbols | 115 files | 94% cohesion

## When to Use

Use this skill when working on files in:
- ``
- `.venv-build\Lib\site-packages\annotated_doc\main.py`
- `.venv-build\Lib\site-packages\cryptography\hazmat\asn1\asn1.py`
- `.venv-build\Lib\site-packages\fastapi\_compat\v2.py`
- `.venv-build\Lib\site-packages\fastapi\applications.py`
- `.venv-build\Lib\site-packages\fastapi\background.py`
- `.venv-build\Lib\site-packages\fastapi\datastructures.py`
- `.venv-build\Lib\site-packages\fastapi\dependencies\models.py`
- `.venv-build\Lib\site-packages\fastapi\dependencies\utils.py`
- `.venv-build\Lib\site-packages\fastapi\encoders.py`
- `.venv-build\Lib\site-packages\fastapi\exception_handlers.py`
- `.venv-build\Lib\site-packages\fastapi\exceptions.py`
- `.venv-build\Lib\site-packages\fastapi\openapi\docs.py`
- `.venv-build\Lib\site-packages\fastapi\openapi\models.py`
- `.venv-build\Lib\site-packages\fastapi\openapi\utils.py`
- `.venv-build\Lib\site-packages\fastapi\param_functions.py`
- `.venv-build\Lib\site-packages\fastapi\params.py`
- `.venv-build\Lib\site-packages\fastapi\routing.py`
- `.venv-build\Lib\site-packages\fastapi\security\api_key.py`
- `.venv-build\Lib\site-packages\fastapi\security\base.py`
- `.venv-build\Lib\site-packages\fastapi\security\http.py`
- `.venv-build\Lib\site-packages\fastapi\security\oauth2.py`
- `.venv-build\Lib\site-packages\fastapi\security\open_id_connect_url.py`
- `.venv-build\Lib\site-packages\fastapi\sse.py`
- `.venv-build\Lib\site-packages\fastapi\utils.py`
- `.venv-build\Lib\site-packages\huggingface_hub\_oauth.py`
- `.venv-build\Lib\site-packages\huggingface_hub\cli\_errors.py`
- `.venv-build\Lib\site-packages\huggingface_hub\cli\_framework.py`
- `.venv-build\Lib\site-packages\starlette\applications.py`
- `.venv-build\Lib\site-packages\starlette\background.py`
- `.venv-build\Lib\site-packages\starlette\middleware\authentication.py`
- `.venv-build\Lib\site-packages\starlette\middleware\errors.py`
- `.venv-build\Lib\site-packages\starlette\middleware\exceptions.py`
- `.venv-build\Lib\site-packages\starlette\requests.py`
- `.venv-build\Lib\site-packages\starlette\responses.py`
- `.venv-build\Lib\site-packages\starlette\routing.py`
- `.venv-build\Lib\site-packages\starlette\testclient.py`
- `external-call::dep:annotated_doc.Doc`
- `external-call::dep:authlib.integrations.starlette_client.OAuth`
- `external-call::dep:fastapi._compat.copy_field_info`
- `external-call::dep:fastapi._compat.create_body_model`
- `external-call::dep:fastapi._compat.field_annotation_is_scalar`
- `external-call::dep:fastapi._compat.field_annotation_is_scalar_sequence`
- `external-call::dep:fastapi._compat.get_definitions`
- `external-call::dep:fastapi._compat.get_flat_models_from_fields`
- `external-call::dep:fastapi._compat.get_model_name_map`
- `external-call::dep:fastapi._compat.get_schema_from_model_field`
- `external-call::dep:fastapi._compat.is_scalar_field`
- `external-call::dep:fastapi._compat.is_uploadfile_or_nonable_uploadfile_annotation`
- `external-call::dep:fastapi._compat.is_uploadfile_sequence_annotation`
- `external-call::dep:fastapi._compat.lenient_issubclass`
- `external-call::dep:fastapi.background.BackgroundTasks`
- `external-call::dep:fastapi.concurrency.asynccontextmanager`
- `external-call::dep:fastapi.concurrency.contextmanager_in_threadpool`
- `external-call::dep:fastapi.datastructures.Default`
- `external-call::dep:fastapi.dependencies.models.Dependant`
- `external-call::dep:fastapi.dependencies.models._get_cache_key`
- `external-call::dep:fastapi.dependencies.models._get_computed_scope`
- `external-call::dep:fastapi.dependencies.models._get_oauth_scopes`
- `external-call::dep:fastapi.dependencies.models._get_security_scheme`
- `external-call::dep:fastapi.dependencies.models._is_async_gen_callable`
- `external-call::dep:fastapi.dependencies.models._is_coroutine_callable`
- `external-call::dep:fastapi.dependencies.models._is_gen_callable`
- `external-call::dep:fastapi.dependencies.models._is_security_scheme`
- `external-call::dep:fastapi.dependencies.utils._get_body_field`
- `external-call::dep:fastapi.dependencies.utils._get_flat_body_params`
- `external-call::dep:fastapi.dependencies.utils._get_flat_fields_from_params`
- `external-call::dep:fastapi.dependencies.utils._should_embed_body_fields`
- `external-call::dep:fastapi.dependencies.utils.get_dependant`
- `external-call::dep:fastapi.dependencies.utils.get_parameterless_sub_dependant`
- `external-call::dep:fastapi.dependencies.utils.get_stream_item_type`
- `external-call::dep:fastapi.dependencies.utils.get_typed_return_annotation`
- `external-call::dep:fastapi.dependencies.utils.get_validation_alias`
- `external-call::dep:fastapi.dependencies.utils.solve_dependencies`
- `external-call::dep:fastapi.encoders.jsonable_encoder`
- `external-call::dep:fastapi.exceptions.DependencyScopeError`
- `external-call::dep:fastapi.exceptions.EndpointContext`
- `external-call::dep:fastapi.exceptions.HTTPException`
- `external-call::dep:fastapi.exceptions.RequestValidationError`
- `external-call::dep:fastapi.exceptions.ResponseValidationError`
- `external-call::dep:fastapi.exceptions.WebSocketRequestValidationError`
- `external-call::dep:fastapi.openapi.docs.get_redoc_html`
- `external-call::dep:fastapi.openapi.docs.get_swagger_ui_html`
- `external-call::dep:fastapi.openapi.docs.get_swagger_ui_oauth2_redirect_html`
- `external-call::dep:fastapi.openapi.models.HTTPBase`
- `external-call::dep:fastapi.openapi.models.HTTPBearer`
- `external-call::dep:fastapi.openapi.models.OAuth2`
- `external-call::dep:fastapi.openapi.models.OAuthFlows`
- `external-call::dep:fastapi.openapi.models.OpenAPI`
- `external-call::dep:fastapi.openapi.models.OpenIdConnect`
- `external-call::dep:fastapi.openapi.utils.get_openapi`
- `external-call::dep:fastapi.param_functions.Form`
- `external-call::dep:fastapi.params`
- `external-call::dep:fastapi.routing`
- `external-call::dep:fastapi.security.oauth2.SecurityScopes`
- `external-call::dep:fastapi.sse.format_sse_event`
- `external-call::dep:fastapi.utils.create_model_field`
- `external-call::dep:fastapi.utils.deep_dict_update`
- `external-call::dep:fastapi.utils.get_path_param_names`
- `external-call::dep:fastapi.utils.get_value_or_default`
- `external-call::dep:fastapi.utils.is_body_allowed_for_status_code`
- `external-call::dep:starlette._utils.AwaitableOrContextManagerWrapper`
- `external-call::dep:starlette._utils.is_async_callable`
- `external-call::dep:starlette.middleware.body_limit.RequestBodyLimitMiddleware`
- `external-call::dep:starlette.requests.Request`
- `external-call::dep:starlette.responses.HTMLResponse`
- `external-call::dep:starlette.responses.JSONResponse`
- `external-call::dep:starlette.responses.Response`
- `external-call::dep:starlette.responses.StreamingResponse`
- `external-call::dep:starlette.routing`
- `external-call::dep:starlette.routing.compile_path`
- `external-call::dep:starlette.routing.get_name`
- `external-call::dep:typing_extensions.deprecated`
- `external-call::dep:typing_inspection.typing_objects.is_typealiastype`
- `tools\obus_launcher\test_obus_launcher.py`

## Key Files

| File | Symbols |
|------|---------|
| `` | replace, getsourcefile, asynccontextmanager, format_exception, contextlib.contextmanager, ... |
| `.venv-build\Lib\site-packages\annotated_doc\main.py` | __init__, documentation, other, Doc, __repr__, ... |
| `.venv-build\Lib\site-packages\cryptography\hazmat\asn1\asn1.py` | Default |
| `.venv-build\Lib\site-packages\fastapi\_compat\v2.py` | known_models, get_flat_models_from_annotation, known_models, get_flat_models_from_field, annotation, ... |
| `.venv-build\Lib\site-packages\fastapi\applications.py` | operation_id, openapi, response_model_exclude_unset, docs_url, root_path, ... |
| `.venv-build\Lib\site-packages\fastapi\background.py` | args, func, BackgroundTasks, kwargs, add_task |
| `.venv-build\Lib\site-packages\fastapi\datastructures.py` | value, core_schema, Default, __init__, __eq__, ... |
| `.venv-build\Lib\site-packages\fastapi\dependencies\models.py` | Dependant |
| `.venv-build\Lib\site-packages\fastapi\dependencies\utils.py` | fields, _should_embed_body_fields, parent_oauth_scopes, solve_dependencies, param_name, ... |
| `.venv-build\Lib\site-packages\fastapi\encoders.py` | jsonable_encoder, obj, sqlalchemy_safe, by_alias, include, ... |
| `.venv-build\Lib\site-packages\fastapi\exception_handlers.py` | exc, websocket_request_validation_exception_handler, exc, http_exception_handler, request_validation_exception_handler, ... |
| `.venv-build\Lib\site-packages\fastapi\exceptions.py` | endpoint_ctx, endpoint_ctx, errors, code, detail, ... |
| `.venv-build\Lib\site-packages\fastapi\openapi\docs.py` | oauth2_redirect_url, swagger_favicon_url, swagger_js_url, openapi_url, get_swagger_ui_oauth2_redirect_html, ... |
| `.venv-build\Lib\site-packages\fastapi\openapi\models.py` | Example, APIKeyIn, Response |
| `.venv-build\Lib\site-packages\fastapi\openapi\utils.py` | body_field, separate_input_output_schemas, model_name_map, tags, _get_openapi_operation_parameters, ... |
| `.venv-build\Lib\site-packages\fastapi\param_functions.py` | allow_inf_nan, lt, description, max_digits, pattern, ... |
| `.venv-build\Lib\site-packages\fastapi\params.py` | multiple_of, discriminator, include_in_schema, examples, decimal_places, ... |
| `.venv-build\Lib\site-packages\fastapi\routing.py` | name, put, tags, response_model_include, response_class, ... |
| `.venv-build\Lib\site-packages\fastapi\security\api_key.py` | name, description, __init__, auto_error, name, ... |
| `.venv-build\Lib\site-packages\fastapi\security\base.py` | SecurityBase |
| `.venv-build\Lib\site-packages\fastapi\security\http.py` | description, __init__, HTTPBearer, make_not_authenticated_error, make_authenticate_headers, ... |
| `.venv-build\Lib\site-packages\fastapi\security\oauth2.py` | OAuth2, auto_error, request, scheme_name, scheme_name, ... |
| `.venv-build\Lib\site-packages\fastapi\security\open_id_connect_url.py` | OpenIdConnect, __call__, make_not_authenticated_error, description, auto_error, ... |
| `.venv-build\Lib\site-packages\fastapi\sse.py` | data_str, id, comment, event, _split_sse_lines, ... |
| `.venv-build\Lib\site-packages\fastapi\utils.py` | get_value_or_default, extra_items, first_item |
| `.venv-build\Lib\site-packages\huggingface_hub\_oauth.py` | _add_oauth_routes, app, _get_oauth_uris, _add_mocked_oauth_routes, app, ... |
| `.venv-build\Lib\site-packages\huggingface_hub\cli\_errors.py` | error, _format_cli_extension_install_error |
| `.venv-build\Lib\site-packages\huggingface_hub\cli\_framework.py` | kwargs, handler |
| `.venv-build\Lib\site-packages\starlette\applications.py` | routes |
| `.venv-build\Lib\site-packages\starlette\background.py` | func, __init__, kwargs, args |
| `.venv-build\Lib\site-packages\starlette\middleware\authentication.py` | backend, conn, __init__, exc, default_on_error, ... |
| `.venv-build\Lib\site-packages\starlette\middleware\errors.py` | error_response, exc, send, generate_plain_text, request, ... |
| `.venv-build\Lib\site-packages\starlette\middleware\exceptions.py` | request, exc, http_exception |
| `.venv-build\Lib\site-packages\starlette\requests.py` | empty_receive, max_part_size, json, Request, form, ... |
| `.venv-build\Lib\site-packages\starlette\responses.py` | HTMLResponse |
| `.venv-build\Lib\site-packages\starlette\routing.py` | name, app, path, Router, host, ... |
| `.venv-build\Lib\site-packages\starlette\testclient.py` | _is_asgi3, app |
| `external-call::dep:annotated_doc.Doc` | annotated_doc.Doc |
| `external-call::dep:authlib.integrations.starlette_client.OAuth` | authlib.integrations.starlette_client.OAuth |
| `external-call::dep:fastapi._compat.copy_field_info` | fastapi._compat.copy_field_info |
| `external-call::dep:fastapi._compat.create_body_model` | fastapi._compat.create_body_model |
| `external-call::dep:fastapi._compat.field_annotation_is_scalar` | fastapi._compat.field_annotation_is_scalar |
| `external-call::dep:fastapi._compat.field_annotation_is_scalar_sequence` | fastapi._compat.field_annotation_is_scalar_sequence |
| `external-call::dep:fastapi._compat.get_definitions` | fastapi._compat.get_definitions |
| `external-call::dep:fastapi._compat.get_flat_models_from_fields` | fastapi._compat.get_flat_models_from_fields |
| `external-call::dep:fastapi._compat.get_model_name_map` | fastapi._compat.get_model_name_map |
| `external-call::dep:fastapi._compat.get_schema_from_model_field` | fastapi._compat.get_schema_from_model_field |
| `external-call::dep:fastapi._compat.is_scalar_field` | fastapi._compat.is_scalar_field |
| `external-call::dep:fastapi._compat.is_uploadfile_or_nonable_uploadfile_annotation` | fastapi._compat.is_uploadfile_or_nonable_uploadfile_annotation |
| `external-call::dep:fastapi._compat.is_uploadfile_sequence_annotation` | fastapi._compat.is_uploadfile_sequence_annotation |
| `external-call::dep:fastapi._compat.lenient_issubclass` | fastapi._compat.lenient_issubclass |
| `external-call::dep:fastapi.background.BackgroundTasks` | fastapi.background.BackgroundTasks |
| `external-call::dep:fastapi.concurrency.asynccontextmanager` | fastapi.concurrency.asynccontextmanager |
| `external-call::dep:fastapi.concurrency.contextmanager_in_threadpool` | fastapi.concurrency.contextmanager_in_threadpool |
| `external-call::dep:fastapi.datastructures.Default` | fastapi.datastructures.Default |
| `external-call::dep:fastapi.dependencies.models.Dependant` | fastapi.dependencies.models.Dependant |
| `external-call::dep:fastapi.dependencies.models._get_cache_key` | fastapi.dependencies.models._get_cache_key |
| `external-call::dep:fastapi.dependencies.models._get_computed_scope` | fastapi.dependencies.models._get_computed_scope |
| `external-call::dep:fastapi.dependencies.models._get_oauth_scopes` | fastapi.dependencies.models._get_oauth_scopes |
| `external-call::dep:fastapi.dependencies.models._get_security_scheme` | fastapi.dependencies.models._get_security_scheme |
| `external-call::dep:fastapi.dependencies.models._is_async_gen_callable` | fastapi.dependencies.models._is_async_gen_callable |
| `external-call::dep:fastapi.dependencies.models._is_coroutine_callable` | fastapi.dependencies.models._is_coroutine_callable |
| `external-call::dep:fastapi.dependencies.models._is_gen_callable` | fastapi.dependencies.models._is_gen_callable |
| `external-call::dep:fastapi.dependencies.models._is_security_scheme` | fastapi.dependencies.models._is_security_scheme |
| `external-call::dep:fastapi.dependencies.utils._get_body_field` | fastapi.dependencies.utils._get_body_field |
| `external-call::dep:fastapi.dependencies.utils._get_flat_body_params` | fastapi.dependencies.utils._get_flat_body_params |
| `external-call::dep:fastapi.dependencies.utils._get_flat_fields_from_params` | fastapi.dependencies.utils._get_flat_fields_from_params |
| `external-call::dep:fastapi.dependencies.utils._should_embed_body_fields` | fastapi.dependencies.utils._should_embed_body_fields |
| `external-call::dep:fastapi.dependencies.utils.get_dependant` | fastapi.dependencies.utils.get_dependant |
| `external-call::dep:fastapi.dependencies.utils.get_parameterless_sub_dependant` | fastapi.dependencies.utils.get_parameterless_sub_dependant |
| `external-call::dep:fastapi.dependencies.utils.get_stream_item_type` | fastapi.dependencies.utils.get_stream_item_type |
| `external-call::dep:fastapi.dependencies.utils.get_typed_return_annotation` | fastapi.dependencies.utils.get_typed_return_annotation |
| `external-call::dep:fastapi.dependencies.utils.get_validation_alias` | fastapi.dependencies.utils.get_validation_alias |
| `external-call::dep:fastapi.dependencies.utils.solve_dependencies` | fastapi.dependencies.utils.solve_dependencies |
| `external-call::dep:fastapi.encoders.jsonable_encoder` | fastapi.encoders.jsonable_encoder |
| `external-call::dep:fastapi.exceptions.DependencyScopeError` | fastapi.exceptions.DependencyScopeError |
| `external-call::dep:fastapi.exceptions.EndpointContext` | fastapi.exceptions.EndpointContext |
| `external-call::dep:fastapi.exceptions.HTTPException` | fastapi.exceptions.HTTPException |
| `external-call::dep:fastapi.exceptions.RequestValidationError` | fastapi.exceptions.RequestValidationError |
| `external-call::dep:fastapi.exceptions.ResponseValidationError` | fastapi.exceptions.ResponseValidationError |
| `external-call::dep:fastapi.exceptions.WebSocketRequestValidationError` | fastapi.exceptions.WebSocketRequestValidationError |
| `external-call::dep:fastapi.openapi.docs.get_redoc_html` | fastapi.openapi.docs.get_redoc_html |
| `external-call::dep:fastapi.openapi.docs.get_swagger_ui_html` | fastapi.openapi.docs.get_swagger_ui_html |
| `external-call::dep:fastapi.openapi.docs.get_swagger_ui_oauth2_redirect_html` | fastapi.openapi.docs.get_swagger_ui_oauth2_redirect_html |
| `external-call::dep:fastapi.openapi.models.HTTPBase` | fastapi.openapi.models.HTTPBase |
| `external-call::dep:fastapi.openapi.models.HTTPBearer` | fastapi.openapi.models.HTTPBearer |
| `external-call::dep:fastapi.openapi.models.OAuth2` | fastapi.openapi.models.OAuth2 |
| `external-call::dep:fastapi.openapi.models.OAuthFlows` | fastapi.openapi.models.OAuthFlows |
| `external-call::dep:fastapi.openapi.models.OpenAPI` | fastapi.openapi.models.OpenAPI |
| `external-call::dep:fastapi.openapi.models.OpenIdConnect` | fastapi.openapi.models.OpenIdConnect |
| `external-call::dep:fastapi.openapi.utils.get_openapi` | fastapi.openapi.utils.get_openapi |
| `external-call::dep:fastapi.param_functions.Form` | fastapi.param_functions.Form |
| `external-call::dep:fastapi.params` | fastapi.params |
| `external-call::dep:fastapi.routing` | fastapi.routing |
| `external-call::dep:fastapi.security.oauth2.SecurityScopes` | fastapi.security.oauth2.SecurityScopes |
| `external-call::dep:fastapi.sse.format_sse_event` | fastapi.sse.format_sse_event |
| `external-call::dep:fastapi.utils.create_model_field` | fastapi.utils.create_model_field |
| `external-call::dep:fastapi.utils.deep_dict_update` | fastapi.utils.deep_dict_update |
| `external-call::dep:fastapi.utils.get_path_param_names` | fastapi.utils.get_path_param_names |
| `external-call::dep:fastapi.utils.get_value_or_default` | fastapi.utils.get_value_or_default |
| `external-call::dep:fastapi.utils.is_body_allowed_for_status_code` | fastapi.utils.is_body_allowed_for_status_code |
| `external-call::dep:starlette._utils.AwaitableOrContextManagerWrapper` | starlette._utils.AwaitableOrContextManagerWrapper |
| `external-call::dep:starlette._utils.is_async_callable` | starlette._utils.is_async_callable |
| `external-call::dep:starlette.middleware.body_limit.RequestBodyLimitMiddleware` | starlette.middleware.body_limit.RequestBodyLimitMiddleware |
| `external-call::dep:starlette.requests.Request` | starlette.requests.Request |
| `external-call::dep:starlette.responses.HTMLResponse` | starlette.responses.HTMLResponse |
| `external-call::dep:starlette.responses.JSONResponse` | starlette.responses.JSONResponse |
| `external-call::dep:starlette.responses.Response` | starlette.responses.Response |
| `external-call::dep:starlette.responses.StreamingResponse` | starlette.responses.StreamingResponse |
| `external-call::dep:starlette.routing` | starlette.routing |
| `external-call::dep:starlette.routing.compile_path` | starlette.routing.compile_path |
| `external-call::dep:starlette.routing.get_name` | starlette.routing.get_name |
| `external-call::dep:typing_extensions.deprecated` | typing_extensions.deprecated |
| `external-call::dep:typing_inspection.typing_objects.is_typealiastype` | typing_inspection.typing_objects.is_typealiastype |
| `tools\obus_launcher\test_obus_launcher.py` | urlopen, test_collect_readiness_uses_real_warmup_and_memory_routes |

## Connected Communities

- **. +31 dirs** (17 cross-edges)
- **. +47 dirs** (10 cross-edges)
- **. +45 dirs** (8 cross-edges)
- **. +4 dirs · get_response** (7 cross-edges)
- **. +7 dirs · send** (5 cross-edges)
- **fastapi/_compat +8 dirs** (5 cross-edges)
- **. +2 dirs · _is_coroutine_callable_cached** (5 cross-edges)
- **. +1 dirs · get_validation_alias** (5 cross-edges)
- **. +1 dirs · append · .** (5 cross-edges)
- **. +4 dirs · ModelField** (4 cross-edges)
- **starlette/middleware +5 dirs** (4 cross-edges)
- **site-packages/starlette +7 dirs** (3 cross-edges)
- **. +3 dirs · AsyncExitStack** (3 cross-edges)
- **. +2 dirs · fastapi.logger.logger** (2 cross-edges)
- **site-packages/setuptools +6 dirs** (2 cross-edges)
- **site-packages/starlette +1 dirs · get** (2 cross-edges)
- **. +19 dirs** (2 cross-edges)
- **. +5 dirs · _assert_func** (2 cross-edges)
- **site-packages/httpx +7 dirs** (2 cross-edges)
- **site-packages/starlette +1 dirs · setdefault** (1 cross-edges)
- **site-packages/click · get_current_context** (1 cross-edges)
- **_vendor/packaging +1 dirs · _get** (1 cross-edges)
- **. +1 dirs · parse · .** (1 cross-edges)
- **. +3 dirs · _extract_source_from_frame** (1 cross-edges)
- **site-packages/starlette +1 dirs · replace_params** (1 cross-edges)
- **. +4 dirs · cleandoc** (1 cross-edges)
- **numpy/f2py +2 dirs** (1 cross-edges)
- **_core/tests +8 dirs** (1 cross-edges)
- **. +3 dirs · app** (1 cross-edges)
- **tmp +12 dirs** (1 cross-edges)
- **. +1 dirs · get_typed_annotation** (1 cross-edges)
- **site-packages/huggingface_hub +17 dirs** (1 cross-edges)

## How to Explore

```
analyze(operation:"communities", id:"community-3152")
explore(operation:"context", task:"understand . +12 dirs · annotated_doc.Doc", format:"gcx")
```

_`format: "gcx"` returns the [GCX1 compact wire format](../../docs/wire-format.md) — round-trippable, ~27% fewer tokens than JSON. Drop it for JSON output; agents using `@gortex/wire` or the Go `github.com/gortexhq/gcx-go` package decode either._
