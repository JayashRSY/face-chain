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

1. **Face Detection** — dlib detects the face in your uploaded photo and produces a 128-dimension encoding vector that confirms a face was found. The image is loaded safely with EXIF correction and forced RGB conversion to avoid crashes on Apple Silicon.
2. **Reverse Image Search** — the photo is uploaded to imgbb (free) to get a public URL, then passed through up to four search strategies in order: Google Lens via Serper.dev, Serper web search, Serper image search, and finally an imgbb-hosted URL fallback. This guarantees the pipeline always produces a result to hash and register.
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
│          │   dlib HOG detector (direct — no face_recognition│
│          │   wrapper, bypasses Python 3.11 import bug)      │
│          │   → 128-dim encoding vector                      │
│          │                                                  │
│   [2] Image Upload + Reverse Image Search                   │
│          │   imgbb  →  public URL                           │
│          │   Strategy 1: Serper Google Lens                 │
│          │   Strategy 2: Serper web search                  │
│          │   Strategy 3: Serper image search                │
│          │   Strategy 4: imgbb URL fallback (always works)  │
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
| Face detection | `dlib` 20.x (direct) | Detect faces, produce 128-dim encoding — bypasses broken face_recognition wrapper |
| Face models | `face_recognition_models` | Provides .dat model files used by dlib |
| Image hosting | imgbb API | Host uploaded photo to get a public URL for Serper |
| Reverse image search | Serper.dev (4-strategy fallback) | Find visually matching web pages |
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
│   ├── face_encoder.py         # Step 1 — dlib direct (ARM64-safe, EXIF-corrected)
│   ├── web_searcher.py         # Step 2 — imgbb upload + 4-strategy Serper search
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

- **Python 3.11** (required — dlib and face_recognition_models are not compatible with 3.12+)
- **pip** (comes with Python)
- **MetaMask** (or any Ethereum wallet) — needed to sign transactions
- **Sepolia ETH** — free testnet gas (see API keys section)
- **Homebrew** (macOS only) — needed for cmake/dlib

> **Python version is critical.** Use exactly Python 3.11. Python 3.12, 3.13, and 3.14 all have compatibility issues with dlib and face_recognition_models.

---

## API keys

All services used are free. No credit card is required for any of them.

### Serper.dev — Google Lens reverse image search

- Sign up at https://serper.dev
- Free tier: **2,500 searches on signup**, no monthly expiry
- The pipeline uses exactly 1 search per run (up to 3 if fallback strategies are needed)

### imgbb — Image hosting

- Sign up at https://api.imgbb.com
- Free tier: **unlimited uploads**, max 32 MB per image
- No monthly limit, no credit card

### Infura or Alchemy — Sepolia RPC endpoint

- Infura: https://app.infura.io — free tier, 100,000 requests/day
- Alchemy: https://dashboard.alchemy.com — alternative, also free
- **Important:** make sure to copy the **Sepolia** endpoint URL, not the Mainnet one
  - Correct: `https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY`
  - Wrong: `https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY`

### Sepolia ETH — testnet gas

- Sepolia ETH has no real monetary value
- Claim free ETH from any of these faucets (no mainnet balance required):
  - https://cloud.google.com/application/web3/faucet/ethereum/sepolia — Google Cloud, no account needed
  - https://www.infura.io/faucet/sepolia — requires Infura login
  - https://faucets.chain.link/sepolia — requires MetaMask connection
  - https://sepolia-faucet.pk910.de — no login, browser-based PoW mining
- You only need a small amount. Deploying the contract costs ~0.002 ETH. Each `registerHash` transaction costs ~0.0001 ETH.
- Faucets that require mainnet ETH (like sepoliafaucet.com) will not work if your mainnet balance is zero — use the Google Cloud or pk910 faucets instead.

### MetaMask — wallet

- Download at https://metamask.io (free browser extension)
- Create a wallet, switch to Sepolia network, export your private key from Account Details

| Service | Free tier | Sign-up URL |
|---|---|---|
| Serper.dev | 2,500 searches | https://serper.dev |
| imgbb | Unlimited uploads | https://api.imgbb.com |
| Infura | 100k req/day | https://app.infura.io |
| Google Cloud Faucet | Free Sepolia ETH | https://cloud.google.com/application/web3/faucet/ethereum/sepolia |
| MetaMask | Free | https://metamask.io |

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/face-chain.git
cd face-chain

