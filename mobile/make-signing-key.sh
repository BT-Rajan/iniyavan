#!/usr/bin/env bash
# Makes Zigora's Android signing key and hands it to GitHub as the four repository secrets the Android workflow needs, then starts a build.
# Run it once, on your own server:  bash mobile/make-signing-key.sh
# Needs: keytool (from a JDK, e.g. sudo apt install openjdk-21-jdk-headless) and the GitHub CLI (sudo apt install gh, then: gh auth login).
# The key stays on this server, in ~/zigora-signing; only GitHub gets a copy, as encrypted secrets. Keep the folder and the password safe:
# every future version of the app must be signed with this same key, or phones will refuse the update.
set -euo pipefail

REPO="${REPO:-BT-Rajan/iniyavan}"
DIR="${ZIGORA_KEY_DIR:-$HOME/zigora-signing}"
KS="$DIR/zigora.keystore"
ALIAS="zigora"
DNAME="CN=Zigora, O=Zigora Intelligence, L=Chennai, ST=Tamil Nadu, C=IN"

need() { command -v "$1" > /dev/null || { echo "Missing: $1. $2"; exit 1; }; }
need keytool "Install a JDK: sudo apt install openjdk-21-jdk-headless"
need gh "Install the GitHub CLI: sudo apt install gh  (or see https://cli.github.com)"
need base64 ""
gh auth status > /dev/null 2>&1 || { echo "Sign in to GitHub first: gh auth login"; exit 1; }
gh repo view "$REPO" > /dev/null || { echo "Can't reach $REPO with your GitHub sign-in."; exit 1; }

mkdir -p "$DIR"; chmod 700 "$DIR"
if [ -f "$KS" ]; then
  echo "A key already exists: $KS"
  read -r -p "Use it and send it to GitHub again? [Y/n] " a
  case "${a:-y}" in [Nn]*) echo "Stopped. Nothing changed."; exit 0;; esac
  read -r -s -p "Password of the existing key: " PW; echo
  keytool -list -keystore "$KS" -storepass "$PW" -alias "$ALIAS" > /dev/null 2>&1 || { echo "That password doesn't open $KS."; exit 1; }
else
  while :; do
    read -r -s -p "Choose a password for the key (at least 8 characters): " PW; echo
    read -r -s -p "Type it again: " PW2; echo
    [ "$PW" = "$PW2" ] && [ ${#PW} -ge 8 ] && break
    echo "The two didn't match, or it is shorter than 8 characters. Try again."
  done
  echo "Making the key for: $DNAME"
  export ZIGORA_PW="$PW"
  keytool -genkeypair -keystore "$KS" -storetype PKCS12 -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10000 \
    -dname "$DNAME" -storepass:env ZIGORA_PW -keypass:env ZIGORA_PW > /dev/null
  unset ZIGORA_PW
  chmod 600 "$KS"
  echo "Made $KS"
fi

# the key as one line of base64 text, checked by turning it back into the file
B64="$(base64 -w0 "$KS")"
printf '%s' "$B64" | base64 -d | cmp -s - "$KS" || { echo "The key could not be turned into text correctly. Nothing was sent."; exit 1; }

echo "Sending the four secrets to $REPO…"
printf '%s' "$B64"   | gh secret set ANDROID_KEYSTORE_B64      --repo "$REPO"
printf '%s' "$PW"    | gh secret set ANDROID_KEYSTORE_PASSWORD --repo "$REPO"
printf '%s' "$ALIAS" | gh secret set ANDROID_KEY_ALIAS         --repo "$REPO"
printf '%s' "$PW"    | gh secret set ANDROID_KEY_PASSWORD      --repo "$REPO"
unset PW PW2 B64
gh secret list --repo "$REPO" | grep -E '^ANDROID_' || true

read -r -p "Start the Android build now, to publish the app? [Y/n] " a
case "${a:-y}" in
  [Nn]*) echo "Later: GitHub → Actions → Android → Run workflow." ;;
  *) gh workflow run android.yml --repo "$REPO" --ref main && echo "Started. In about 5 minutes the release appears at https://github.com/$REPO/releases" ;;
esac
echo
echo "Done. Back up $DIR (the key) and remember the password: you need both for every future version."
