# Deepseek-CLI

Claude code with free Deepseek API
Powered by chat.deepseek.com

Thx github.com/xtekky/deepseek4free for PoW bypass

- `deepapi/` - anthropic-совместимый прокси для claude code
- `run_claude_deepseek.bat` - запускает локальное api и claude code через это же api
- `run_claude_deepseek.sh` - linux/mac launcher для того же сценария
- `deepapi.env.example.bat` - шаблон cfg
- `deepapi.env.example.sh` - shell-шаблон cfg

## attention
используйте аккаунты, которые вам не жалко потерять, возможна блокировка

## что нужно

- windows
- установленный `python 3.11+`
- установленный `node`, он нужен для pow solver
- установленный `claude code`, команда `claude` должна быть доступна в `path`
- аккаунт на `chat.deepseek.com` и рабочий `bearer` токен + cookie

для linux/mac:

- `python 3.11+`
- `node`
- `claude`
- `curl`

## запуск

1. скопируй `deepapi.env.example.bat` в `deepapi.env.bat`
2. впиши в `deepapi.env.bat` свои `DEEPSEEK_TOKEN` и `DEEPSEEK_COOKIE`
3. запусти `run_claude_deepseek.bat`
4. батник спросит модель и thinking mode, потом поднимет прокси и стартанет `claude`

linux/mac:

1. скопируй `deepapi.env.example.sh` в `deepapi.env.sh`
2. впиши свои `DEEPSEEK_TOKEN` и `DEEPSEEK_COOKIE`
3. сделай `chmod +x run_claude_deepseek.sh`
4. запусти `./run_claude_deepseek.sh`

## доступные модели

- `deepseek-v4`
- `deepseek-v4-reasoner`
- `deepseek-v4-search`
- `deepseek-v4-reasoner-search`
- 
## важное про `/model`

- меню `/model` внутри `claude code` может по-прежнему показывать sonnet/opus/haiku, потому что это их локальный ui
- но батник запускает `claude` с `--model <выбранная_модель>`, так что реально уходит именно выбранный deepseek-профиль
## новый чат

прокси хранит несколько deepseek-сессий и матчится по истории сообщений

если хочешь явно создать новый deepseek chat, напиши в claude code одно из слов:

- `new`
- `/new`
- `new chat`
- `новый чат`
- `новый`
- `нью`

## bug reports
если словил баг или есть предложение по улучшению - пиши в https://github.com/wetakush/deepseek-cli/issues
