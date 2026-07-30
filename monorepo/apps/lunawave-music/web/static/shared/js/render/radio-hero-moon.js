import { on } from "../bus.js";
import { getInterpolatedPosition } from "./player.js";
import { store } from "/framework/static/js/core/store.js";

export let setRadioHeroAnimState;
export let shortestDeltaTestOnly;

/* ═══════════════════════════════════════════
   radio-hero-moon.js — "Night Dial" moon-phase animation module
   Sumber: docs/rfc/radio_toggle.md §5.3, §5.4, §6; mockup lunawave-hero-creative-v8.html

   SELF-CONTAINED: modul ini query elemen SVG-nya sendiri lewat
   document.getElementById, TIDAK menambah entry baru ke dom.js (RFC §5.3 —
   hindari 2 sumber kebenaran untuk elemen yang sama).

   Dibangun bertahap sesi 3-4 (R3.1..R4.1). Sudah di-load lewat
   import initRadioHeroBusSubscriptions di web/static/pages/app/main.js.

   UPDATE (progress-driven): mode "cycling" tidak lagi loop buta 42 detik.
   Fase bulan sekarang mengikuti progress lagu yang sedang diputar
   (store.current_track.duration + getInterpolatedPosition() dari
   player.js, dibaca read-only): awal lagu = bulan gelap/baru, tengah
   lagu = purnama, akhir lagu = gelap lagi. Time-lapse 42 detik tetap
   dipertahankan sebagai fallback kalau durasi lagu belum diketahui
   (mis. sebelum track pertama termuat). Lihat getSongProgressPhase()
   & stepCycle() di bawah.
   ═══════════════════════════════════════════ */

