#!/usr/bin/env bash
# The Android app's version number N (the app is 1.0.N): the commits that changed the app, its own folder and the web files it packs in.
# Used by the Android workflow to name a release and by run.sh to know which release a deploy should show.
cd "$(dirname "${BASH_SOURCE[0]}")" && git rev-list --count HEAD -- . ../frontend/src/reader.jsx ../frontend/src/content.jsx ../frontend/src/highlighter.js \
  ../frontend/src/styles.css ../frontend/src/locales ../frontend/reader.html ../frontend/vite.reader.config.js
