# meteora-wallet-metrics ☄️

**Telegram Bot** shows **Meteora Wallet Metrics** that may be interesting to the **LP Army community**. There are 3 options for presenting analytics to choose from:
```bash
 Choose output format:
1. CSV file
2. Text report
3. Both formats
Enter your choice (1-3): # Enter the number

1 Wallet ☄:
9BY...NHR
💵 Total fees claimed: $135.71
🛀 Pools with claimed fees: 12
🗓 First tx: 22.12.2024
📅 Number of active weeks: 11
📅 Number of active months: 3
🖼 LP Army Certificate сNFT: Yes
🚫 Blacklist kelsier_addresses: No
```
## Overview
The bot has several significant improvements.
1. Enhanced Process Visualization
   - Added detailed progress tracking for all functions
   - Implemented percentage display specifically for several functions
   - The progress message updates in real-time and disappears when processing is complete
2. Improved Scalability for Multiple Users
   - Completely rewrote the wallet processing logic to handle concurrent requests
   - Each user's request now runs independently in the background using asyncio tasks (Multiple users can now process wallets simultaneously without blocking each other)
3. API Rotation System
   - Implemented files with Quicknode and Helius API
   - Assigns endpoints in a round-robin fashion
   - Tracks which API endpoints each user is using
   - Rotates through available endpoints when a user makes multiple requests

## Running
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Export your Telegram token and prepare RPC/Helius endpoint files.
3. Start the bot:
   ```bash
   python meteora-telegram-bot-v3.py
   ```

Wallet metrics are cached locally using SQLite (`wallet_metrics.db`).
You can swap this with an external database by modifying `database.py`
and running the database as a Docker service if required for higher load.


## To contact us
Discord: `alexturetskiy`

Telegram: https://t.me/AlexTuretskiy

Telegram channel: https://t.me/meteora_wallet_metrics

Twitter: https://twitter.com/Alex007hi
