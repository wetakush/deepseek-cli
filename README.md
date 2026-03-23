# Deepseek-CLI

Claude code with free Deepseek API
Powered by chat.deepseek.com

Thx github.com/xtekky/deepseek4free for PoW bypass

by t.me/noxad

- `deepapi/` - anthropic-совместимый прокси для claude code
- `run_claude_deepseek.bat` - запускает локальное api и claude code через это же api
- `deepapi.env.example.bat` - шаблон cfg

## attention
используйте аккаунты, которые вам не жалко потерять, возможна блокировка

## что нужно

- windows
- установленный `python 3.11+`
- установленный `node`, он нужен для pow solver
- установленный `claude code`, команда `claude` должна быть доступна в `path`
- аккаунт на `chat.deepseek.com` и рабочий `bearer` токен + cookie

## запуск

1. скопируй `deepapi.env.example.bat` в `deepapi.env.bat`
2. впиши в `deepapi.env.bat` свои `DEEPSEEK_TOKEN` и `DEEPSEEK_COOKIE`
3. запусти `run_claude_deepseek.bat`
4. батник спросит модель и thinking mode, потом поднимет прокси и стартанет `claude`

## доступные модели

- `deepseek-chat`
- `deepseek-reasoner`
- `deepseek-chat-search`
- `deepseek-reasoner-search`
- старый `deepseek-chat-web` тоже поддержан как legacy-конфиг

## важное про `/model`

- меню `/model` внутри `claude code` может по-прежнему показывать sonnet/opus/haiku, потому что это их локальный ui
- но батник запускает `claude` с `--model <выбранная_модель>`, так что реально уходит именно выбранный deepseek-профиль
- клиентские override для `thinking` и `search` по умолчанию выключены, чтобы `deepseek-chat` не улетал в think сам по себе

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
