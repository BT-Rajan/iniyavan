#!/usr/bin/env bash
# After a deploy: waits (up to 20 minutes) until the Android release this commit makes is out on GitHub, then has the running server show
# it, so the home page and the app's update note don't keep the previous version for a day. run.sh starts it in the background.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
env_of() { sed -n "s/^$1=//p" .env | tail -1 | tr -d "\"'"; }
if grep -q '^ANDROID_REPO=' .env; then REPO=$(env_of ANDROID_REPO); else REPO=BT-Rajan/iniyavan; fi
[ -n "$REPO" ] || { echo "ANDROID_REPO is empty: nothing to show."; exit 0; }
HOST=$(env_of HOST); PORT=$(env_of PORT); case "${HOST:-0.0.0.0}" in 0.0.0.0|::) HOST=127.0.0.1;; esac
BASE="http://${HOST:-127.0.0.1}:${PORT:-5252}"
KEY=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(("android-refresh:"+sys.argv[1].strip()).encode()).hexdigest())' "$(env_of JWT_SECRET)")
# the version this commit's release carries (a shallow clone can't count it: then just look once)
WANT=0; [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = false ] && WANT=$(bash mobile/version.sh)
newest() {
  curl -fsS -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$REPO/releases?per_page=10" | python3 -c '
import sys, json, re
v = [int(m.group(1)) for r in json.load(sys.stdin) if not r.get("draft") and not r.get("prerelease")
     for m in [re.fullmatch(r"android-v1\.0\.(\d+)", r.get("tag_name") or "")] if m]
print(max(v or [0]))'
}
for i in $(seq 1 20); do
  have=$(newest 2>/dev/null || echo 0)
  [ "$have" -ge "$WANT" ] && break
  echo "$(date '+%F %T') waiting for Android 1.0.$WANT on GitHub (newest is 1.0.$have)"; sleep 60
done
for i in $(seq 1 30); do curl -fsS -o /dev/null "$BASE/api/config" && break; sleep 2; done  # the server just restarted
echo "$(date '+%F %T') server now shows: $(curl -fsS -X POST -H "X-Refresh-Key: $KEY" "$BASE/api/app/android/refresh")"
