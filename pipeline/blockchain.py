"""
blockchain.py
Handles all Ethereum Sepolia testnet interactions:
  - upload_hash()  : registers SHA-256 hash on-chain via HashRegistry contract
  - verify_hash()  : reads the on-chain record and confirms existence
"""

import os
import json
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv

load_dotenv()

RPC_URL = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET = os.getenv("WALLET_ADDRESS")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# Load ABI generated after contract deployment
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


def upload_hash(data_hash_hex: str, metadata: str) -> str:
    """
    Register a SHA-256 hash on Sepolia via the HashRegistry contract.
    Returns the transaction hash string.
    """
    w3 = _get_web3()
    contract = _get_contract(w3)
    account = w3.eth.account.from_key(PRIVATE_KEY)
    bytes32_hash = bytes.fromhex(data_hash_hex)

    tx = contract.functions.registerHash(bytes32_hash, metadata).build_transaction({
        "from": WALLET,
        "nonce": w3.eth.get_transaction_count(WALLET),
        "gas": 200_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    tx_hex = receipt.transactionHash.hex()
    print(f"[Blockchain] Tx confirmed in block {receipt.blockNumber}: {tx_hex}")
    return tx_hex


def verify_hash(data_hash_hex: str) -> dict:
    """
    Read the on-chain record for a given hash.
    Returns dict: {exists, uploader, timestamp, metadata}
    """
    w3 = _get_web3()
    contract = _get_contract(w3)
    bytes32_hash = bytes.fromhex(data_hash_hex)

    exists, uploader, timestamp, metadata = contract.functions.verifyHash(bytes32_hash).call()
    result = {
        "exists": exists,
        "uploader": uploader,
        "timestamp": timestamp,
        "metadata": metadata,
    }
    print(f"[Blockchain] Verification: exists={exists}, block_ts={timestamp}")
    return result
