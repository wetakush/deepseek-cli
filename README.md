# Deepseek-CLI

Claude code with FREE Deepseek API
Powered by chat.deepseek.com 

Thx github.com/xtekky/deepseek4free for PoW bypass

by t.me/noxad

- `deepapi/` - anthropic-совместимый прокси для claude code
- `run_claude_deepseek.bat` - запускает локальное апи и claude code через это же api
- `deepapi.env.example.bat` - шаблон cfg

## что нужно

- windows
- установленный `python 3.11+`
- установленный `node`, он нужен для pow solver
- установленный `claude code`, команда `claude` должна быть доступна в `path`
- аккаунт на `chat.deepseek.com` и рабочий `bearer` токен + cookie

## запуск

1. скопируй `deepapi.env.example.bat` в `deepapi.env.bat`
2. впиши в `deepapi.env.bat` свои значения `DEEPSEEK_TOKEN` и `DEEPSEEK_COOKIE`
3. запусти `run_claude_deepseek.bat`
4. батник сам установит зависимости, поднимет локальный прокси и запустит claude code

## как работает новый чат

прокси хранит несколько deepseek-сессий и старается матчить их по истории сообщений

если хочешь явно создать новый deepseek chat, напиши в claude code одно из слов:

- `new`
- `/new`
- `new chat`
- `новый чат`
- `новый`
- `нью`
