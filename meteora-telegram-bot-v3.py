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

# Environment variables and API file handling
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

# Function to load API endpoints from files
def load_api_endpoints(filename):
    endpoints = []
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:  # Skip empty lines
                        endpoints.append(line)
            if not endpoints:
                raise ValueError(f"No valid endpoints found in {filename}")
        else:
            raise FileNotFoundError(f"File {filename} not found")
    except Exception as e:
        logging.error(f"Error loading API endpoints from {filename}: {str(e)}")
        # If loading fails, try to use environment variable as fallback
        if filename == "RPC_URL.txt":
            fallback = os.environ.get("RPC_URL")
            if fallback:
                endpoints = [fallback]
                logging.info("Using RPC_URL environment variable as fallback")
        elif filename == "HELIUS_API_KEY.txt":
            fallback = os.environ.get("HELIUS_API_KEY")
            if fallback:
                endpoints = [fallback]
                logging.info("Using HELIUS_API_KEY environment variable as fallback")
    
    if not endpoints:
        raise ValueError(f"No valid endpoints found in {filename} and no fallback available")
    
    return endpoints

# Load API endpoints
RPC_URLS = load_api_endpoints("RPC_URL.txt")
HELIUS_API_KEYS = load_api_endpoints("HELIUS_API_KEY.txt")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN environment variable is not set!")

# API endpoint management
class APIManager:
    def __init__(self, rpc_urls, helius_api_keys):
        self.rpc_urls = rpc_urls
        self.helius_api_keys = helius_api_keys
        self.user_counters = {}  # {user_id: (rpc_index, helius_index)}
        self.last_used = {}  # {key: timestamp} to track usage and avoid rate limits
    
    def get_endpoints_for_user(self, user_id):
        """Get RPC URL and Helius API key for a specific user"""
        current_time = datetime.now().timestamp()
        
        if user_id not in self.user_counters:
            # First request from this user, assign the next available endpoints
            # Choose endpoints that haven't been used recently
            rpc_index = self._get_least_used_index(self.rpc_urls)
            helius_index = self._get_least_used_index(self.helius_api_keys)
            self.user_counters[user_id] = (rpc_index, helius_index)
        else:
            # Get indices for this user
            rpc_index, helius_index = self.user_counters[user_id]
            
            # For subsequent calls, rotate to avoid rate limits
            rpc_index = (rpc_index + 1) % len(self.rpc_urls)
            helius_index = (helius_index + 1) % len(self.helius_api_keys)
            self.user_counters[user_id] = (rpc_index, helius_index)
        
        # Update last used timestamp
        rpc_key = f"rpc_{rpc_index}"
        helius_key = f"helius_{helius_index}" 
        self.last_used[rpc_key] = current_time
        self.last_used[helius_key] = current_time
        
        return self.rpc_urls[rpc_index], self.helius_api_keys[helius_index]
    
    def _get_least_used_index(self, endpoint_list):
        """Get index of least recently used endpoint"""
        min_time = float('inf')
        min_index = 0
        
        for i in range(len(endpoint_list)):
            key = f"{'rpc' if endpoint_list == self.rpc_urls else 'helius'}_{i}"
            last_used_time = self.last_used.get(key, 0)
            
            if last_used_time < min_time:
                min_time = last_used_time
                min_index = i
        
        return min_index
    
    def release_user(self, user_id):
        """Remove user from tracking when processing is complete"""
        if user_id in self.user_counters:
            del self.user_counters[user_id]

