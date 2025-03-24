import logging
import sys
import requests
import csv
import os
from datetime import datetime
from solana.rpc.api import Client
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.transaction_status import UiPartiallyDecodedInstruction

# Setting up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('meteora_analytics.log')]
)

RPC_URL = "$RPC_URL"
METEORA_PROGRAM_ID = Pubkey.from_string("LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo")
CNFT_MINT = "Cw4DD54N14aNNaRdhBCq7W9QQh8Bat812VuFbXbLC8bH"  # Changed to string
BLACKLIST_FILE = "kelsier_addresses.csv"


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


def check_cnft(wallet_address: str) -> bool:
    """Check cNFT ownership using Helius DAS API"""
    try:
        HELIUS_API_KEY = "$HELIUS_API_KEY"
        url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "get_assets_by_owner",
            "params": {
                "ownerAddress": wallet_address,
                "page": 1,
                "limit": 1000,
                "displayOptions": {
                    "showUnverifiedCollections": True
                }
            }
        }

        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()
        target_mint = "Cw4DD54N14aNNaRdhBCq7W9QQh8Bat812VuFbXbLC8bH"

        return any(
            item.get("id") == target_mint
            for item in data.get("result", {}).get("items", [])
        )

    except Exception as e:
        logging.error(f"cNFT check error: {str(e)}")
        return False


def get_transactions(wallet: Pubkey) -> list[tuple[Signature, int]]:
    """Get all transactions with timestamps"""
    try:
        client = Client(RPC_URL)
        response = client.get_signatures_for_address(
            wallet,
            limit=1000,
            commitment="confirmed"
        )
        return [(sig.signature, sig.block_time) for sig in response.value if sig.block_time]
    except Exception as e:
        logging.error(f"RPC connection failed: {str(e)}")
        return []


def filter_meteora_transactions(transactions: list[tuple[Signature, int]]) -> list[tuple[Signature, int]]:
    """Filter Meteora transactions with timestamps"""
    client = Client(RPC_URL)
    meteora_txs = []

    for sig, timestamp in transactions:
        try:
            tx = client.get_transaction(sig, encoding="jsonParsed").value
            if not tx:
                continue

            for instr in tx.transaction.transaction.message.instructions:
                if isinstance(instr, UiPartiallyDecodedInstruction):
                    if instr.program_id == METEORA_PROGRAM_ID:
                        meteora_txs.append((sig, timestamp))
                        break
        except Exception as e:
            logging.error(f"Error processing transaction {sig}: {str(e)}")

    return meteora_txs


def extract_pool_address(signature: Signature) -> str | None:
    """Extract pool address from transaction"""
    try:
        client = Client(RPC_URL)
        tx = client.get_transaction(signature, encoding="jsonParsed").value

        if not tx:
            return None

        for instr in tx.transaction.transaction.message.instructions:
            if isinstance(instr, UiPartiallyDecodedInstruction):
                if instr.program_id == METEORA_PROGRAM_ID:
                    try:
                        return str(instr.accounts[2])
                    except IndexError:
                        continue
        return None
    except Exception as e:
        logging.error(f"Failed to parse {signature}: {str(e)}")
        return None


def get_pool_fees(wallet: str, pool: str) -> float:
    """Get fees in USD for a pool"""
    try:
        response = requests.get(
            f"https://dlmm-api.meteora.ag/wallet/{wallet}/{pool}/earning",
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return float(data.get("total_fee_usd_claimed", 0.0))
    except Exception as e:
        logging.error(f"Failed to get fees for {pool}: {str(e)}")
        return 0.0


def calculate_activity_metrics(timestamps: list[int]) -> tuple[int, int]:
    """Calculate active weeks and months"""
    weeks = set()
    months = set()

    for ts in timestamps:
        date = datetime.utcfromtimestamp(ts)
        year, week, _ = date.isocalendar()
        weeks.add((year, week))
        months.add((date.year, date.month))

    return len(weeks), len(months)


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
    except Exception as e:
        logging.error(f"Failed to write CSV: {str(e)}")

def process_wallet(wallet_address: str, blacklist: set) -> dict:
    """Process single wallet and return results"""
    result = {
        'wallet': wallet_address,
        'total_fees': 0.0,
        'pools_with_fees': 0,
        'first_tx': 'N/A',
        'active_weeks': 0,
        'active_months': 0,
        'cnft': False,
        'blacklist': False
    }

    try:
        # Check blacklist
        result['blacklist'] = wallet_address in blacklist

        # Check cNFT
        result['cnft'] = check_cnft(wallet_address)  # Используем строковый адрес

        wallet_pubkey = Pubkey.from_string(wallet_address)

        # Get transactions data
        all_transactions = get_transactions(wallet_pubkey)
        meteora_transactions = filter_meteora_transactions(all_transactions)


        # Process timestamps
        timestamps = [ts for _, ts in meteora_transactions]
        if timestamps:
            first_tx_ts = min(timestamps)
            result['first_tx'] = datetime.utcfromtimestamp(first_tx_ts).strftime('%d.%m.%Y')

        # Calculate activity metrics
        result['active_weeks'], result['active_months'] = calculate_activity_metrics(timestamps)

        # Process pools and fees
        pool_addresses = list(set(
            address for sig, _ in meteora_transactions
            if (address := extract_pool_address(sig)) is not None
        ))

        for pool in pool_addresses:
            fees = get_pool_fees(wallet_address, pool)
            result['total_fees'] += fees
            if fees >= 0.01:
                result['pools_with_fees'] += 1

    except Exception as e:
        logging.critical(f"Critical failure for {wallet_address}: {str(e)}")

    return result


def print_wallet_result(wallet_number: int, data: dict):
    """Print formatted wallet results to console"""
    print(f"{wallet_number} Wallet:")
    print(data['wallet'])
    print(f"💵 Total fees claimed: ${data['total_fees']:.2f}")
    print(f"🛀 Pools with claimed fees: {data['pools_with_fees']}")
    print(f"🗓 First tx: {data['first_tx']}")
    print(f"📅 Number of active weeks: {data['active_weeks']}")
    print(f"📅 Number of active months: {data['active_months']}")
    print(f"🖼 LP Army Certificate сNFT: {'Yes' if data['cnft'] else 'No'}")
    print(f"🚫 Blacklist kelsier_addresses: {'Yes' if data['blacklist'] else 'No'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 script.py <wallet_address1> [<wallet_address2> ...]")
        sys.exit(1)

    # Load blacklist once
    blacklist = load_blacklist()

    addresses = sys.argv[1:]

    # Request output format
    print("Choose output format:")
    print("1. CSV file")
    print("2. Text report")
    print("3. Both formats")
    choice = input("Enter your choice (1-3): ").strip()

    if choice not in ['1', '2', '3']:
        print("Invalid choice. Exiting.")
        sys.exit(1)

    results = []

    # Processing wallets
    for addr in addresses:
        results.append(process_wallet(addr, blacklist))

    # Output of text report
    if choice in ['2', '3']:
        for i, data in enumerate(results, start=1):
            print_wallet_result(i, data)
            if i < len(results):
                print()

    # Generate CSV
    if choice in ['1', '3']:
        csv_filename = generate_filename()
        write_csv_report(results, csv_filename)
        print(f"\nCSV report generated: {csv_filename}")
