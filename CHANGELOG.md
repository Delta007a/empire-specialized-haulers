# Changelog

## 0.4.2

- Fixed GamePort login for headless clients, including WC. A missing or unsuccessful client catalog receipt no longer causes the mod to reject native login with `LoginAuthFailed`.
- Kept client catalog reports as diagnostics. The EVE client still receives the ship catalog during login.
- Updated the Launcher manifest and package metadata to 0.4.2.

Validated against EveJS 261028.1's native handshake with empty, unsuccessful and successful catalog responses. The installed 0.4.2 package was also confirmed working in-game by the user.

This release includes all nine ships, blueprints, models, icons and native Mastery profiles. Automatic market stock seeding is not included.
