import logging
import os
import sys
import requests
import csv
import asyncio
import concurrent.futures
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction_status import UiPartiallyDecodedInstruction

# Setting up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meteora_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
RPC_URL = os.environ.get("RPC_URL")
HELIUS_API_KEY = os.environ.get("HELIUS_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")
if not RPC_URL:
    raise ValueError("RPC_URL environment variable is not set!")
if not HELIUS_API_KEY:
    raise ValueError("HELIUS_API_KEY environment variable is not set!")

# Constants
METEORA_PROGRAM_ID = Pubkey.from_string("LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo")
CNFT_CREATOR_ADDRESS = "BC11Rk2ZoLxb7tjSpycXDyHnyTdYeaYMgbMwimh8DThX"  # Address of the creator
CNFT_NAME_MATCH = "Meteora LP Army Certificate"  # Name to match for cNFT
BLACKLIST_FILE = "kelsier_addresses.csv"

# Load blacklist
def load_blacklist() -> set:
    """Load blacklisted addresses from CSV"""
    blacklist = set()
    try:
        if os.path.exists(BLACKLIST_FILE):
            with open(BLACKLIST_FILE, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    blacklist.add(row['address'].strip())
        else:
            logging.warning(f"Blacklist file {BLACKLIST_FILE} not found")
    except Exception as e:
        logging.error(f"Error loading blacklist: {str(e)}")
    return blacklist

# Global blacklist to avoid reloading for every request
BLACKLIST = load_blacklist()

# Task tracking for progress reporting
class TaskProgress:
    def __init__(self, task_name):
        self.task_name = task_name
        self.current = 0
        self.total = 0
        self.status = "idle"  # "idle", "running", "completed", "failed"
    
    def start(self, total=None):
        self.status = "running"
        if total is not None:
            self.total = total
    
    def update(self, current):
        self.current = current
    
    def complete(self):
        self.status = "completed"
        self.current = self.total
    
    def fail(self):
        self.status = "failed"
    
    @property
    def percent(self):
        if self.total <= 0:
            return 0
        return int((self.current / self.total) * 100)
    
    def __str__(self):
        if self.status == "idle":
            return f"{self.task_name}"
        elif self.status == "running" and self.total > 0:
            return f"{self.task_name} {self.current}/{self.total} ({self.percent}%)"
        elif self.status == "running":
            return f"{self.task_name} {self.current}"
        elif self.status == "completed":
            return f"{self.task_name} completed"
        else:
            return f"{self.task_name} failed"

class WalletProcessor:
    def __init__(self, wallet_address, update_callback=None):
        self.wallet_address = wallet_address
        self.update_callback = update_callback
        
        # Initialize tasks
        self.tasks = {
            "check_blacklist": TaskProgress("check_blacklist"),
            "check_cnft": TaskProgress("check_cnft"),
            "get_transactions": TaskProgress("get_transactions"),
            "filter_meteora_transactions": TaskProgress("filter_meteora_transactions"),
            "process_timestamps": TaskProgress("process_timestamps"),
            "calculate_activity_metrics": TaskProgress("calculate_activity_metrics"),
            "extract_pool_address": TaskProgress("extract_pool_address"),
            "get_pool_fees": TaskProgress("get_pool_fees")
        }
        
        # Result data
        self.result = {
            'wallet': wallet_address,
            'total_fees': 0.0,
            'pools_with_fees': 0,
            'first_tx': 'N/A',
            'active_weeks': 0,
            'active_months': 0,
            'cnft': False,
            'blacklist': False
        }
        
        # Processing data
        self.transactions = []
        self.meteora_transactions = []
        self.pool_addresses = []
    
    async def update_progress(self):
        """Send progress update if callback is available"""
        if self.update_callback:
            # Get all running tasks
            running_tasks = [task for task in self.tasks.values() 
                            if task.status == "running"]
            
            # Create status message
            message = ""
            if running_tasks:
                message = "Running:\n"
                for task in running_tasks:
                    # Only show percent for specific functions
                    if task.task_name in ["filter_meteora_transactions", "extract_pool_address", "get_pool_fees"]:
                        message += f"{task}\n"
            
            await self.update_callback(message)
    
    async def check_blacklist(self):
        """Check if wallet is blacklisted"""
        task = self.tasks["check_blacklist"]
        task.start()
        
        try:
            self.result['blacklist'] = self.wallet_address in BLACKLIST
            task.complete()
        except Exception as e:
            logging.error(f"Blacklist check error for {self.wallet_address}: {str(e)}")
            task.fail()
        
        await self.update_progress()
    
    async def check_cnft(self):
        """Check if wallet has a Meteora LP Army Certificate cNFT"""
        task = self.tasks["check_cnft"]
        task.start()
        
        try:
            url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": "1",
                "method": "getAssetsByOwner",
                "params": {
                    "ownerAddress": self.wallet_address,
                    "page": 1,
                    "limit": 1000
                }
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if there's valid result data
            if "result" not in data or "items" not in data.get("result", {}):
                logging.warning(f"Invalid response format from Helius API for wallet {self.wallet_address}")
                task.complete()
                await self.update_progress()
                return False
            
            # Iterate through all NFTs in the response
            for item in data["result"]["items"]:
                # Check for creator address
                has_creator = False
                if "creators" in item:
                    for creator in item["creators"]:
                        if creator.get("address") == CNFT_CREATOR_ADDRESS:
                            has_creator = True
                            break
                
                # Check for the NFT name
                nft_name = None
                if "content" in item and "metadata" in item["content"]:
                    nft_name = item["content"]["metadata"].get("name", "")
                
                # If both creator and name match, return True
                if has_creator and CNFT_NAME_MATCH in nft_name:
                    logging.info(f"Found Meteora LP Army Certificate cNFT in wallet {self.wallet_address}")
                    self.result['cnft'] = True
                    task.complete()
                    await self.update_progress()
                    return True
            
            # If we reach here, no matching NFT was found
            logging.info(f"No Meteora LP Army Certificate cNFT found in wallet {self.wallet_address}")
            task.complete()
            await self.update_progress()
            return False

        except Exception as e:
            logging.error(f"cNFT check error for wallet {self.wallet_address}: {str(e)}")
            task.fail()
            await self.update_progress()
            return False
    
    async def get_transactions(self):
        """Get all transactions with timestamps"""
        task = self.tasks["get_transactions"]
        task.start()
        
        try:
            client = Client(RPC_URL)
            wallet_pubkey = Pubkey.from_string(self.wallet_address)
            response = client.get_signatures_for_address(
                wallet_pubkey,
                limit=1000,
                commitment="confirmed"
            )
            
            self.transactions = [(sig.signature, sig.block_time) for sig in response.value if sig.block_time]
            task.update(len(self.transactions))
            task.complete()
        except Exception as e:
            logging.error(f"RPC connection failed for {self.wallet_address}: {str(e)}")
            task.fail()
        
        await self.update_progress()
    
    async def filter_meteora_transactions(self):
        """Filter Meteora transactions with timestamps"""
        task = self.tasks["filter_meteora_transactions"]
        task.start(len(self.transactions))
        
        client = Client(RPC_URL)
        self.meteora_transactions = []
        
        try:
            for index, (sig, timestamp) in enumerate(self.transactions, 1):
                try:
                    tx = client.get_transaction(sig, encoding="jsonParsed").value
                    if not tx:
                        continue

                    for instr in tx.transaction.transaction.message.instructions:
                        if isinstance(instr, UiPartiallyDecodedInstruction):
                            if instr.program_id == METEORA_PROGRAM_ID:
                                self.meteora_transactions.append((sig, timestamp))
                                break
                except Exception as e:
                    logging.error(f"Error processing transaction {sig}: {str(e)}")
                
                # Update progress
                task.update(index)
                if index % 5 == 0 or index == len(self.transactions):  # Update every 5 transactions or at the end
                    await self.update_progress()
            
            task.complete()
            await self.update_progress()
        except Exception as e:
            logging.error(f"Failed to filter transactions for {self.wallet_address}: {str(e)}")
            task.fail()
            await self.update_progress()
    
    async def process_timestamps(self):
        """Process transaction timestamps"""
        task = self.tasks["process_timestamps"]
        task.start()
        
        try:
            timestamps = [ts for _, ts in self.meteora_transactions]
            if timestamps:
                first_tx_ts = min(timestamps)
                self.result['first_tx'] = datetime.utcfromtimestamp(first_tx_ts).strftime('%d.%m.%Y')
            
            task.complete()
        except Exception as e:
            logging.error(f"Failed to process timestamps for {self.wallet_address}: {str(e)}")
            task.fail()
        
        await self.update_progress()
    
    async def calculate_activity_metrics(self):
        """Calculate active weeks and months"""
        task = self.tasks["calculate_activity_metrics"]
        task.start()
        
        try:
            timestamps = [ts for _, ts in self.meteora_transactions]
            
            weeks = set()
            months = set()

            for ts in timestamps:
                date = datetime.utcfromtimestamp(ts)
                year, week, _ = date.isocalendar()
                weeks.add((year, week))
                months.add((date.year, date.month))

            self.result['active_weeks'] = len(weeks)
            self.result['active_months'] = len(months)
            
            task.complete()
        except Exception as e:
            logging.error(f"Failed to calculate activity metrics for {self.wallet_address}: {str(e)}")
            task.fail()
        
        await self.update_progress()
    
    async def extract_pool_addresses(self):
        """Extract pool addresses from transactions"""
        task = self.tasks["extract_pool_address"]
        task.start(len(self.meteora_transactions))
        
        unique_pool_addresses = set()
        client = Client(RPC_URL)
        
        try:
            for index, (sig, _) in enumerate(self.meteora_transactions, 1):
                try:
                    tx = client.get_transaction(sig, encoding="jsonParsed").value

                    if not tx:
                        continue

                    for instr in tx.transaction.transaction.message.instructions:
                        if isinstance(instr, UiPartiallyDecodedInstruction):
                            if instr.program_id == METEORA_PROGRAM_ID:
                                try:
                                    pool_address = str(instr.accounts[2])
                                    unique_pool_addresses.add(pool_address)
                                except IndexError:
                                    continue
                except Exception as e:
                    logging.error(f"Failed to parse {sig}: {str(e)}")
                
                # Update progress
                task.update(index)
                if index % 5 == 0 or index == len(self.meteora_transactions):  # Update every 5 transactions or at the end
                    await self.update_progress()
            
            self.pool_addresses = list(unique_pool_addresses)
            task.complete()
            await self.update_progress()
        except Exception as e:
            logging.error(f"Failed to extract pool addresses for {self.wallet_address}: {str(e)}")
            task.fail()
            await self.update_progress()
    
    async def get_pool_fees(self):
        """Get fees in USD for all pools"""
        task = self.tasks["get_pool_fees"]
        task.start(len(self.pool_addresses))
        
        try:
            for index, pool in enumerate(self.pool_addresses, 1):
                try:
                    response = requests.get(
                        f"https://dlmm-api.meteora.ag/wallet/{self.wallet_address}/{pool}/earning",
                        timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    fees = float(data.get("total_fee_usd_claimed", 0.0))
                    self.result['total_fees'] += fees
                    if fees >= 0.01:
                        self.result['pools_with_fees'] += 1
                except Exception as e:
                    logging.error(f"Failed to get fees for {pool}: {str(e)}")
                
                # Update progress
                task.update(index)
                if index % 2 == 0 or index == len(self.pool_addresses):  # Update every 2 pools or at the end
                    await self.update_progress()
            
            task.complete()
            await self.update_progress()
        except Exception as e:
            logging.error(f"Failed to get pool fees for {self.wallet_address}: {str(e)}")
            task.fail()
            await self.update_progress()
    
    async def process(self):
        """Process wallet and return results"""
        logging.info(f"Processing wallet: {self.wallet_address}")
        
        # Process wallet in correct sequence
        await self.check_blacklist()
        await self.check_cnft()
        await self.get_transactions()
        await self.filter_meteora_transactions()
        await self.process_timestamps()
        await self.calculate_activity_metrics()
        await self.extract_pool_addresses()
        await self.get_pool_fees()
        
        return self.result


def format_wallet_result(wallet_number: int, data: dict) -> str:
    """Format wallet results as text"""
    return (
        f"{wallet_number} Wallet:\n"
        f"{data['wallet']}\n"
        f"💵 Total fees claimed: ${data['total_fees']:.2f}\n"
        f"🛀 Pools with claimed fees: {data['pools_with_fees']}\n"
        f"🗓 First tx: {data['first_tx']}\n"
        f"📅 Number of active weeks: {data['active_weeks']}\n"
        f"📅 Number of active months: {data['active_months']}\n"
        f"🖼 LP Army Certificate сNFT: {'Yes' if data['cnft'] else 'No'}\n"
        f"🚫 Blacklist kelsier_addresses: {'Yes' if data['blacklist'] else 'No'}"
    )


def generate_filename():
    """Generate unique CSV filename with timestamp and counter"""
    base_name = "Meteora"
    today = datetime.now().strftime("%Y%m%d")
    counter = 0
    while True:
        filename = f"{base_name}_{today}_{counter}.csv"
        if not os.path.exists(filename):
            return filename
        counter += 1


def write_csv_report(data: list, filename: str):
    """Write analysis results to CSV file"""
    fieldnames = [
        '№', 'Wallet', 'Fees$', 'Pools', 'First Tx Date',
        'Weeks', 'Months', 'Blacklist', 'сNFT'
    ]

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for index, row in enumerate(data, start=1):
                writer.writerow({
                    '№': index,
                    'Wallet': row['wallet'],
                    'Fees$': f"{round(row['total_fees'], 2):.2f}",
                    'Pools': row['pools_with_fees'],
                    'First Tx Date': row['first_tx'],
                    'Weeks': row['active_weeks'],
                    'Months': row['active_months'],
                    'Blacklist': 'Yes' if row['blacklist'] else 'No',
                    'сNFT': 'Yes' if row['cnft'] else 'No'
                })
        logging.info(f"CSV report saved as {filename}")
        return filename
    except Exception as e:
        logging.error(f"Failed to write CSV: {str(e)}")
        return None


# Tracking user tasks
user_tasks = {}  # {user_id: {"wallets": [...], "results": [...], "message_id": ...}}


# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    keyboard = [
        [InlineKeyboardButton("START", callback_data="start_analysis")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "What can this bot do? Check ALL your Meteora metrics!",
        reply_markup=reply_markup
    )


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the start button click."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        text="Send me wallets separated by spaces"
    )


async def handle_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle wallet addresses sent by user."""
    # Parse wallets from message
    text = update.message.text.strip()
    # Split by any number of spaces
    wallets = [wallet for wallet in text.split() if wallet]
    
    if not wallets:
        await update.message.reply_text("No valid wallet addresses found. Please try again.")
        return
    
    # Store wallets in context for later use
    context.user_data["wallets"] = wallets
    
    # Create buttons for output format selection
    keyboard = [
        [
            InlineKeyboardButton("Text", callback_data="format_text"),
            InlineKeyboardButton("CSV", callback_data="format_csv"),
            InlineKeyboardButton("Text + CSV", callback_data="format_all")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Found {len(wallets)} wallet(s). Please select output format:",
        reply_markup=reply_markup
    )


async def format_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle format selection."""
    query = update.callback_query
    await query.answer()
    
    selected_format = query.data.split("_")[1]  # format_text -> text
    wallets = context.user_data.get("wallets", [])
    user_id = update.effective_user.id
    
    if not wallets:
        await query.edit_message_text("No wallets found. Please start over.")
        return
    
    # Edit message to show processing status
    info_message = await query.edit_message_text(f"Processing {len(wallets)} wallet(s)... This may take some time.")
    
    # Create a progress message for detailed updates
    progress_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Processing 1/{len(wallets)} wallets.."
    )
    
    # Store task information for this user
    user_tasks[user_id] = {
        "wallets": wallets,
        "current_wallet_index": 0,
        "results": [],
        "format": selected_format,
        "info_message_id": info_message.message_id,
        "progress_message_id": progress_message.message_id,
        "chat_id": update.effective_chat.id
    }
    
    # Start processing in the background
    asyncio.create_task(process_wallets_for_user(user_id, context))


