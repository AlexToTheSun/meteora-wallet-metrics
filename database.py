import aiosqlite
import time

DB_FILE = "wallet_metrics.db"
TTL_SECONDS = 3600  # 1 hour

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            """CREATE TABLE IF NOT EXISTS wallet_metrics (
                wallet TEXT PRIMARY KEY,
                total_fees REAL,
                pools_with_fees INTEGER,
                first_tx TEXT,
                active_weeks INTEGER,
                active_months INTEGER,
                cnft INTEGER,
                blacklist INTEGER,
                updated_at INTEGER
            )"""
        )
        await db.commit()

async def get_wallet_metrics(wallet: str):
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute(
            "SELECT total_fees, pools_with_fees, first_tx, active_weeks, active_months, cnft, blacklist, updated_at FROM wallet_metrics WHERE wallet = ?",
            (wallet,)
        )
        row = await cursor.fetchone()
        await cursor.close()
    if row:
        total_fees, pools_with_fees, first_tx, active_weeks, active_months, cnft, blacklist, updated_at = row
        if updated_at >= int(time.time()) - TTL_SECONDS:
            return {
                "wallet": wallet,
                "total_fees": total_fees,
                "pools_with_fees": pools_with_fees,
                "first_tx": first_tx,
                "active_weeks": active_weeks,
                "active_months": active_months,
                "cnft": bool(cnft),
                "blacklist": bool(blacklist),
            }
    return None

async def store_wallet_metrics(wallet: str, data: dict):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "REPLACE INTO wallet_metrics (wallet, total_fees, pools_with_fees, first_tx, active_weeks, active_months, cnft, blacklist, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                wallet,
                data.get("total_fees", 0.0),
                data.get("pools_with_fees", 0),
                data.get("first_tx", "N/A"),
                data.get("active_weeks", 0),
                data.get("active_months", 0),
                int(data.get("cnft", False)),
                int(data.get("blacklist", False)),
                int(time.time()),
            ),
        )
        await db.commit()
