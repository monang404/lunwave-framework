const js = require("@eslint/js");
const globals = require("globals");

// Globals yang diekspos ke window oleh modul shared JS lewat window-compat block.
// Daftar ini berlaku sebagai pengganti type declarations untuk eslint no-undef.
const lunaWaveGlobals = {
  // store.js
  store: "readonly",
  createStore: "readonly",
  markPendingToggle: "readonly",
  isPendingToggleActive: "readonly",
  PENDING_TOGGLE_TIMEOUT_MS: "readonly",
  // ws.js
  wsConnect: "readonly",
  wsSend: "readonly",
  handleServerMessage: "readonly",
  ws: "readonly",
  syncLocalLyrics: "readonly",
  renderHeader: "readonly",
  // utils/format.js
  formatTime: "readonly",
  escapeHtml: "readonly",
  formatDurationLong: "readonly",
  // utils/toast.js
  showLogToast: "readonly",
  showConnectionToast: "readonly",
  hideConnectionToast: "readonly",
  safeStorage: "readonly",
  loadLazyCovers: "readonly",
  getCoverArt: "readonly",
  getCoverArtFast: "readonly",
  extractDominantColor: "readonly",
  cleanTrackTitle: "readonly",
  // dom.js
  dom: "readonly",
  initDOM: "readonly",
  // config.js
  TABS: "readonly",
  // portal.js
  initPortal: "readonly",
  initSetupCheck: "readonly",
  // services/auth.js
  login: "readonly",
  logout: "readonly",
  applyRoleUI: "readonly",
  updateSetupSubmitState: "readonly",
  _lastLoadedVideoId: "writable",
  // Dual CJS/ESM export shim guard: `if (typeof module !== 'undefined' && module.exports)`
  // at the bottom of store.js/ws.js/utils/format.js, used so Vitest (Node/require)
  // can load the same file the browser loads natively as an ES module.
  module: "readonly",
  // render/*
  renderProgress: "readonly",
  renderPlayBtn: "readonly",
  renderNowPlaying: "readonly",
  renderQueue: "readonly",
  renderRadio: "readonly",
  renderSearchResults: "readonly",
  renderDiscoverTab: "readonly",
  renderRecentRow: "readonly",
  renderDiscoverPersonalization: "readonly",
  renderDiscoverSearchResults: "readonly",
  renderLyrics: "readonly",
  renderPlayerBar: "readonly",
  renderSettingsSheet: "readonly",
  renderFullState: "readonly",
  applyFullState: "readonly",
  updateSearchPlayingState: "readonly",
  updateDiscoverPlayingState: "readonly",
  handleArtistDetail: "readonly",
  handleDiscoverSearchError: "readonly",
  syncPlayerStateAttr: "readonly",
  syncBrowserAudio: "readonly",
  setRadioHeroAnimState: "readonly",
  startProgressClock: "readonly",
  // audio/*
  initAudio: "readonly",
  getOrInitAudio: "readonly",
  resetAnchorClock: "readonly",
  setPositionAnchor: "readonly",
  _progressRafId: "readonly",
  _resumeAndPlay: "readonly",
  // events/*
  initEvents: "readonly",
  switchTab: "readonly",
  buildDecadeChips: "readonly",
  getDecade: "readonly",
  isDraggingQueue: "readonly",
  // Additional auto-discovered globals
  _fadeIntervals: "readonly",
  activeAudioIndex: "readonly",
  analyser: "readonly",
  buildSrThumbHtml: "readonly",
  closeMainOverlay: "readonly",
  closeSettings: "readonly",
  dataArray: "readonly",
  enterDiscoverSearchLoading: "readonly",
  exitDiscoverSearchMode: "readonly",
  getInterpolatedPosition: "readonly",
  hideActionModal: "readonly",
  initActionModalEvents: "readonly",
  initClickDelegationEvents: "readonly",
  initDiscoverFilterEvents: "readonly",
  initDiscoverSearchEvents: "readonly",
  initDragScrollEvents: "readonly",
  initKeyboardShortcutEvents: "readonly",
  initLyricsEvents: "readonly",
  initProgressEvents: "readonly",
  initQueueDragDrop: "readonly",
  initQueueEvents: "readonly",
  initSearchInputEvents: "readonly",
  initSettingsEvents: "readonly",
  initTransportEvents: "readonly",
  initVisualizer: "readonly",
  playSearchTrack: "readonly",
  resumeVisualizerLoop: "readonly",
  showActionModal: "readonly",
  startFakeBeatLoop: "readonly",
  stopProgressClock: "readonly",
  submitSetup: "readonly",
  unlockBrowserAudio: "readonly",
  updateMediaSession: "readonly",
  updateOffsetDisplay: "readonly",
};

module.exports = [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2021,
      globals: {
        ...globals.browser,
        ...lunaWaveGlobals,
      }
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "warn",
      "no-case-declarations": "warn",
      "no-empty": "warn",
    }
  },
  {
    // Config files and Playwright/Node-side tests run under Node (CommonJS),
    // not the browser -- they use require()/process/module directly.
    files: [
      "eslint.config.js",
      "playwright.config.js",
      "tests/frontend/visual/**/*.js",
    ],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "commonjs",
      globals: {
        ...globals.node,
      }
    }
  },
  {
    // vitest.config.js uses ESM `export default`, unlike the CJS configs above.
    files: ["vitest.config.js"],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "module",
      globals: {
        ...globals.node,
      }
    }
  }
];
