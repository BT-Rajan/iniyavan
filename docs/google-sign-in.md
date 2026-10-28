# Sign in with Google: setting it up (Cogzidel Technologies)

Cogzidel Technologies owns the Google Cloud project and the OAuth clients. Zigora only needs the **Web client ID**;
no client secret is used or stored (the app checks Google's signed ID token against Google's public keys).

## 1. Google Cloud project
1. Sign in to https://console.cloud.google.com with a Cogzidel Technologies Google Workspace account.
2. Create a project (for example `zigora-sign-in`) under the Cogzidel Technologies organization.

## 2. OAuth consent screen (Google Auth Platform → Branding / Audience)
- App name: **Zigora**. User support email and developer contact: a Cogzidel Technologies address.
- App logo (optional; a logo means Google reviews the branding).
- App home page, privacy policy and terms links on your domain. Authorized domains: the site's domain (for example `example.edu`).
- Audience: **External**. Scopes: only `openid`, `email`, `profile` (non-sensitive, no Google review needed).
- While the app is in *Testing*, only listed test users can sign in. Press **Publish app** before going live.

## 3. Web client (used by the website, and by Android as the "server" client)
Clients → Create client → **Web application**.
- Authorized JavaScript origins: the site's address exactly as people open it, e.g. `https://learn.example.edu`
  (add `http://localhost:5173` for development if wanted). No redirect URIs are needed.
- Copy the client ID (`…apps.googleusercontent.com`).

## 4. Android client
Clients → Create client → **Android**.
- Package name: `app.zigora`.
- SHA-1 of the signing certificate. Make one client per key: the release (upload) key, the Play App Signing key
  (Play Console → App integrity), and the debug key if testing debug builds. Get a SHA-1 with
  `keytool -list -v -keystore <keystore> -alias <alias>`.
- The Android client ID is not entered anywhere; Google matches it from the package and signature. The app asks for a token
  for the **Web** client ID, which it reads from the server.

## 5. Turn it on in Zigora
Either an admin pastes the Web client ID in **Settings → Access → Sign in with Google**, or set it in the server's `.env`:
```
GOOGLE_CLIENT_ID=1234567890-abc.apps.googleusercontent.com
```
(Several IDs may be listed with commas; the first is the one the web page and app use.) Clearing the setting turns it off.

## How accounts are matched
- The first Google sign-in finds the account with the same email and links that Google account to it; after that the link is used,
  even if the Google email changes. A different Google account with the same email is refused.
- An unknown Google email can sign up (no emailed code — Google has checked the email) only when self-registration is on;
  otherwise people are told to ask an admin.
- Passwords keep working. Someone who signed up with Google can set a password with "Forgot password?".
