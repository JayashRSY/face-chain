# FaceChain

> **Face scan → Web discovery → Blockchain verification**

FaceChain is an end-to-end pipeline that takes a face photo as input, finds matching content across the web using reverse image search, and seals the discovered post as a tamper-evident record on the Ethereum blockchain. It ships with a full web UI that shows live step-by-step progress as the pipeline runs.

Built for **HH Goa 2026 — Task 3: Face Identification & Blockchain Verification.**

---

## Table of Contents

1. [How it works](#how-it-works)
2. [Pipeline diagram](#pipeline-diagram)
3. [Tech stack](#tech-stack)
4. [Project structure](#project-structure)
5. [Prerequisites](#prerequisites)
6. [API keys — what you need & cost](#api-keys)
7. [Installation](#installation)
8. [Environment setup](#environment-setup)
9. [Deploy the smart contract](#deploy-the-smart-contract)
10. [Running the web UI](#running-the-web-ui)
11. [Running the CLI](#running-the-cli)
12. [API endpoints](#api-endpoints)
13. [Smart contract reference](#smart-contract-reference)
14. [How verification works](#how-verification-works)
15. [Known limitations](#known-limitations)
16. [Troubleshooting](#troubleshooting)

---

## How it works

FaceChain chains five operations together, each feeding the next:

1. **Face Detection** — dlib detects the face in your uploaded photo and produces a 128-dimension encoding vector that confirms a face was found.
2. **Reverse Image Search** — the photo is hosted on imgbb (free), then passed to Serper.dev's Google Lens API which returns visually matching pages from across the web.
3. **Post Scraping** — the best match URL is scraped for its Open Graph metadata: title, description, preview image, and site name.
4. **SHA-256 Fingerprint** — the scraped metadata is serialised to canonical JSON and hashed with SHA-256, producing a 32-byte deterministic fingerprint of the discovery.
5. **Blockchain Registration** — the hash is written to a Solidity `HashRegistry` contract on Ethereum Sepolia testnet via `web3.py`. Anyone can re-hash the same post data and call `verifyHash()` to prove the record is authentic and untampered.

---

## Pipeline diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        FaceChain                            │
│                                                             │
│   Input Image (face photo)                                  │
│          │                                                  │
│   [1] Face Detection & Encoding                             │
│          │   face_recognition (dlib HOG model)              │
│          │   → 128-dim encoding vector                      │
│          │                                                  │
│   [2] Image Upload + Reverse Image Search                   │
│          │   imgbb  →  public URL                           │
│          │   Serper.dev Google Lens  →  visual matches      │
│          │                                                  │
│   [3] Social Media Filter + Post Scraping                   │
│          │   BeautifulSoup  →  OG title, desc, image, URL   │
│          │                                                  │
│   [4] SHA-256 Fingerprint                                   │
│          │   hashlib  →  64-char hex digest                 │
│          │                                                  │
│   [5] Blockchain Upload + Verification                      │
│          │   web3.py  →  Sepolia HashRegistry contract      │
│          │   registerHash(bytes32, string)                  │
│          │   verifyHash(bytes32)  →  confirmed ✓            │
│          │                                                  │
│   Output: Etherscan link, tx hash, on-chain timestamp       │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Tool | Purpose |
|---|---|---|
| Face detection | `face_recognition` 1.3 (dlib) | Detect faces, produce 128-dim encoding |
| Image hosting | imgbb API | Host uploaded photo to get a public URL |
| Reverse image search | Serper.dev Google Lens | Find visually matching web pages |
| Post scraping | `requests` + `beautifulsoup4` | Extract Open Graph metadata from match URL |
| Fingerprinting | Python `hashlib` SHA-256 | Deterministic hash of post data |
| Blockchain | Ethereum Sepolia + `web3.py` | Store and verify hash on-chain |
| Smart contract | Solidity 0.8.19 | `HashRegistry` — immutable hash registry |
| Contract compile | `py-solc-x` | Compile Solidity from Python |
| Web server | Flask 3 | Serve UI + SSE pipeline streaming |
| Frontend | Vanilla JS + CSS | Drag-drop upload, live progress, results |

---

## Project structure

```
face-chain/
│
├── app.py                      # Flask server — UI + SSE streaming endpoints
├── main.py                     # CLI runner (no UI, terminal output)
│
├── pipeline/
│   ├── __init__.py
│   ├── face_encoder.py         # Step 1 — dlib face detection & encoding
│   ├── web_searcher.py         # Step 2 — imgbb upload + Serper reverse image search
│   ├── post_scraper.py         # Step 3 — Open Graph metadata scraper
│   ├── hasher.py               # Step 4 — SHA-256 canonical hasher
│   ├── blockchain.py           # Step 5 — web3.py Sepolia interactions
│   └── contract_abi.json       # Auto-generated after: python scripts/deploy_contract.py
│
├── contracts/
│   └── HashRegistry.sol        # Solidity 0.8.19 smart contract
│
├── scripts/
│   └── deploy_contract.py      # One-time deploy + ABI export
│
├── ui/
│   ├── templates/
│   │   └── index.html          # Single-page UI
│   └── static/
│       ├── css/main.css        # Dark theme styles
│       └── js/app.js           # Drag-drop, SSE listener, results renderer
│
├── sample_images/              # Put test face photos here
├── uploads/                    # Temp store for uploaded images (auto-created)
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Prerequisites

- **Python 3.10 or later**
- **pip** (comes with Python)
- **MetaMask** (or any Ethereum wallet) — needed to sign transactions
- **Sepolia ETH** — free testnet gas (see API keys section)
- **Homebrew** (macOS only) — needed for cmake/dlib

---

## API keys

All services used are free. No credit card is required for any of them.

### Serper.dev — Google Lens reverse image search

- Sign up at https://serper.dev
- Free tier: **2,500 searches on signup**, no monthly expiry
- The pipeline uses exactly 1 search per run

### imgbb — Image hosting

- Sign up at https://api.imgbb.com
- Free tier: **unlimited uploads**, max 32 MB per image
- No monthly limit, no credit card

### Infura — Sepolia RPC endpoint

- Sign up at https://app.infura.io
- Free tier: **100,000 requests/day** on Sepolia
- Go to Dashboard → Create New API Key → copy the Sepolia HTTPS URL
- Alternative: https://dashboard.alchemy.com (also free)

### Sepolia ETH — testnet gas

- Sepolia ETH has no real monetary value
- Claim free ETH from any of these faucets:
  - https://sepoliafaucet.com — 0.5 ETH/day
  - https://faucet.sepolia.dev — 0.05 ETH/request
  - https://www.alchemy.com/faucets/ethereum-sepolia — 0.1 ETH/day
- You only need a small amount. Deploying the contract costs ~0.002 ETH. Each `registerHash` transaction costs ~0.0001 ETH.

### MetaMask — wallet

- Download at https://metamask.io (free browser extension)
- Create a wallet, switch to Sepolia network, export your private key from Account Details

| Service | Free tier | Sign-up URL |
|---|---|---|
| Serper.dev | 2,500 searches | https://serper.dev |
| imgbb | Unlimited uploads | https://api.imgbb.com |
| Infura | 100k req/day | https://app.infura.io |
| Sepolia faucet | ~0.5 ETH/day | https://sepoliafaucet.com |
| MetaMask | Free | https://metamask.io |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/face-chain.git
cd face-chain

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### macOS — dlib note

`face_recognition` depends on `dlib` which requires cmake. If the install fails:

```bash
brew install cmake
pip install dlib
pip install face-recognition
```

### Windows — dlib note

On Windows, install the pre-built dlib wheel:

```bash
pip install dlib-bin
pip install face-recognition
```

---

## Environment setup

```bash
cp .env.example .env
```

Open `.env` and fill in all six values:

```bash
# Serper.dev — reverse image search
SERPER_API_KEY=your_serper_api_key_here

# imgbb — image hosting
IMGBB_API_KEY=your_imgbb_api_key_here

# Infura or Alchemy — Sepolia RPC
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID

# MetaMask private key (NEVER commit this)
PRIVATE_KEY=your_wallet_private_key_here

# Your wallet public address
WALLET_ADDRESS=0xYourWalletAddressHere

# Filled in after deploy_contract.py
CONTRACT_ADDRESS=0xDeployedContractAddressHere
```

> **Security:** `.env` is listed in `.gitignore`. Never commit it. Never share your `PRIVATE_KEY`.

---

## Deploy the smart contract

This is a one-time step. It compiles `HashRegistry.sol`, deploys it to Sepolia, and saves the ABI to `pipeline/contract_abi.json`.

```bash
python scripts/deploy_contract.py
```

Expected output:

```
[Deploy] Installing solc 0.8.19
[Deploy] Compiling HashRegistry.sol ...
[Deploy] ABI saved to pipeline/contract_abi.json
[Deploy] Connecting to Sepolia ...
[Deploy] Wallet: 0xYour...  Balance: 0.482100 SepoliaETH
[Deploy] Transaction sent: 0xabc123...
[Deploy] Waiting for confirmation ...

============================================================
  CONTRACT DEPLOYED SUCCESSFULLY
  Address : 0xDeployedContractAddress
  Tx Hash : 0xabc123...
  Block   : 7123456
  Etherscan: https://sepolia.etherscan.io/address/0xDeployed...
============================================================

Add this to your .env file:
  CONTRACT_ADDRESS=0xDeployedContractAddress
```

Copy the `CONTRACT_ADDRESS` value into your `.env` file. You never need to deploy again unless you want a fresh contract.

---

## Running the web UI

```bash
python app.py
```

Then open **http://localhost:5050** in your browser.

### UI walkthrough

1. **Drag and drop** a face photo (JPG, PNG, or WebP, max 16 MB) onto the upload zone, or click **Browse file**.
2. A preview of the image appears. Click **Run Pipeline**.
3. The five pipeline steps light up in real time as they complete:
   - Step 1 turns yellow (running) then green (done) with the encoding shape
   - Step 2 shows how many visual matches were found
   - Step 3 shows the scraped post title
   - Step 4 shows the SHA-256 hash
   - Step 5 confirms blockchain registration with the Etherscan link
4. A **Results card** appears at the bottom showing:
   - The discovered post with thumbnail, title, description, and a direct link
   - The full SHA-256 fingerprint
   - The on-chain record: transaction hash, Etherscan link, registration timestamp, and uploader address
5. Use **Standalone Verification** at the bottom of the page to paste any 64-char hash and verify it against the chain independently.

---

## Running the CLI

If you prefer the terminal without the UI:

```bash
python main.py sample_images/your_face.jpg
```

Example output:

```
══════════════════════════════════════════════════════════════
  FACECHAIN  |  Face  →  Web  →  Blockchain
══════════════════════════════════════════════════════════════

[1/5] Detecting face ...
      Encoding shape : (128,)  ✓

[2/5] Running reverse image search (Google Lens via Serper) ...
      Chosen URL : https://instagram.com/p/abc123

[3/5] Scraping post metadata ...
      Title: John Doe — Tech Speaker at Web3 Summit

[4/5] Hashing post data (SHA-256) ...
      a3f9c27d8e1b...

[5/5] Uploading hash to Ethereum Sepolia testnet ...
      Tx confirmed in block 7123456: 0xabc...

      Verifying hash on-chain ...

══════════════════════════════════════════════════════════════
  PIPELINE COMPLETE
══════════════════════════════════════════════════════════════
  Input image      : sample_images/your_face.jpg
  Post found       : https://instagram.com/p/abc123
  Post title       : John Doe — Tech Speaker at Web3 Summit
  SHA-256 hash     : a3f9c27d8e1b...
  Tx hash          : 0xabc123...
  On-chain verified: True
  Registered by    : 0xYourWalletAddress
  Timestamp (unix) : 1725484800
  Etherscan        : https://sepolia.etherscan.io/tx/0xabc123...
══════════════════════════════════════════════════════════════
```

---

## API endpoints

The Flask server exposes three endpoints:

### `GET /`
Serves the web UI.

### `POST /upload`
Accepts a face image, starts the pipeline in a background thread, returns a job ID.

**Request:** `multipart/form-data` with field `image` (JPG / PNG / WebP, max 16 MB)

**Response:**
```json
{ "job_id": "abc123def456..." }
```

### `GET /stream/<job_id>`
Server-Sent Events stream. Connect with `EventSource` to receive live pipeline progress.

Each event is a JSON object:
```json
{
  "step": 3,
  "status": "done",
  "message": "Post metadata extracted",
  "data": { "post": { "url": "...", "title": "...", ... } },
  "ts": 1725484800.123
}
```

`status` is one of: `"running"` `"done"` `"error"`

The final event is `{ "__done__": true }` which signals the stream is closed.

### `POST /verify`
Verifies any SHA-256 hash against the Sepolia chain.

**Request:**
```json
{ "hash": "64characterhexstring..." }
```

**Response (found):**
```json
{
  "exists": true,
  "uploader": "0xYourWalletAddress",
  "timestamp": 1725484800,
  "metadata": "FaceChain|https://instagram.com/p/abc123"
}
```

**Response (not found):**
```json
{ "exists": false, "uploader": "0x000...", "timestamp": 0, "metadata": "" }
```

---

## Smart contract reference

**File:** `contracts/HashRegistry.sol`
**Solidity:** 0.8.19
**Network:** Ethereum Sepolia Testnet (Chain ID: 11155111)

### Functions

#### `registerHash(bytes32 dataHash, string calldata metadata)`
Registers a SHA-256 hash on-chain. Reverts if the hash has already been registered (first-write-wins).

- `dataHash` — 32-byte SHA-256 of the canonical post JSON
- `metadata` — human-readable label, typically the post URL (max 200 chars recommended)

Emits `HashRegistered(bytes32 indexed dataHash, address indexed uploader, uint256 timestamp, string metadata)`.

#### `verifyHash(bytes32 dataHash) → (bool exists, address uploader, uint256 timestamp, string metadata)`
Read-only. Returns the on-chain record for any hash. Returns `exists = false` if the hash has never been registered.

### How the hash is computed

```python
import json, hashlib

canonical = {
    "url":         post_data["url"],
    "title":       post_data["title"],
    "description": post_data["description"],
    "og_image":    post_data["og_image"],
}
serialized = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
```

The keys are always sorted and the encoding is always UTF-8, so the same post data always produces the same hash regardless of where the code runs.

---

## How verification works

1. FaceChain scrapes a post and serialises its canonical fields (url, title, description, og_image) to JSON.
2. SHA-256 of that JSON string is computed — this is the fingerprint.
3. The fingerprint is stored on-chain via `registerHash()` alongside the post URL and the registrant's wallet address.
4. To verify later: scrape the same post again, compute the same hash, call `verifyHash()` on the contract.
5. If `exists == true` and the timestamp matches, the record is authentic. Because the Ethereum blockchain is immutable, nobody can alter or delete the record after it is written.

This proves two things:
- The post existed at the time of registration (blockchain timestamp).
- The post content has not changed since registration (hash mismatch would indicate tampering).

---

## Known limitations

- **Face quality** — `face_recognition` works best on clear, forward-facing, well-lit photos. Blurry, angled, or very small faces may not be detected.
- **Serper free tier** — 2,500 searches on signup. The pipeline uses 1 per run, so this is enough for hundreds of demos.
- **Social media login walls** — Instagram, TikTok, and X (Twitter) block full page scraping for logged-out users. The pipeline still extracts whatever Open Graph tags are publicly visible and registers that. The hash will simply reflect the partial metadata.
- **Block confirmation time** — Sepolia transactions take approximately 12 seconds to confirm. This is normal testnet behaviour.
- **This project does not identify who a person is.** It finds visually similar images on the web for a given face photo. The match quality depends entirely on whether that face appears in publicly indexed pages.
- **In-memory job store** — the Flask server stores pipeline jobs in a Python dict. Restarting the server clears all job history. This is fine for demo purposes; a production version would use Redis or a database.
- **Single uploader address** — all hashes are registered from the same wallet. In a production system each user would sign their own transaction.

---

## Troubleshooting

### `No face detected in: ...`
The face detection model could not find a face in the image. Try a clearer, front-facing photo with good lighting. The face should be at least ~80×80 pixels in the image.

### `pip install face-recognition` fails
On macOS, run `brew install cmake` first. On Windows, use `pip install dlib-bin` instead of `dlib`.

### `Cannot connect to Sepolia RPC`
Check that `SEPOLIA_RPC_URL` in `.env` is correct and your Infura/Alchemy project is active. Try opening the URL in your browser — it should return a JSON response.

### `pipeline/contract_abi.json not found`
You need to deploy the contract first. Run `python scripts/deploy_contract.py` and copy the printed `CONTRACT_ADDRESS` into your `.env`.

### `Hash already registered` (contract revert)
You are trying to register the same post twice. This is intentional — the contract is first-write-wins. Use a different face image or a different post to generate a new hash.

### Sepolia transaction stuck / pending
Your wallet may be out of Sepolia ETH. Claim more from https://sepoliafaucet.com. Check your balance at https://sepolia.etherscan.io/address/YOUR_WALLET_ADDRESS.

### UI shows no results after Step 5
Open the browser developer console (F12) and check for errors. Ensure `CONTRACT_ADDRESS` in `.env` matches the deployed contract and that `pipeline/contract_abi.json` exists.
