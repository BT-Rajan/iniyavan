# The Android app's newest release: found on GitHub at most once a day, shown on the home page and in the app
import httpx
import main

REL = [{"tag_name": "v9", "draft": False, "prerelease": False, "assets": [{"name": "x.apk", "browser_download_url": "u0"}]},  # not the app's tag
       {"tag_name": "android-v1.0.8", "draft": True, "prerelease": False, "assets": [{"name": "z.apk", "browser_download_url": "u1"}]},
       {"tag_name": "android-v1.0.7", "draft": False, "prerelease": False, "published_at": "2026-10-24T03:20:00Z",
        "assets": [{"name": "notes.txt"}, {"name": "zigora-1.0.7.apk", "browser_download_url": "https://github.com/o/r/releases/download/android-v1.0.7/zigora-1.0.7.apk", "size": 4000000}]}]

class Res:
    def __init__(self, data, code=200): self.data, self.code = data, code
    def raise_for_status(self):
        if self.code >= 400: raise httpx.HTTPStatusError("x", request=None, response=None)
    def json(self): return self.data

def test_the_newest_published_apk_is_found_and_asked_for_once_a_day(env, monkeypatch):
    calls = []
    monkeypatch.setattr(main.httpx, "get", lambda url, **k: calls.append(url) or Res(REL))
    main.android_seen.update(at=-1e12, release=None)
    r = env.c.get("/api/app/android"); assert r.status_code == 200  # no sign-in needed: the home page asks
    assert r.json() == {"version": "1.0.7", "code": 7, "date": "2026-10-24T03:20:00Z", "size": 4000000,
                        "url": "https://github.com/o/r/releases/download/android-v1.0.7/zigora-1.0.7.apk"}
    assert calls == [f"https://api.github.com/repos/{main.ANDROID_REPO}/releases"]
    env.c.get("/api/app/android"); assert len(calls) == 1  # the day's answer is kept
    t = main.android_seen["at"]
    assert main.android_release(t + main.ANDROID_CHECK - 1)["code"] == 7 and len(calls) == 1
    main.android_release(t + main.ANDROID_CHECK + 1); assert len(calls) == 2  # a day later it looks again

def test_when_github_cannot_be_reached_the_last_answer_stays(env, monkeypatch):
    main.android_seen.update(at=-1e12, release=None)
    monkeypatch.setattr(main.httpx, "get", lambda url, **k: Res(REL)); main.android_release(1000.0)
    def down(url, **k): raise httpx.ConnectError("down")
    monkeypatch.setattr(main.httpx, "get", down)
    assert main.android_release(1000.0 + main.ANDROID_CHECK + 1)["version"] == "1.0.7"
    main.android_seen.update(at=-1e12, release=None)
    assert env.c.get("/api/app/android").json() == {"version": None}  # nothing found yet: the page and the app offer no download
    main.android_seen.update(at=-1e12, release=None); assert main.android_release(5000.0) is None
    calls = []; monkeypatch.setattr(main.httpx, "get", lambda url, **k: calls.append(1) or Res(REL))
    main.android_release(5000.0 + main.ANDROID_RETRY - 1); assert calls == []  # after a failure it waits an hour, not a day
    main.android_release(5000.0 + main.ANDROID_RETRY + 1); assert calls == [1]