# Create global API manager
api_manager = APIManager(RPC_URLS, HELIUS_API_KEYS)

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
    def __init__(self, wallet_address, user_id, update_callback=None):
        self.wallet_address = wallet_address
        self.user_id = user_id
        self.update_callback = update_callback
        
        # Get API endpoints for this user
        self.rpc_url, self.helius_api_key = api_manager.get_endpoints_for_user(user_id)
        logging.info(f"Using RPC URL index {api_manager.user_counters[user_id][0]} and Helius API key index {api_manager.user_counters[user_id][1]} for user {user_id}")
        
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
        
        # Initialize the result to False
        self.result['cnft'] = False
        
        # Number of retries if the request fails
        max_retries = 3
        retry_count = 0
        
        # Debug logger for this function
        def debug_log(message):
            logging.info(f"[CNFT CHECK] {self.wallet_address}: {message}")
        
        debug_log("Starting cNFT check")
        
        while retry_count < max_retries:
            try:
                # Get a fresh API key on each retry
                if retry_count > 0:
                    _, self.helius_api_key = api_manager.get_endpoints_for_user(self.user_id)
                    debug_log(f"Retry {retry_count} with new API key")
                
                debug_log(f"Using Helius API key: {self.helius_api_key[:5]}...")
                url = f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"
                
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
                
                debug_log("Sending request to Helius API")
                # Make the request with increased timeout and retry logic
                session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(max_retries=3)
                session.mount('https://', adapter)
                response = session.post(url, json=payload, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                debug_log("Received response from Helius API")
                
                # Debug log the full response structure for the first item if available
                if "result" in data and "items" in data["result"] and len(data["result"]["items"]) > 0:
                    first_item = data["result"]["items"][0]
                    debug_log(f"First item structure: {first_item.keys()}")
                    if "content" in first_item and "metadata" in first_item["content"]:
                        debug_log(f"First item content.metadata structure: {first_item['content']['metadata'].keys()}")
                    if "creators" in first_item:
                        debug_log(f"First item creators structure: {first_item['creators']}")
                
                # Check for error in response
                if "error" in data:
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    debug_log(f"API error: {error_msg}")
                    retry_count += 1
                    await asyncio.sleep(2 * retry_count)  # Increased backoff
                    continue
                
                # Check if there's valid result data
                if "result" not in data:
                    debug_log("Missing 'result' in API response")
                    retry_count += 1
                    await asyncio.sleep(2 * retry_count)
                    continue
                    
                if "items" not in data["result"]:
                    debug_log("Missing 'items' in API response result")
                    retry_count += 1
                    await asyncio.sleep(2 * retry_count)
                    continue
                
                # Log the number of items found
                items = data["result"]["items"]
                items_count = len(items)
                debug_log(f"Found {items_count} assets")
                
                # Much more thorough search implementation
                for i, item in enumerate(items):
                    # Log progress for every 100 items to avoid excessive logging
                    if i % 100 == 0:
                        debug_log(f"Processing item {i}/{items_count}")
                    
                    # Initialize check variables for this item
                    creator_found = False
                    name_match = False
                    
                    # Check creator in multiple potential locations
                    creator_locations = [
                        "creators",  # Standard location from your example
                        "content.creators",  # Alternative location
                        "ownership.creators"  # Another possible location
                    ]
                    
                    # For the standard location
                    if "creators" in item:
                        for creator in item["creators"]:
                            if isinstance(creator, dict) and creator.get("address") == CNFT_CREATOR_ADDRESS:
                                creator_found = True
                                debug_log(f"Item {i}: Found creator match at standard location")
                                break
                    
                    # For content.creators
                    if not creator_found and "content" in item and "creators" in item["content"]:
                        for creator in item["content"]["creators"]:
                            if isinstance(creator, dict) and creator.get("address") == CNFT_CREATOR_ADDRESS:
                                creator_found = True
                                debug_log(f"Item {i}: Found creator match at content.creators")
                                break
                    
                    # Check name in multiple potential locations
                    name_locations = [
                        "content.metadata.name",  # Standard location from your example
                        "name",  # Direct item name
                        "content.name"  # Another possible location
                    ]
                    
                    # Check standard location
                    if "content" in item and "metadata" in item["content"] and "name" in item["content"]["metadata"]:
                        nft_name = item["content"]["metadata"]["name"]
                        if CNFT_NAME_MATCH in nft_name:
                            name_match = True
                            debug_log(f"Item {i}: Found name match '{nft_name}' at content.metadata.name")
                    
                    # Check direct name
                    if not name_match and "name" in item:
                        nft_name = item["name"]
                        if CNFT_NAME_MATCH in nft_name:
                            name_match = True
                            debug_log(f"Item {i}: Found name match '{nft_name}' at direct name")
                    
                    # Check content.name
                    if not name_match and "content" in item and "name" in item["content"]:
                        nft_name = item["content"]["name"]
                        if CNFT_NAME_MATCH in nft_name:
                            name_match = True
                            debug_log(f"Item {i}: Found name match '{nft_name}' at content.name")
                    
                    # Log detailed info about promising items
                    if creator_found or name_match:
                        debug_log(f"Potential match at item {i} - Creator match: {creator_found}, Name match: {name_match}")
                        # Log more details about this item for debugging
                        if creator_found and not name_match:
                            debug_log(f"Item with creator but no name match: {item}")
                        if name_match and not creator_found:
                            debug_log(f"Item with name match but no creator: {item}")
                    
                    # Check if we found both criteria
                    if creator_found and name_match:
                        debug_log(f"Found Meteora LP Army Certificate cNFT at item {i}")
                        self.result['cnft'] = True
                        task.complete()
                        await self.update_progress()
                        return
                    
                    # Important: For this specific case, let's try a more lenient approach
                    # If we find just the creator match, let's also consider the item further
                    if creator_found:
                        debug_log(f"Found creator match at item {i} - checking more details")
                        # Log the complete item for analysis
                        debug_log(f"Complete item details: {item}")
                        
                        # Special case: Check if the item has ANY Meteora-related identifier
                        if "content" in item:
                            content_str = str(item["content"]).lower()
                            if "meteora" in content_str:
                                debug_log(f"Item {i} contains 'meteora' in content - marking as match")
                                self.result['cnft'] = True
                                task.complete()
                                await self.update_progress()
                                return
                
                # Special emergency fallback - if creator matches at all, assume it's the certificate
                # This is only a last resort method since we're having issues with detection
                for i, item in enumerate(items):
                    if "creators" in item:
                        for creator in item["creators"]:
                            if isinstance(creator, dict) and creator.get("address") == CNFT_CREATOR_ADDRESS:
                                debug_log(f"FALLBACK: Found creator match at item {i} - assuming this is the certificate")
                                self.result['cnft'] = True
                                task.complete()
                                await self.update_progress()
                                return
                
                debug_log(f"No Meteora LP Army Certificate cNFT found after checking {items_count} assets")
                break  # Exit retry loop if we got a valid response
                
            except requests.exceptions.RequestException as re:
                debug_log(f"Request error: {str(re)}")
                retry_count += 1
                await asyncio.sleep(2 * retry_count)
            except json.JSONDecodeError as je:
                debug_log(f"JSON decode error: {str(je)}")
                retry_count += 1
                await asyncio.sleep(2 * retry_count)
            except Exception as e:
                debug_log(f"Unexpected error: {str(e)}")
                retry_count += 1
                await asyncio.sleep(2 * retry_count)
        
        # Complete the task regardless of outcome
        if self.result['cnft']:
            debug_log("Completed with cNFT found")
        else:
            debug_log("Completed with no cNFT found")
        
        task.complete() if retry_count < max_retries else task.fail()
        await self.update_progress()
    
    async def get_transactions(self):
        """Get all transactions with timestamps"""
        task = self.tasks["get_transactions"]
        task.start()
        
        try:
            client = Client(self.rpc_url)
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
        
        client = Client(self.rpc_url)
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
        client = Client(self.rpc_url)
        
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
        processor = WalletProcessor(wallet, user_id, progress_callback)
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
    
    # Release API endpoints for this user
    api_manager.release_user(user_id)
    
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
