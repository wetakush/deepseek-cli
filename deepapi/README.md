# deepapi

локальный anthropic-совместимый прокси для `claude code`, который ходит в `chat.deepseek.com`

что умеет:

- принимает `post /v1/messages`, `post /v1/messages/count_tokens`, `get /v1/models`
- отдает список deepseek-моделей, а не только один дефолтный id
- понимает обычные текстовые ответы и `tool_use`
- сам создает `chat_session`
- сам запрашивает `create_pow_challenge`
- сам собирает `x-ds-pow-response`
- стримит текст чанками без схлопывания пробелов и переносов
- для кодовых задач сильнее толкает модель в реальные tool-вызовы и файловые изменения
- держит registry из нескольких deepseek-сессий и матчится по общему префиксу истории
- создает новый deepseek chat только когда последний юзерский текст это `new`, `/new`, `new chat`, `новый чат`, `новый` или `нью`

доступные модели:

- `deepseek-chat`
- `deepseek-reasoner`
- `deepseek-chat-search`
- `deepseek-reasoner-search`
- если в конфиге остался старый `deepseek-chat-web`, он тоже продолжит работать как legacy-модель

как работает выбор thinking/search:

- выбор модели идет через `model` из запроса, либо через `DEEPAPI_MODEL` по умолчанию
- батник спрашивает модель и отдельно спрашивает thinking mode перед запуском `claude`
- по умолчанию клиентские override для `thinking` и `search` выключены, чтобы выбранная модель вела себя предсказуемо
- при желании это можно включить через `DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE=true` и `DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE=true`
- если `claude code` продолжает слать антропиковские id вроде `opus` или `sonnet`, прокси замапит их на близкие deepseek-профили

ограничения:

- для pow нужен установленный `node`, потому что solver использует wasm
- список моделей в меню `/model` самого `claude code` может оставаться антропиковским, это их локальный ui, но батник теперь стартует `claude` с `--model <выбранная_модель>`

настройка через переменные окружения:

```powershell
$env:DEEPSEEK_TOKEN = "bearer-or-raw-token"
$env:DEEPSEEK_COOKIE = "optional_cookie_string"
$env:DEEPAPI_API_KEY = "deepapi-local"
$env:DEEPAPI_HOST = "127.0.0.1"
$env:DEEPAPI_PORT = "8080"
$env:DEEPAPI_MODEL = "deepseek-reasoner"
$env:DEEPAPI_THINKING_ENABLED = "true"
$env:DEEPAPI_SEARCH_ENABLED = "false"
$env:DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE = "false"
$env:DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE = "false"
$env:DEEPAPI_STREAM_CHUNK_SIZE = "96"
```

запуск:

```powershell
python -m deepapi
```

для `claude code`:

```powershell
$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:8080"
$env:ANTHROPIC_AUTH_TOKEN = "deepapi-local"
```

после этого можно выбирать модели из `/v1/models` или оставлять дефолт через `DEEPAPI_MODEL`
