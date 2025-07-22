# meteora-wallet-metrics

Script shows Meteora wallet metrics that may be interesting to the LP Army community. There are 3 options for presenting analytics to choose from:
```bash
 Choose output format:
1. CSV file
2. Text report
3. Both formats
Enter your choice (1-3): # Enter the number

1 Wallet:
9BY...NHR
💵 Total fees claimed: $135.71
🛀 Pools with claimed fees: 12
🗓 First tx: 22.12.2024
📅 Number of active weeks: 11
📅 Number of active months: 3
🖼 LP Army Certificate сNFT: Yes
🚫 Blacklist kelsier_addresses: No

CSV report generated: Meteora_20250325_0.csv
# CSV file will be generated in the script folder.
```
## Overview
In this tutorial
- [What can this script do?](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main#what-can-this-script-do)
- [1) Create Quicknode and Helius keys](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#1-create-quicknode-and-helius-keys)
- [2) Installation](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#2-installation)
- [Auto install script if you use Ubuntu](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#auto-install-script-if-you-use-ubuntu)
- [To contact us](https://github.com/AlexToTheSun/meteora-wallet-metrics/blob/main/README.md#to-contact-us)

### What can this script do?
- You can check several wallets at once. Enter them separated by a space.

## Installation from docker

## Step 1: Install Docker

```bash
# Update package index
apt update

# Install required packages
apt install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
apt update

# Install Docker Engine
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Start and enable Docker service
systemctl start docker
systemctl enable docker

# Verify Docker installation
docker --version
docker run hello-world
```

## Step 2: Create Project Directory and Download Files

```bash
# Create project directory
mkdir -p /opt/meteora-telegram-bot
cd /opt/meteora-telegram-bot

# Download the bot script
wget https://raw.githubusercontent.com/AlexToTheSun/meteora-wallet-metrics/refs/heads/telegram-bot-v2/meteora.py

# Download requirements.txt
wget https://raw.githubusercontent.com/AlexToTheSun/meteora-wallet-metrics/refs/heads/telegram-bot-v2/requirements.txt

# Verify files are downloaded
ls -la
```
###  Create files: RPC_URL.txt with rpc from [Quicknode](https://dashboard.quicknode.com/) and HELIUS_API_KEY.txt with api from [Helius](https://dashboard.helius.dev/) .
First you need to create these keys and type it to HELIUS_API_KEY.txt and RPC_URL.txt each on a new line.
1) On https://dashboard.quicknode.com/
You should get http provider link.           
Example: `https://horse-yellow-lemon.solana-mainnet.quiknode.pro/23jk589df7g98sdf443k5j2o23h489df79g92834/`

2) On https://dashboard.helius.dev/
On Helius you should get Apy Key ID.           
Example: `87cv87sd-2h59-0v0c-2389-90cvb987987g`

```
nano RPC_URL.txt
#...
nano HELIUS_API_KEY.txt
#...
```
## Step 3: Create Dockerfile

Create a file named `Dockerfile` in your project directory:

```bash
cat > Dockerfile << 'EOF'
# Use Python 3.10 slim image (matches your tested environment)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the bot script
COPY meteora.py .

# Copy API configuration files (критично для ротации!)
COPY HELIUS_API_KEY.txt .
COPY RPC_URL.txt .

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash botuser
RUN chown -R botuser:botuser /app
USER botuser

# Command to run the bot
CMD ["python", "meteora.py"]
EOF
```

## Step 4: Create Docker Compose File (Optional but Recommended)

```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  meteora-bot:
    build: .
    container_name: meteora-telegram-bot
    restart: unless-stopped
    environment:
      # Только Telegram Bot Token нужен как переменная окружения
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      # RPC и API читаются из файлов внутри контейнера
    volumes:
      # Монтируем файлы API для возможности обновления без пересборки
      - ./HELIUS_API_KEY.txt:/app/HELIUS_API_KEY.txt:ro
      - ./RPC_URL.txt:/app/RPC_URL.txt:ro
      # Optional: Mount logs directory if your bot creates logs
      - ./logs:/app/logs
    networks:
      - meteora-network

networks:
  meteora-network:
    driver: bridge
EOF
```

## Step 5: Create Environment File
HERE you should type your bot' token instead of `<your_bot_token>`.
```bash
cat > .env << 'EOF'
# Только Telegram Bot Token
TELEGRAM_BOT_TOKEN=<your_bot_token>
EOF
```

## Step 6: Build and Run the Docker Image
### Using Docker Compose (METHOD 1)

```bash
# Build the image
docker compose build

# Run the bot
docker compose up -d

# Check logs
docker compose logs -f meteora-bot

# Stop the bot
docker compose down
```
### Using Docker Commands Directly (METHOD 2)

```bash
# Build the image
docker build -t meteora-telegram-bot .

# Run the container
docker run -d \
  --name meteora-telegram-bot \
  --restart unless-stopped \
  -e TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here" \
  meteora-telegram-bot

# Check logs
docker logs -f meteora-telegram-bot

# Stop the container
docker stop meteora-telegram-bot
docker rm meteora-telegram-bot
```

## To contact us
Discord: `alexturetskiy`

Telegram: https://t.me/AlexTuretskiy

Telegram channel: https://t.me/meteora_wallet_metrics

Twitter: https://twitter.com/Alex007hi
