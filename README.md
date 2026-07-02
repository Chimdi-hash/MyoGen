# 🧬 MYOGEN — Decentralized Muscle Physiology Dictionary

> The world's first AI-validated, on-chain dictionary for muscle physiology and anatomy, built on **GenLayer Bradbury Testnet**.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/YOUR_USERNAME/myogen)

---

## 🌐 Live Demo
Deploy to Vercel and access at your project URL.

## ✨ Features
- 🔐 **Wallet-gated** — Connect MetaMask to GenLayer Bradbury Testnet (Chain ID 961)
- 🤖 **AI Validators** — 5 validators reach consensus via Optimistic Democracy
- 🧬 **300+ Terms** — Full muscle physiology & anatomy coverage
- 🎨 **7 Visualization Types** — Animated Canvas diagrams per term
- ⚡ **Sequential Study** — No timeout errors, cached validator results
- 🌙 **Glassmorphism UI** — Futuristic orange/white design with animations

## 📁 Project Structure
```
myogen/
├── index.html          # Landing page
├── register.html       # Wallet connect & registration
├── study.html          # Main study room (tx signing + AI results)
├── explorer.html       # Browse study history
├── about.html          # About MYOGEN & GenLayer
├── style.css           # Global design system
├── app.js              # Shared wallet/UI utilities
├── myogen_contract.py  # GenLayer Intelligent Contract
├── vercel.json         # Vercel deployment config
└── package.json        # Dev server scripts
```

## 🚀 Deploy to Vercel

### Option 1: Vercel CLI
```bash
npm install -g vercel
vercel --prod
```

### Option 2: GitHub → Vercel Dashboard
1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) → New Project
3. Import your GitHub repo
4. Vercel auto-detects static site — click **Deploy**

### Option 3: Drag & Drop
1. Go to [vercel.com/new](https://vercel.com/new)
2. Drag the `myogen/` folder directly

## 🏗️ Local Development
```bash
npm run dev   # Starts local server at http://localhost:3000
```

## 🔗 GenLayer Network Config
| Property | Value |
|---|---|
| Network Name | GenLayer Bradbury Testnet |
| Chain ID | 961 |
| RPC URL | https://rpc.bradbury.genlayer.com |
| Currency | GEN |
| Explorer | https://explorer.bradbury.genlayer.com |

## 🐍 Smart Contract Deployment
The `myogen_contract.py` is a GenLayer Intelligent Contract. To deploy:
```bash
pip install genlayer
genlayer deploy myogen_contract.py --network bradbury
```
After deployment, update `CONTRACT_ADDRESS` in `app.js`.

## 🎯 User Workflow
1. Visit site → **Connect Wallet** (MetaMask + GenLayer testnet)
2. Navigate to **Study** → type muscle term
3. Click **Study This Term** → MetaMask prompts to sign tx
4. **5 AI validators** analyze term via LLM on GenLayer
5. **Consensus reached** → explanation + animated visualization displayed
6. Study next term immediately — cached results = no waiting

## 📄 License
MIT © 2026 MYOGEN
