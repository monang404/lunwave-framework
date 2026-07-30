# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-07-15
### Added
- Quality of Life improvements including Thompson Sampling Bandit algorithm for smarter Radio Mode selections.
- EBU R128 Loudness Normalization support to maintain consistent volume across tracks.
- Adaptive Network Prefetch using a latency window for smoother transitions.

### Fixed
- Stabilized CI/CD pipelines by properly forcing zombie threads (like `yt-dlp` and `ffprobe` executors) to terminate on exit.
- Increased unit and integration test coverage to > 78%.

## [1.0.0] - 2026-07-13
### Added
- Complete rewrite of architecture into Hexagonal/Ports & Adapters pattern.
- Radio mode with infinite smart queue.
- SponsorBlock integration.
- Synchronized lyrics viewer.
- Full unit test coverage for pure logic components.
