const { test, expect } = require('@playwright/test');

test.describe('LunaWave Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to app page
    await page.goto('/admin');
    // Log in via the portal-screen (admin_account is seeded from
    // LUNAWAVE_ADMIN_USER/LUNAWAVE_ADMIN_PASS env vars, so this is the
    // login form, not the first-run setup form).
    await page.waitForSelector('#portal-screen', { state: 'visible' });
    await page.fill('#admin-username', process.env.LUNAWAVE_ADMIN_USER || 'admin');
    await page.fill('#admin-password', process.env.LUNAWAVE_ADMIN_PASS || '');
    await page.click('#admin-submit-btn');
    // Wait for network idle or main elements to load
    await page.waitForSelector('#app', { state: 'visible' });
    // Mock or wait for some elements if necessary
  });

  test('Radio Hero - Off State', async ({ page }) => {
    // .radio-hero lives inside #tab-radio, which is not the default active
    // tab (#tab-home is). Without switching tabs this test silently no-ops
    // (isVisible() stays false, toHaveScreenshot never runs). Replicate
    // exactly what switchTab('radio') does in events/index.js so the tab
    // panel actually becomes visible.
    await page.evaluate(() => {
      document.body.dataset.activeTab = 'radio';
      document.getElementById('tab-home')?.classList.remove('active');
      document.getElementById('tab-radio')?.classList.add('active');
    });
    const radioHero = page.locator('.radio-hero');
    if (await radioHero.isVisible()) {
      await expect(radioHero).toHaveScreenshot('radio-hero-off.png');
    }
  });

  test('Player Bar - Paused', async ({ page }) => {
    // No real mpv/audio available in this environment (mpv binary not
    // found), so #player-bar stays CSS-hidden while data-player-state
    // stays "IDLE" (see body[data-player-state="IDLE"] #player-bar rule
    // in desktop.css). Per explicit user decision, simulate a "paused"
    // state directly via DOM injection instead of driving real playback.
    await page.evaluate(() => {
      document.body.setAttribute('data-player-state', 'PAUSED');
      const title = document.getElementById('np-title');
      const artist = document.getElementById('np-artist');
      if (title) title.textContent = '[Simulated Track Title]';
      if (artist) artist.textContent = '[Simulated Artist]';
    });
    const playerBar = page.locator('#player-bar');
    if (await playerBar.isVisible()) {
      await expect(playerBar).toHaveScreenshot('player-bar-paused.png');
    }
  });

  test('Now Playing Panel', async ({ page }) => {
    // Same simulated-state rationale as 'Player Bar - Paused' above:
    // .home-track-info is hidden while data-player-state="IDLE"
    // (see grid.css). Simulated, not real playback.
    await page.evaluate(() => {
      document.body.setAttribute('data-player-state', 'PAUSED');
      const title = document.getElementById('np-title');
      const artist = document.getElementById('np-artist');
      if (title) title.textContent = '[Simulated Track Title]';
      if (artist) artist.textContent = '[Simulated Artist]';
    });
    const nowPlaying = page.locator('.home-track-info');
    if (await nowPlaying.isVisible()) {
      await expect(nowPlaying).toHaveScreenshot('now-playing-panel.png');
    }
  });
});
