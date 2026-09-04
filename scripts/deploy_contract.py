"""
deploy_contract.py
Compiles HashRegistry.sol with py-solc-x and deploys to Ethereum Sepolia testnet.
Saves the ABI to pipeline/contract_abi.json.

Usage:
    python scripts/deploy_contract.py
Then copy the printed CONTRACT_ADDRESS into your .env file.
"""

import os
import json
from pathlib import Path
from web3 import Web3
from dotenv import load_dotenv
from solcx import compile_standard, install_solc

load_dotenv()

RPC_URL     = os.getenv("SEPOLIA_RPC_URL")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
WALLET      = os.getenv("WALLET_ADDRESS")

SOLC_VERSION = "0.8.19"
CONTRACT_FILE = Path(__file__).parent.parent / "contracts" / "HashRegistry.sol"
ABI_OUT       = Path(__file__).parent.parent / "pipeline" / "contract_abi.json"


def main():
    print("[Deploy] Installing solc", SOLC_VERSION)
    install_solc(SOLC_VERSION)

    print("[Deploy] Compiling HashRegistry.sol ...")
    source = CONTRACT_FILE.read_text()
    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"HashRegistry.sol": {"content": source}},
            "settings": {
                "outputSelection": {
                    "*": {"*": ["abi", "evm.bytecode"]}
                }
            },
        },
        solc_version=SOLC_VERSION,
    )

    contract_data = compiled["contracts"]["HashRegistry.sol"]["HashRegistry"]
    abi      = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    # Save ABI for runtime use
    ABI_OUT.write_text(json.dumps(abi, indent=2))
    print(f"[Deploy] ABI saved to {ABI_OUT}")

    print("[Deploy] Connecting to Sepolia ...")
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError(f"Cannot connect to: {RPC_URL}")

    account = w3.eth.account.from_key(PRIVATE_KEY)
    bal     = w3.from_wei(w3.eth.get_balance(WALLET), "ether")
    print(f"[Deploy] Wallet: {WALLET}  Balance: {bal:.6f} SepoliaETH")

    Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = Contract.constructor().build_transaction({
        "from":     WALLET,
        "nonce":    w3.eth.get_transaction_count(WALLET),
        "gas":      1_000_000,
        "gasPrice": w3.eth.gas_price,
    })

    signed  = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[Deploy] Transaction sent: {tx_hash.hex()}")
    print("[Deploy] Waiting for confirmation ...")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    addr    = receipt.contractAddress

    print("\n" + "="*60)
    print(f"  CONTRACT DEPLOYED SUCCESSFULLY")
    print(f"  Address : {addr}")
    print(f"  Tx Hash : {receipt.transactionHash.hex()}")
    print(f"  Block   : {receipt.blockNumber}")
    print(f"  Etherscan: https://sepolia.etherscan.io/address/{addr}")
    print("="*60)
    print(f"\nAdd this to your .env file:")
    print(f"  CONTRACT_ADDRESS={addr}\n")


if __name__ == "__main__":
    main()