async def update_progress_message(user_id, wallet_index, total_wallets, details, context):
    """Update the progress message with wallet processing details"""
    user_task = user_tasks.get(user_id)
    if not user_task:
        return
    
    base_message = f"Processing {wallet_index + 1}/{total_wallets} wallets.."
    if details:
        message = f"{base_message}\n{details}"
    else:
        message = base_message
    
    try:
        await context.bot.edit_message_text(
            chat_id=user_task["chat_id"],
            message_id=user_task["progress_message_id"],
            text=message
        )
    except Exception as e:
        logging.error(f"Failed to update progress message: {str(e)}")


async def process_wallets_for_user(user_id, context):
    """Process all wallets for a specific user"""
    user_task = user_tasks.get(user_id)
    if not user_task:
        return
    
    wallets = user_task["wallets"]
    results = []
    
    # Process wallets concurrently
    for i, wallet in enumerate(wallets):
        user_task["current_wallet_index"] = i
        
        # Create a progress update callback for this wallet
        async def progress_callback(details):
            await update_progress_message(user_id, i, len(wallets), details, context)
        
        # Process this wallet
        processor = WalletProcessor(wallet, progress_callback)
        result = await processor.process()
        results.append(result)
    
    # Delete progress message when done
    try:
        await context.bot.delete_message(
            chat_id=user_task["chat_id"],
            message_id=user_task["progress_message_id"]
        )
    except Exception as e:
        logging.error(f"Failed to delete progress message: {str(e)}")
    
    # Generate outputs based on selected format
    selected_format = user_task["format"]
    
    if selected_format in ["text", "all"]:
        for i, data in enumerate(results, start=1):
            text_result = format_wallet_result(i, data)
            await context.bot.send_message(
                chat_id=user_task["chat_id"], 
                text=text_result
            )
    
    if selected_format in ["csv", "all"]:
        filename = generate_filename()
        csv_path = write_csv_report(results, filename)
        if csv_path:
            await context.bot.send_document(
                chat_id=user_task["chat_id"],
                document=open(filename, 'rb'),
                filename=filename
            )
    
    # Send completion message
    await context.bot.send_message(
        chat_id=user_task["chat_id"],
        text=f"Analysis complete for {len(wallets)} wallet(s)!"
    )
    
    # Clean up user task
    del user_tasks[user_id]


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "This bot analyzes Solana wallets for Meteora metrics.\n\n"
        "Commands:\n"
        "/start - Start using the bot\n"
        "/help - Show this help message\n\n"
        "To use the bot, click START and send wallet addresses separated by spaces."
    )


def main() -> None:
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(start_handler, pattern="^start_analysis$"))
    application.add_handler(CallbackQueryHandler(format_handler, pattern="^format_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallets))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