(function () {
  "use strict";

  // ── R3.1: query elemen sendiri, guard null (bisa di-load standalone
  // walau elemen SVG belum ada di index.html) ──
  const litCool = document.getElementById("moonLitCool");
  const litWarm = document.getElementById("moonLitWarm");
  const moonGroup = document.getElementById("moonGroup");

  const CX = 86, CY = 66, R = 40;
  const SYNODIC_DAYS = 29.530588853;
  const KNOWN_NEW_MOON_UTC = Date.UTC(2000, 0, 6, 18, 14, 0);
  const reduceMotion = globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ── Astronomy: real moon phase fraction (0 = new, 0.5 = full) ──
  function realPhase(date) {
    const days = (date.getTime() - KNOWN_NEW_MOON_UTC) / 86400000;
    let p = (days % SYNODIC_DAYS) / SYNODIC_DAYS;
    if (p < 0) p += 1;
    return p;
  }

  // ── Geometry: terminator path via two-arc construction ──
  // rx = r*cos(theta) gives the ellipse half-width of the terminator curve;
  // sweep flags flip which side is illuminated as the phase crosses quarters.
  function moonPathD(phase) {
    const theta = phase * 2 * Math.PI;
    const rx = Math.abs(R * Math.cos(theta));
    const outerSweep = phase < 0.5 ? 1 : 0;
    const innerSweep = (phase < 0.25 || phase > 0.75) ? outerSweep : (outerSweep ? 0 : 1);
    return `M ${CX} ${CY - R} A ${R} ${R} 0 0 ${outerSweep} ${CX} ${CY + R} A ${rx} ${R} 0 0 ${innerSweep} ${CX} ${CY - R} Z`;
  }

  // ── Libration: real moons rock slightly as they orbit, so a hair more
  // or less of the limb tips into view over the month. Two independent,
  // non-matching frequencies (not locked to the phase cycle itself) keep
  // it reading as a slow physical drift rather than a synced wobble loop.
  function render(phase) {
    if (!litCool || !litWarm) return;
    const d = moonPathD(phase);
    litCool.setAttribute("d", d);
    litWarm.setAttribute("d", d);

    if (moonGroup && !reduceMotion) {
      const t = phase * 2 * Math.PI;
      const lon = Math.sin(t * 1.0) * 1.6;
      const lat = Math.sin(t * 0.63 + 1.1) * 1.1;
      const dx = Math.sin(t * 1.0) * 1.3;
      const dy = Math.cos(t * 0.63) * 0.9;
      moonGroup.style.transform = `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px) rotate(${(lon + lat).toFixed(2)}deg)`;
    }
  }
  // ── R3.2: State machine rAF (cycling/tweening) — SEMUA di module-scope
  // (closure IIFE), BUKAN di window, supaya mustahil bentrok dengan
  // _progressRafId di player.js (RFC §5.3, §5.4). ──
  let currentPhase = realPhase(new Date());
  let mode = "idle";       // 'idle' | 'cycling' | 'tweening'
  let rafId = null;
  let cycleStartTs = null;
  let cycleStartPhase = 0;
  let tweenStartTs = null;
  let tweenStartPhase = 0;
  let tweenTargetPhase = 0;
  const CYCLE_SECONDS = 42; // fallback time-lapse duration, dipakai HANYA kalau durasi lagu tidak diketahui
  const TWEEN_MS = 900;

  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function shortestDelta(from, to) {
    let d = (to - from) % 1;
    if (d < 0) d += 1;   // normalize ke [0, 1)
    if (d > 0.5) d -= 1; // ambil arah terpendek; tie (d === 0.5) tetap +0.5
    return d;
  }
  shortestDeltaTestOnly = shortestDelta;

  // ── R3.2b (progress-driven): map fase bulan ke progress lagu yang sedang
  // diputar, bukan ke jam buatan. CATATAN: secara empiris moonPathD(0) itu
  // PURNAMA dan moonPathD(0.5) itu gelap/baru (kebalikan dari asumsi awal
  // di komentar realPhase() di atas) — jadi fraction progress lagu digeser
  // 0.5 dulu sebelum dipakai sebagai phase, supaya hasil akhirnya sesuai
  // konvensi yang diminta: awal lagu (fraction 0) = gelap, tengah lagu
  // (fraction 0.5) = purnama, akhir lagu (fraction 1 ≡ 0 lagi) = gelap lagi.
  // Baca store.current_track.duration + getInterpolatedPosition() dari
  // player.js (top-level function/const di script classic lain, jadi
  // bisa diakses langsung — TIDAK menulis balik apa pun ke sana, read-only).
  // Return null kalau durasi lagu belum diketahui (belum ada track / durasi
  // 0), supaya caller bisa fallback ke time-lapse 42 detik yang lama. ──
  function getSongProgressPhase() {
    const track = store && store.current_track;
    const dur = track ? track.duration : 0;
    if (!dur || dur <= 0) return null;
    const pos = typeof getInterpolatedPosition === "function"
      ? getInterpolatedPosition()
      : (store ? store.position || 0 : 0);
    const fraction = Math.max(0, Math.min(1, pos / dur));
    return (fraction + 0.5) % 1;
  }

  function stepCycle(ts) {
    if (mode !== "cycling") return;
    const songPhase = getSongProgressPhase();
    if (songPhase !== null) {
      // Lagu sedang diputar & durasinya diketahui: fase bulan mengikuti
      // posisi playback secara langsung (informatif, bukan loop buta).
      currentPhase = songPhase;
      cycleStartTs = null; // reset supaya kalau nanti fallback dipakai lagi, mulai dari 0 elapsed
    } else {
      // Fallback: belum ada lagu / durasi tidak diketahui -> time-lapse lama.
      if (cycleStartTs === null) cycleStartTs = ts;
      const elapsed = (ts - cycleStartTs) / 1000;
      currentPhase = (cycleStartPhase + elapsed / CYCLE_SECONDS) % 1;
    }
    render(currentPhase);
    if (document.hidden) {
      rafId = null;
      mode = "idle";
      return;
    }
    rafId = requestAnimationFrame(stepCycle);
  }

  function stepTween(ts) {
    if (mode !== "tweening") return;
    if (tweenStartTs === null) tweenStartTs = ts;
    const t = Math.min(1, (ts - tweenStartTs) / TWEEN_MS);
    const eased = easeInOutCubic(t);
    currentPhase = (tweenStartPhase + shortestDelta(tweenStartPhase, tweenTargetPhase) * eased + 1) % 1;
    render(currentPhase);
    if (t < 1) {
      if (document.hidden) {
        rafId = null;
        mode = "idle";
        return;
      }
      rafId = requestAnimationFrame(stepTween);
    } else {
      mode = "idle";
    }
  }

  function goCycling() {
    if (rafId !== null) cancelAnimationFrame(rafId);
    // QA R6.6 fix: reduceMotion sebelumnya hanya mematikan transform libration
    // di render(), tapi rAF loop stepCycle tetap jalan terus-menerus di
    // belakang layar walau OS-level prefers-reduced-motion aktif. RFC §5.5
    // poin 5 & DoD R6.6 mensyaratkan loop-nya sendiri berhenti (fallback ke
    // render statis), bukan cuma transform-nya yang di-skip.
    if (reduceMotion) {
      mode = "idle";
      currentPhase = realPhase(new Date());
      render(currentPhase);
      return;
    }
    mode = "cycling";
    cycleStartTs = null;
    cycleStartPhase = currentPhase;
    rafId = requestAnimationFrame(stepCycle);
  }

  function goTweenToReal() {
    if (rafId !== null) cancelAnimationFrame(rafId);
    if (reduceMotion) {
      mode = "idle";
      currentPhase = realPhase(new Date());
      render(currentPhase);
      return;
    }
    mode = "tweening";
    tweenStartTs = null;
    tweenStartPhase = currentPhase;
    tweenTargetPhase = realPhase(new Date());
    rafId = requestAnimationFrame(stepTween);
  }

  // ── R3.3: init — render fase bulan nyata sekali saat modul dimuat ──
  render(currentPhase);

  // ── R3.3: SATU-SATUNYA API publik. Hanya menerima 1 parameter boolean,
  // tidak return apa pun yang dikonsumsi caller (RFC §5.3, §6 poin 2):
  //   - TIDAK menyentuh classList dari #radio-toggle-btn (domain radio-tab.js)
  //   - UPDATE (progress-driven): modul ini SEKARANG membaca
  //     store.current_track.duration + getInterpolatedPosition() secara
  //     read-only (lihat getSongProgressPhase()) supaya fase bulan bisa
  //     mengikuti progress lagu. Tidak ada store.* lain yang disentuh, dan
  //     modul ini tetap TIDAK PERNAH menulis ke store.* apa pun.
  //   - TIDAK memanggil resetAnchorClock/setPositionAnchor/wsSend/apa pun
  //     dari playback-sync.js atau player.js
  //   - TIDAK menulis dom.rtSub.textContent (domain radio-tab.js)
  // Klik/keydown listener dari mockup SENGAJA TIDAK diporting — event click
  // 100% milik transport-events.js (termasuk role-check admin & wsSend). ──
  setRadioHeroAnimState = function (isOn) {
    if (isOn) {
      goCycling();
    } else {
      goTweenToReal();
    }
  };

  globalThis.setRadioHeroAnimState = setRadioHeroAnimState;
})();

export function initRadioHeroBusSubscriptions() {
    on("radio-hero:anim", ({ on: animOn }) => setRadioHeroAnimState(animOn));
}
