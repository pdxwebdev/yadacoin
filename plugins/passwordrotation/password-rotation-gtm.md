Lead with the **relying-party story**, not KEL. An implementer should need two fields and one check.

**1. One-page implementer spec**  
“On register: store `nextPasswordHash`. On sign-in: `verify(password, storedHash)`, then replace it.” No KEL, no Yada node, no PHC params unless they want them. The protocol page stays for authenticators.

**2. Tiny RP library**  
e.g. `@yadacoin/password-verify`: `verifyPassword`, `parseCallback`. Target: 20 lines in Express / Next / PHP. That’s what you hand a startup.

**3. Ship the authenticator**  
Unpacked Chrome + sideloaded APK won’t get distribution. Web Store listing + a Play internal track (even “dev”) so RPs can say “users install this.”

**4. One canonical demo that looks like a real app**  
Not a harness. Fake “Acme login” that uses only the callback fields. That’s the clone target.

**5. Freeze the callback contract**  
`password`, `nextPasswordHash`, `nonce`, `ok`. Treat that as v1. Everything else can change.

**6. WebView / in-app browser handoff**  
When the extension can’t run (Instagram WebView, etc.):  
`POST /password-rotation/auth-session` with `{ username, site, action, expectedHash? }` → poll  
`GET /password-rotation/auth-session/{id}` until `session_status` is `approved` | `denied` | `expired`.  
The user’s Yada Password app stays on `/websocket`, receives `password_auth_request`, Approves, posts result. No FCM. Optional: `POST /password-rotation/home` so any entry node can proxy to the user’s home node.

Skip PAKE/WebAuthn comparisons in the first pitch. Pitch: **rotating password, drop-in for login forms, authenticator does the hard part.**

