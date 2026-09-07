"""
blockchain.py
Handles all Ethereum Sepolia testnet interactions.
When a hash is already registered, fetches the original tx hash from
Etherscan so the UI can always show a clickable transaction link.
"""

import os
import json
import time
import requests
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL          = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY      = os.getenv("PRIVATE_KEY")
WALLET           = os.getenv("WALLET_ADDRESS")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

ABI_PATH = Path(__file__).parent / "contract_abi.json"


def _get_web3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to Sepolia RPC: {RPC_URL}")
    return w3


def _get_contract(w3):
    if not ABI_PATH.exists():
        raise FileNotFoundError(
            "pipeline/contract_abi.json not found. Run: python scripts/deploy_contract.py"
        )
    with open(ABI_PATH) as f:
        abi = json.load(f)
    return w3.eth.contract(
        address=Web3.to_checksum_address(CONTRACT_ADDRESS),
        abi=abi,
    )


def _find_original_tx(data_hash_hex: str) -> str | None:
    """
    Scans the contract's transaction list on Etherscan to find
    the tx whose calldata contains our SHA-256 hash.
    Returns a valid 66-char tx hash (0x + 64 hex chars) or None.
    """
    try:
        url = "https://api-sepolia.etherscan.io/api"
        params = {
            "module":     "account",
            "action":     "txlist",
            "address":    CONTRACT_ADDRESS,
            "startblock": "0",
            "endblock":   "latest",
            "sort":       "asc",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == "1" and data.get("result"):
            target = data_hash_hex.lower()
            for tx in data["result"]:
                inp = tx.get("input", "").lower()
                if target in inp:
                    tx_hash = tx.get("hash", "")
                    # Validate: must be 0x + 64 hex chars = 66 chars total
                    if len(tx_hash) == 66 and tx_hash.startswith("0x"):
                        print(f"[Blockchain] Found original tx: {tx_hash}")
                        return tx_hash

    except Exception as e:
        print(f"[Blockchain] Could not fetch original tx from Etherscan: {e}")

    return None


def upload_hash(data_hash_hex: str, metadata: str) -> dict:
    """
    Register a SHA-256 hash on Sepolia via the HashRegistry contract.
    Returns dict: { status, tx_hash, record }
    """
    w3       = _get_web3()
    contract = _get_contract(w3)
    account  = w3.eth.account.from_key(PRIVATE_KEY)
    b32      = bytes.fromhex(data_hash_hex)

    # ── Check if already registered ───────────────────────────
    existing = verify_hash(data_hash_hex)
    if existing["exists"]:
        print(f"[Blockchain] Hash already registered at ts={existing['timestamp']} — skipping tx.")
        original_tx = _find_original_tx(data_hash_hex)
        return {
            "status":  "already_registered",
            "tx_hash": original_tx,
            "record":  existing,
        }

    # ── Register ──────────────────────────────────────────────
    try:
        # Estimate gas, add 50% buffer to be safe
        try:
            estimated = contract.functions.registerHash(b32, metadata).estimate_gas({"from": WALLET})
            gas_limit = int(estimated * 1.5)
            print(f"[Blockchain] Estimated gas: {estimated}, using: {gas_limit}")
        except Exception:
            gas_limit = 500_000
            print(f"[Blockchain] Gas estimation failed, using default: {gas_limit}")

        tx = contract.functions.registerHash(b32, metadata).build_transaction({
            "from":     WALLET,
            "nonce":    w3.eth.get_transaction_count(WALLET),
            "gas":      gas_limit,
            "gasPrice": w3.eth.gas_price,
        })
        signed  = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        print(f"[Blockchain] Tx sent: {tx_hash.hex()} — waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
        tx_hex  = receipt.transactionHash.hex()
        print(f"[Blockchain] Confirmed in block {receipt.blockNumber}: {tx_hex}")

        # Wait for state propagation then verify
        record = None
        for attempt in range(5):
            time.sleep(3)
            record = verify_hash(data_hash_hex)
            if record["exists"]:
                print(f"[Blockchain] Verified on attempt {attempt + 1}.")
                break
            print(f"[Blockchain] Verify attempt {attempt + 1} — retrying...")

        if not record or not record["exists"]:
            print("[Blockchain] Warning: tx confirmed but verifyHash still returning false.")
            record = {
                "exists":    True,
                "uploader":  WALLET,
                "timestamp": int(time.time()),
                "metadata":  metadata,
            }

        return {
            "status":  "registered",
            "tx_hash": tx_hex,
            "record":  record,
        }

    except Exception as exc:
        if "already registered" in str(exc).lower():
            print("[Blockchain] Race condition — hash registered by another process.")
            record      = verify_hash(data_hash_hex)
            original_tx = _find_original_tx(data_hash_hex)
            return {
                "status":  "already_registered",
                "tx_hash": original_tx,
                "record":  record,
            }
        raise


def verify_hash(data_hash_hex: str) -> dict:
    """Read the on-chain record for a given hash."""
    w3       = _get_web3()
    contract = _get_contract(w3)
    b32      = bytes.fromhex(data_hash_hex)

    exists, uploader, timestamp, metadata = contract.functions.verifyHash(b32).call()
    result = {
        "exists":    exists,
        "uploader":  uploader,
        "timestamp": timestamp,
        "metadata":  metadata,
    }
    print(f"[Blockchain] Verification: exists={exists}, ts={timestamp}")
    return result
