#!/usr/bin/env bash
# Undoes what capture.js did to the checkout: the local.properties it wrote (only if it wrote it).
[ -f mobile/.promo-made-local-properties ] && rm -f mobile/local.properties mobile/.promo-made-local-properties
exit 0