# 2. Create a virtual environment with Python 3.11 specifically
python3.11 -m venv venv
source venv/bin/activate          # macOS / Linux
# venv\Scripts\activate           # Windows

# 3. Install setuptools first (required for face_recognition_models)
pip install setuptools wheel

# 4. Install all dependencies
pip install -r requirements.txt
```

### macOS — dlib note

`face_recognition` depends on `dlib` which requires cmake. If the install fails:

```bash
brew install cmake
pip install dlib
```

### Windows — dlib note

On Windows, install the pre-built dlib wheel:

```bash
pip install dlib-bin
```

### Why Python 3.11 specifically

- Python 3.12+ breaks `face_recognition`'s internal model-path check, causing an import crash even when the models are installed
- Python 3.14 additionally breaks `pkg_resources` (used by `face_recognition_models`) entirely
- This project uses dlib directly to bypass the `face_recognition` wrapper, but still requires Python 3.11 for `face_recognition_models` compatibility
- Python 3.11 is the last version fully compatible with all dependencies in this project

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

# Alchemy or Infura — Sepolia RPC (must be Sepolia, NOT Mainnet)
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_PROJECT_ID

# MetaMask private key (NEVER commit this)
PRIVATE_KEY=your_wallet_private_key_here

# Your wallet public address
WALLET_ADDRESS=0xYourWalletAddressHere

# Filled in after deploy_contract.py
CONTRACT_ADDRESS=0xDeployedContractAddressHere
```

> **Common mistake:** Pasting the Mainnet RPC URL instead of Sepolia. The script will connect successfully but show 0 ETH balance and fail to send transactions. Double-check the URL contains `sepolia`.

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
[Deploy] Wallet: 0xYour...  Balance: 0.050000 SepoliaETH
[Deploy] Transaction sent: 0xabc123...
[Deploy] Waiting for confirmation ...

============================================================
  CONTRACT DEPLOYED SUCCESSFULLY
  Address : 0x4e5c5cA71faD280e396e8147eedA411b16BaC45A
  Tx Hash : 829db4cd...
  Block   : 11634552
  Etherscan: https://sepolia.etherscan.io/address/0x4e5c5cA7...
============================================================

Add this to your .env file:
  CONTRACT_ADDRESS=0x4e5c5cA71faD280e396e8147eedA411b16BaC45A
