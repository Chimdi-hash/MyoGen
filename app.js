/* ===================================================
   MYOGEN — Shared JavaScript Utilities
   GenLayer Studio Integration
   =================================================== */

// ── GenLayer Studio Config ──
const GENLAYER_CONFIG = {
  chainId: '0xF22F',        // 61999 in hex
  chainIdDec: 61999,
  chainName: 'GenLayer Studio',
  rpcUrls: ['https://studio.genlayer.com/api'],
  nativeCurrency: {
    name: 'GEN',
    symbol: 'GEN',
    decimals: 18
  },
  blockExplorerUrls: []
};

// ── Contract Address (set after deployment) ──
// The deployed GenLayer Contract Address for MyoGen
const CONTRACT_ADDRESS = '0x6bb0DD73994248F91986e00bddA1c831150255aB';

// ── Wallet State ──
window.myogenWallet = {
  address: null,
  provider: null,
  signer: null,
  isConnected: false,
  chainId: null,
};

// ── Toast Notifications ──
function showToast(message, type = 'info', duration = 4000) {
  let toast = document.getElementById('myogen-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'myogen-toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }

  const icons = {
    success: '✅',
    error: '❌',
    info: '🧬',
    warning: '⚠️'
  };

  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span style="font-size:1.1rem">${icons[type] || '🔬'}</span>
    <span>${message}</span>
  `;

  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

// ── Connect Wallet ──
async function connectWallet() {
  if (typeof window.ethereum === 'undefined') {
    showToast('Please install MetaMask to use MYOGEN', 'error');
    window.open('https://metamask.io/', '_blank');
    return false;
  }

  try {
    showToast('Connecting to wallet...', 'info');

    const accounts = await window.ethereum.request({
      method: 'eth_requestAccounts'
    });

    if (!accounts || accounts.length === 0) {
      showToast('No accounts found. Please unlock MetaMask.', 'error');
      return false;
    }

    // Switch to / add GenLayer Studio
    await switchToGenLayer();

    window.myogenWallet.address = accounts[0];
    window.myogenWallet.isConnected = true;

    // Persist to localStorage
    localStorage.setItem('myogen_wallet', accounts[0]);
    localStorage.setItem('myogen_connected', 'true');

    updateWalletUI();
    showToast(`Connected: ${shortenAddress(accounts[0])}`, 'success');

    // Listen for account changes
    window.ethereum.on('accountsChanged', handleAccountsChanged);
    window.ethereum.on('chainChanged', handleChainChanged);

    return true;
  } catch (err) {
    if (err.code === 4001) {
      showToast('Wallet connection rejected by user.', 'warning');
    } else {
      showToast(`Connection error: ${err.message}`, 'error');
    }
    return false;
  }
}

// ── Switch to GenLayer Studio ──
async function switchToGenLayer() {
  try {
    await window.ethereum.request({
      method: 'wallet_switchEthereumChain',
      params: [{ chainId: GENLAYER_CONFIG.chainId }]
    });
  } catch (switchError) {
    if (switchError.code === 4902) {
      try {
        await window.ethereum.request({
          method: 'wallet_addEthereumChain',
          params: [GENLAYER_CONFIG]
        });
      } catch (addError) {
        showToast('Could not add GenLayer network. Please add it manually.', 'error');
        throw addError;
      }
    } else if (switchError.code === 4001) {
      showToast('Please switch to GenLayer Studio network.', 'warning');
    }
  }
}

// ── Disconnect Wallet ──
function disconnectWallet() {
  window.myogenWallet = {
    address: null,
    provider: null,
    signer: null,
    isConnected: false,
    chainId: null,
  };

  localStorage.removeItem('myogen_wallet');
  localStorage.removeItem('myogen_connected');

  updateWalletUI();
  showToast('Wallet disconnected.', 'info');

  // Redirect to home if on protected page
  const protectedPages = ['study.html', 'explorer.html'];
  const currentPage = window.location.pathname.split('/').pop();
  if (protectedPages.includes(currentPage)) {
    setTimeout(() => window.location.href = 'index.html', 1200);
  }
}

// ── Handle Events ──
function handleAccountsChanged(accounts) {
  if (accounts.length === 0) {
    disconnectWallet();
  } else if (accounts[0] !== window.myogenWallet.address) {
    window.myogenWallet.address = accounts[0];
    localStorage.setItem('myogen_wallet', accounts[0]);
    updateWalletUI();
    showToast(`Account changed: ${shortenAddress(accounts[0])}`, 'info');
  }
}

function handleChainChanged(chainId) {
  window.myogenWallet.chainId = chainId;
  if (chainId !== GENLAYER_CONFIG.chainId) {
    showToast('Please switch back to GenLayer Studio.', 'warning');
  }
}

// ── Restore Wallet Session ──
async function restoreWalletSession() {
  if (typeof window.ethereum === 'undefined') return;
  if (localStorage.getItem('myogen_connected') !== 'true') return;

  try {
    const accounts = await window.ethereum.request({ method: 'eth_accounts' });
    if (accounts.length > 0) {
      window.myogenWallet.address = accounts[0];
      window.myogenWallet.isConnected = true;
      updateWalletUI();
      window.ethereum.on('accountsChanged', handleAccountsChanged);
      window.ethereum.on('chainChanged', handleChainChanged);
    }
  } catch (err) {
    console.warn('Could not restore session:', err);
  }
}

// ── Update Navbar Wallet UI ──
function updateWalletUI() {
  const connectBtn = document.getElementById('connect-wallet-btn');
  const walletInfo = document.getElementById('wallet-info-bar');
  const walletAddrEl = document.getElementById('wallet-address-display');
  const disconnectBtn = document.getElementById('disconnect-btn');

  if (window.myogenWallet.isConnected && window.myogenWallet.address) {
    if (connectBtn) connectBtn.style.display = 'none';
    if (walletInfo) walletInfo.style.display = 'flex';
    if (walletAddrEl) walletAddrEl.textContent = shortenAddress(window.myogenWallet.address);
  } else {
    if (connectBtn) connectBtn.style.display = 'flex';
    if (walletInfo) walletInfo.style.display = 'none';
  }
}

// ── Utilities ──
function shortenAddress(addr) {
  if (!addr) return '';
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function formatNumber(n) {
  return new Intl.NumberFormat().format(n);
}

// ── Particle System ──
function initParticles(containerId, count = 25) {
  const container = document.getElementById(containerId);
  if (!container) return;

  for (let i = 0; i < count; i++) {
    const particle = document.createElement('div');
    particle.className = 'particle';

    const size = Math.random() * 4 + 1;
    const x = Math.random() * 100;
    const duration = Math.random() * 15 + 10;
    const delay = Math.random() * 15;
    const opacity = Math.random() * 0.4 + 0.1;

    // Alternating orange/white particles
    const isOrange = Math.random() > 0.5;
    const color = isOrange
      ? `rgba(255, ${80 + Math.floor(Math.random() * 100)}, 44, ${opacity})`
      : `rgba(255, 255, 255, ${opacity * 0.5})`;

    particle.style.cssText = `
      width: ${size}px;
      height: ${size}px;
      left: ${x}%;
      background: ${color};
      box-shadow: 0 0 ${size * 3}px ${color};
      animation-duration: ${duration}s;
      animation-delay: -${delay}s;
    `;

    container.appendChild(particle);
  }
}

// ── Floating Muscle Characters ──
function initFloatingChars() {
  const chars = document.querySelectorAll('.floating-char');
  chars.forEach((char, i) => {
    const duration = 20 + Math.random() * 30;
    const delay = -Math.random() * 30;
    const y = 10 + Math.random() * 70;
    char.style.cssText = `
      top: ${y}%;
      animation-duration: ${duration}s;
      animation-delay: ${delay}s;
    `;
  });
}

// ── Scroll Animations ──
function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.animation = 'slide-in-up 0.7s ease both';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  document.querySelectorAll('[data-animate]').forEach(el => {
    el.style.opacity = '0';
    observer.observe(el);
  });
}

// ── Navbar Scroll Effect ──
function initNavbar() {
  const navbar = document.querySelector('.navbar');
  if (!navbar) return;

  window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
      navbar.classList.add('scrolled');
    } else {
      navbar.classList.remove('scrolled');
    }
  });

  // Hamburger
  const hamburger = document.getElementById('hamburger');
  const navLinks = document.getElementById('nav-links');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', () => {
      navLinks.classList.toggle('open');
    });
  }
}

// ── Counter Animation ──
function animateCounter(element, target, suffix = "", duration = 2000) {
  const start = 0;
  const step = target / (duration / 16);
  let current = start;

  const timer = setInterval(() => {
    current += step;
    if (current >= target) {
      current = target;
      clearInterval(timer);
    }
    element.textContent = Math.floor(current).toLocaleString() + suffix;
  }, 16);
}

// ── GenLayer RPC Call (read-only view) ──
async function callContractView(method, params = []) {
  try {
    const response = await fetch(GENLAYER_CONFIG.rpcUrls[0], {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        method: 'gen_call',
        params: [{
          to: CONTRACT_ADDRESS,
          data: encodeMethod(method, params)
        }, 'latest'],
        id: Date.now()
      })
    });
    const data = await response.json();
    return data.result;
  } catch (err) {
    console.error('RPC view call error:', err);
    return null;
  }
}

// ── Encode method call (simplified ABI encoding) ──
function encodeMethod(method, params) {
  // For GenLayer's Python-based contracts, we use a JSON-encoded call format
  return JSON.stringify({ method, params });
}

// ── Initialize on DOM Load ──
document.addEventListener('DOMContentLoaded', async () => {
  initNavbar();
  initParticles('particle-field', 30);
  initFloatingChars();
  initScrollAnimations();
  await restoreWalletSession();

  // Connect button listeners
  const connectBtn = document.getElementById('connect-wallet-btn');
  if (connectBtn) {
    connectBtn.addEventListener('click', connectWallet);
  }

  const disconnectBtn = document.getElementById('disconnect-btn');
  if (disconnectBtn) {
    disconnectBtn.addEventListener('click', disconnectWallet);
  }
});
