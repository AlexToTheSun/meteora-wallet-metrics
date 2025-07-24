# Meteora Telegram Bot

Telegram бот для анализа кошельков Meteora с поддержкой PostgreSQL базы данных для масштабируемости и надежности.


## Требования

- Docker и Docker Compose
- Telegram Bot Token
- Helius API ключи
- RPC URLs (QuickNode или другие)

## Установка

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/AlexToTheSun/meteora-wallet-metrics.git
cd meteora-wallet-metrics
git checkout telegram-bot-v2
```

### 2. Создайте файлы конфигурации

#### RPC_URL.txt
```bash
nano RPC_URL.txt
# Добавьте ваши RPC URLs, каждый на новой строке
# Пример:
# https://example-rpc-1.solana-mainnet.quiknode.pro/123456/
# https://example-rpc-2.solana-mainnet.quiknode.pro/789012/
```

#### HELIUS_API_KEY.txt
```bash
nano HELIUS_API_KEY.txt
# Добавьте ваши Helius API ключи, каждый на новой строке
# Пример:
# 87cv87sd-2h59-0v0c-2389-90cvb987987g
# 12ab34cd-5e67-8f90-1234-56789abcdef0
```

#### .env файл
```bash
nano .env
# Добавьте ваш Telegram Bot Token
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### 3. Запуск с Docker Compose

```bash
# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f meteora-bot

# Остановка
docker-compose down

# Остановка с удалением данных
docker-compose down -v
```

## Структура проекта

```
meteora-wallet-metrics/
├── docker-compose.yml    # Конфигурация Docker Compose с PostgreSQL
├── Dockerfile           # Образ для бота
├── meteora.py          # Основной код бота
├── requirements.txt    # Python зависимости
├── HELIUS_API_KEY.txt # API ключи Helius
├── RPC_URL.txt        # RPC URLs
├── .env              # Переменные окружения
└── logs/            # Директория для логов
```



## База данных

PostgreSQL база данных включает:
- Таблица `blacklist` - черный список адресов
- Таблица `api_usage` - отслеживание использования API
- Таблица `processing_tasks` - состояние обработки задач

## Мониторинг

### Просмотр логов бота
```bash
docker-compose logs -f meteora-bot
```

### Подключение к базе данных
```bash
docker-compose exec postgres psql -U meteora -d meteora_bot
```

### Полезные SQL запросы
```sql
-- Проверка черного списка
SELECT COUNT(*) FROM blacklist;

-- Просмотр использования API
SELECT user_id, api_type, COUNT(*) as usage_count 
FROM api_usage 
GROUP BY user_id, api_type;

-- Очистка старых записей
DELETE FROM api_usage WHERE used_at < NOW() - INTERVAL '7 days';
```

## Обновление

```bash
# Остановка текущей версии
docker-compose down

# Получение обновлений
git pull

# Пересборка и запуск
docker-compose up -d --build
```

## Поддержка

Discord: alexturetskiy
Telegram: https://t.me/AlexTuretskiy
Telegram channel: https://t.me/meteora_wallet_metrics
Twitter: https://twitter.com/Alex007hi