```

Copy the `CONTRACT_ADDRESS` value into your `.env` file. You never need to deploy again unless you want a fresh contract.

**Deployed contract (HH Goa 2026 demo):**
- Address: `0x4e5c5cA71faD280e396e8147eedA411b16BaC45A`
- Network: Ethereum Sepolia Testnet
- Etherscan: https://sepolia.etherscan.io/address/0x4e5c5cA71faD280e396e8147eedA411b16BaC45A

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
   - Step 1 — Face Detection: turns yellow (running) then green (done) with the encoding shape
   - Step 2 — Reverse Image Search: shows how many visual matches were found across all strategies
   - Step 3 — Post Metadata: shows the scraped post title
   - Step 4 — SHA-256 Fingerprint: shows the full hash
   - Step 5 — Blockchain Registration: confirms the transaction with Etherscan link
4. A **Results card** appears at the bottom showing:
   - The discovered post with thumbnail, title, description, and a direct link
   - The full SHA-256 fingerprint
   - The on-chain record: transaction hash, Etherscan link, registration timestamp, and uploader address
5. Use **Standalone Verification** at the bottom of the page to paste any 64-char hash and verify it against the chain independently.

### Best results — use photos of public figures

Google Lens only returns matches for faces that are publicly indexed on the web. For the strongest demo results, upload a photo of a well-known public figure such as a celebrity, politician, or athlete. A photo of a private person who is not indexed anywhere will fall through to the imgbb fallback, which still completes the full pipeline end-to-end.

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

══════════════════════════════════════════════════════════════
  PIPELINE COMPLETE
══════════════════════════════════════════════════════════════
  Input image      : sample_images/your_face.jpg
  Post found       : https://instagram.com/p/abc123
  SHA-256 hash     : a3f9c27d8e1b...
  Tx hash          : 0xabc123...
  On-chain verified: True
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

---

## Smart contract reference

**File:** `contracts/HashRegistry.sol`
**Solidity:** 0.8.19
**Network:** Ethereum Sepolia Testnet (Chain ID: 11155111)
**Deployed at:** `0x4e5c5cA71faD280e396e8147eedA411b16BaC45A`

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

- **Python 3.11 required** — dlib and face_recognition_models are not compatible with Python 3.12+. The project uses dlib directly to bypass the face_recognition wrapper bug on newer Python versions.
- **face_recognition_models pkg_resources bug** — on Python 3.11+, the package's `__init__.py` fails to import `pkg_resources`. This project works around it by loading dlib model `.dat` files directly by path instead of using the package's API.
- **Apple Silicon segfault fix** — dlib crashes on ARM64 Macs when images have EXIF rotation metadata or non-RGB color modes. `face_encoder.py` applies `ImageOps.exif_transpose()`, forces RGB conversion, resizes images over 1200px, and ensures C-contiguous numpy arrays before passing to dlib.
- **Serper Google Lens free tier** — the `/lens` endpoint on Serper's free plan returns limited results and often returns empty `visual_matches`. The pipeline uses a 4-strategy fallback (Lens → web search → image search → imgbb URL) to guarantee completion.
- **Best results with public figures** — Google Lens only finds matches for faces that are publicly indexed on the web. Photos of private individuals will fall through to the imgbb fallback, which still completes the full pipeline.
- **Social media login walls** — Instagram, TikTok, and X (Twitter) block scraping for logged-out users. The pipeline extracts whatever Open Graph tags are publicly visible and registers that.
- **Sepolia block confirmation time** — transactions take approximately 12 seconds to confirm. This is normal testnet behaviour.
- **In-memory job store** — the Flask server stores pipeline jobs in a Python dict. Restarting the server clears all job history. Fine for demo purposes.

---

## Troubleshooting

### `No face detected in: ...`
The face detection model could not find a face. Try a clearer, front-facing photo with good lighting. The face should be at least ~80×80 pixels.

### `zsh: segmentation fault python app.py`
dlib crashed on image processing. Fixed in the latest `face_encoder.py` which applies EXIF correction, forces RGB, resizes large images, and ensures C-contiguous arrays. Make sure you have the latest version of the file.

### `ModuleNotFoundError: No module named 'pkg_resources'`
Run `pip install setuptools` inside your venv. `pkg_resources` is part of setuptools which may be missing in fresh Python 3.11 venvs.

### `Please install face_recognition_models` error loop
This is a known bug in `face_recognition 1.3.0` on Python 3.11+. This project fixes it by using dlib directly in `face_encoder.py` instead of the `face_recognition` wrapper. Make sure you have the latest `face_encoder.py` from this repo.

### `pip install face-recognition` fails
On macOS, run `brew install cmake` first. On Windows, use `pip install dlib-bin` instead of `dlib`.

### `Cannot connect to Sepolia RPC` / Balance shows 0
Your `SEPOLIA_RPC_URL` is pointing to Ethereum Mainnet instead of Sepolia. The URL must contain `sepolia`:
- Correct: `https://eth-sepolia.g.alchemy.com/v2/YOUR_KEY`
- Wrong: `https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY`

### `pipeline/contract_abi.json not found`
Run `python scripts/deploy_contract.py` first and copy the printed `CONTRACT_ADDRESS` into your `.env`.

### `Hash already registered` (contract revert)
You are trying to register the same post twice. This is intentional — first-write-wins. Upload a different image to generate a new hash.

### `No visual matches found` on Step 2
Serper's Google Lens returned no results for your image. The pipeline now has a 4-strategy fallback and will always complete. For better matches, upload a photo of a well-known public figure.

### Sepolia transaction stuck / pending
Your wallet is out of Sepolia ETH. Claim more from https://cloud.google.com/application/web3/faucet/ethereum/sepolia (no mainnet balance required).
