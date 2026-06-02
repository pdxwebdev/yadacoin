"""microsoft_handlers.py — Microsoft Graph agent handler."""
import json

from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM

from ..agent.handlers import AgentChatHandler
from .api import (
    _msgraph_api_delete,
    _msgraph_api_get,
    _msgraph_api_patch,
    _msgraph_api_post,
)


class MicrosoftExecuteHandler(AgentChatHandler):
    """
    POST /ai-agent-auth/api/microsoft/execute

    Verifies a KEL-backed VP (produced after a key-rotation approval for a
    Microsoft write action) then executes the requested MS Graph API call.

    Body (JSON)
    -----------
    public_key       : hex compressed secp256k1 key (agent/provisioned key)
    challenge        : hex string from GET /ai-agent-auth/api/challenge
    vp               : W3C VP object with YadaKELStatus scope "MicrosoftWriteAction"
    nonce            : Microsoft OAuth session nonce (session to mark as used)
    token_enc_key    : hex sha256 of the pre-rotation private key (32-byte key)
    encrypted_token  : hex AES-256-GCM ciphertext (access_token + auth tag)
    iv               : hex 12-byte GCM initialisation vector
    action           : one of send_email | push_todo | add_todo_task |
                       complete_todo_task | delete_todo_task
    scope            : dict of action-specific parameters (to, subject, body,
                       task_title, top, etc.)
    llm              : LLM config dict (provider/model/api_key/...) — required
                       for push_todo (email-to-task extraction)
    """

    async def post(self):
        try:
            body = json.loads(self.request.body)
        except Exception:
            self.set_status(400)
            return self.render_as_json({"error": "invalid JSON body"})

        public_key = (body.get("public_key") or "").strip()
        challenge = (body.get("challenge") or "").strip()
        vp = body.get("vp")
        nonce = (body.get("nonce") or "").strip()
        action = (body.get("action") or "").strip()
        scope = body.get("scope") or {}
        llm_cfg = body.get("llm") or {}
        token_enc_key_hex = (body.get("token_enc_key") or "").strip()
        encrypted_token_hex = (body.get("encrypted_token") or "").strip()
        token_iv_hex = (body.get("iv") or "").strip()

        if not public_key or not challenge or not vp or not action:
            self.set_status(400)
            return self.render_as_json(
                {"error": "public_key, challenge, vp, and action are required"}
            )

        _MS_WRITE_ACTIONS = {
            "send_email",
            "push_todo",
            "add_todo_task",
            "complete_todo_task",
            "delete_todo_task",
        }
        if action not in _MS_WRITE_ACTIONS:
            self.set_status(400)
            return self.render_as_json({"error": f"Unsupported action: {action!r}"})

        # ── Verify the VP against the on-chain KEL ───────────────────────────
        try:
            auth = await _validator.validate_vp(public_key, challenge, vp)
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"error": str(exc)})

        try:
            AgentAuthValidator.enforce_scope(auth, services=["MicrosoftWriteAction"])
        except AuthError as exc:
            self.set_status(exc.http_status)
            return self.render_as_json({"error": str(exc), "scope": auth.scope})

        # ── Resolve the Microsoft access token ───────────────────────────────
        # Preferred path: browser provides token_enc_key + encrypted_token + iv.
        # The access_token was AES-256-GCM encrypted at connect time using a key
        # derived from the pre-action private key (sha256(LS_PRIV)).  Once the
        # action rotation completes on the client the key is replaced and the
        # token becomes permanently inaccessible from the browser.
        access_token = ""
        session_doc = None
        if token_enc_key_hex and encrypted_token_hex and token_iv_hex:
            try:
                _key = bytes.fromhex(token_enc_key_hex)
                _iv = bytes.fromhex(token_iv_hex)
                _ct = bytes.fromhex(encrypted_token_hex)
                _aesgcm = _AESGCM(_key)
                access_token = _aesgcm.decrypt(_iv, _ct, None).decode("utf-8")
            except Exception:
                self.set_status(403)
                return self.render_as_json(
                    {"error": "Token decryption failed — key may have rotated"}
                )
        else:
            # Legacy fallback: look up plaintext access_token by session nonce.
            if not nonce:
                self.set_status(400)
                return self.render_as_json(
                    {"error": "nonce or encrypted token credentials required"}
                )
            try:
                session_doc = (
                    await self.config.mongo.async_db.web2_oauth_sessions.find_one(
                        {
                            "nonce": nonce,
                            "provider": "microsoft",
                            "status": "authorized",
                        }
                    )
                )
            except Exception:
                self.set_status(500)
                return self.render_as_json({"error": "session store error"})
            if not session_doc:
                self.set_status(404)
                return self.render_as_json(
                    {"error": "Microsoft session not found or not authorized"}
                )
            access_token = session_doc.get("access_token", "")
            if not access_token:
                self.set_status(403)
                return self.render_as_json(
                    {"error": "No access token for this session"}
                )

        if not access_token:
            self.set_status(403)
            return self.render_as_json({"error": "No access token available"})

        # ── LLM settings (needed for push_todo) ──────────────────────────────
        provider = (llm_cfg.get("provider") or "ollama").lower().strip()
        model = (llm_cfg.get("model") or "").strip() or self._DEFAULT_MODELS.get(
            provider, "gpt-4o-mini"
        )
        api_key = (llm_cfg.get("api_key") or "").strip()
        ollama_host = (llm_cfg.get("ollama_host") or "http://localhost:11434").strip()
        base_url = (llm_cfg.get("base_url") or "").strip()

        # ── Execute the action ────────────────────────────────────────────────
        try:
            if action == "send_email":
                to_addr = (scope.get("to") or "").strip()
                subject = (scope.get("subject") or "").strip()
                email_body = (scope.get("body") or "").strip()
                if not (to_addr and subject and email_body):
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "send_email requires to, subject, and body in scope"}
                    )
                await _msgraph_api_post(
                    access_token,
                    "/me/sendMail",
                    {
                        "message": {
                            "subject": subject,
                            "body": {"contentType": "Text", "content": email_body},
                            "toRecipients": [{"emailAddress": {"address": to_addr}}],
                        },
                        "saveToSentItems": True,
                    },
                )
                return self.render_as_json(
                    {"status": True, "type": "sent", "to": to_addr, "subject": subject}
                )

            elif action == "add_todo_task":
                task_title = (scope.get("task_title") or "").strip()
                if not task_title:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "add_todo_task requires task_title in scope"}
                    )
                lists_resp = await _msgraph_api_get(access_token, "/me/todo/lists", {})
                todo_lists = lists_resp.get("value", [])
                default_list = next(
                    (
                        l
                        for l in todo_lists
                        if l.get("wellknownListName") == "defaultList"
                    ),
                    todo_lists[0] if todo_lists else None,
                )
                if not default_list:
                    default_list = await _msgraph_api_post(
                        access_token, "/me/todo/lists", {"displayName": "Tasks"}
                    )
                list_id = default_list.get("id", "")
                list_name = default_list.get("displayName", "Tasks")
                await _msgraph_api_post(
                    access_token,
                    f"/me/todo/lists/{list_id}/tasks",
                    {"title": task_title[:255]},
                )
                return self.render_as_json(
                    {
                        "status": True,
                        "type": "task_added",
                        "list_name": list_name,
                        "task": task_title,
                        "reply": f'Done! Added "{task_title}" to your "{list_name}" list.',
                    }
                )

            elif action == "complete_todo_task":
                task_title = (scope.get("task_title") or "").strip()
                if not task_title:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "complete_todo_task requires task_title in scope"}
                    )
                lists_resp = await _msgraph_api_get(access_token, "/me/todo/lists", {})
                todo_lists = lists_resp.get("value", [])
                matched_list_id = matched_list_name = matched_task_id = None
                search_lower = task_title.lower()
                for tl in todo_lists:
                    list_id = tl.get("id", "")
                    tasks_resp = await _msgraph_api_get(
                        access_token,
                        f"/me/todo/lists/{list_id}/tasks",
                        {"$top": 100, "$filter": "status ne 'completed'"},
                    )
                    for task in tasks_resp.get("value", []):
                        if search_lower in (task.get("title") or "").lower():
                            matched_list_id = list_id
                            matched_list_name = tl.get("displayName", "Tasks")
                            matched_task_id = task.get("id", "")
                            task_title = task.get("title", task_title)
                            break
                    if matched_task_id:
                        break
                if not matched_task_id:
                    return self.render_as_json(
                        {
                            "status": False,
                            "error": f'No task matching "{task_title}" found.',
                        }
                    )
                await _msgraph_api_patch(
                    access_token,
                    f"/me/todo/lists/{matched_list_id}/tasks/{matched_task_id}",
                    {"status": "completed"},
                )
                return self.render_as_json(
                    {
                        "status": True,
                        "type": "task_completed",
                        "list_name": matched_list_name,
                        "task": task_title,
                        "reply": f'Done! Marked "{task_title}" as complete in "{matched_list_name}".',
                    }
                )

            elif action == "delete_todo_task":
                task_title = (scope.get("task_title") or "").strip()
                if not task_title:
                    self.set_status(400)
                    return self.render_as_json(
                        {"error": "delete_todo_task requires task_title in scope"}
                    )
                lists_resp = await _msgraph_api_get(access_token, "/me/todo/lists", {})
                todo_lists = lists_resp.get("value", [])
                matched_list_id = matched_list_name = matched_task_id = None
                search_lower = task_title.lower()
                for tl in todo_lists:
                    list_id = tl.get("id", "")
                    tasks_resp = await _msgraph_api_get(
                        access_token,
                        f"/me/todo/lists/{list_id}/tasks",
                        {"$top": 100},
                    )
                    for task in tasks_resp.get("value", []):
                        if search_lower in (task.get("title") or "").lower():
                            matched_list_id = list_id
                            matched_list_name = tl.get("displayName", "Tasks")
                            matched_task_id = task.get("id", "")
                            task_title = task.get("title", task_title)
                            break
                    if matched_task_id:
                        break
                if not matched_task_id:
                    return self.render_as_json(
                        {
                            "status": False,
                            "error": f'No task matching "{task_title}" found.',
                        }
                    )
                await _msgraph_api_delete(
                    access_token,
                    f"/me/todo/lists/{matched_list_id}/tasks/{matched_task_id}",
                )
                return self.render_as_json(
                    {
                        "status": True,
                        "type": "task_deleted",
                        "list_name": matched_list_name,
                        "task": task_title,
                        "reply": f'Done! Deleted "{task_title}" from "{matched_list_name}".',
                    }
                )

            elif action == "push_todo":
                pt_top = int(scope.get("top") or 10)
                if pt_top > 25:
                    pt_top = 25
                ptr = await _msgraph_api_get(
                    access_token,
                    "/me/mailFolders/inbox/messages",
                    {
                        "$top": pt_top,
                        "$select": "id,subject,from,receivedDateTime,body",
                        "$orderby": "receivedDateTime desc",
                    },
                )
                pt_items = ptr.get("value", [])
                if not pt_items:
                    return self.render_as_json(
                        {
                            "status": True,
                            "type": "push_todo_empty",
                            "reply": "Your inbox appears to be empty.",
                        }
                    )
                pt_blocks = []
                for idx, m in enumerate(pt_items, 1):
                    body_content = (m.get("body") or {}).get("content", "")
                    body_type = (m.get("body") or {}).get("contentType", "text")
                    if body_type == "html":
                        body_text = _re.sub(r"<[^>]+>", " ", body_content)
                        body_text = " ".join(body_text.split())[:1200]
                    else:
                        body_text = body_content[:1200]
                    em_subj = (m.get("subject") or "(no subject)")[:120]
                    em_from = ((m.get("from") or {}).get("emailAddress") or {}).get(
                        "name", ""
                    ) or ((m.get("from") or {}).get("emailAddress") or {}).get(
                        "address", ""
                    )
                    em_date = (m.get("receivedDateTime") or "")[:10]
                    pt_blocks.append(
                        f"--- Email {idx} ---\nFrom: {em_from}\nSubject: {em_subj}\nDate: {em_date}\n\n{body_text}"
                    )
                pt_instruction = (
                    f"You are a task extraction assistant. Review the following {len(pt_items)} emails "
                    "and extract a concise list of action items the recipient needs to act on. "
                    "Output ONLY a JSON array of strings, where each string is one task title "
                    "(short, under 255 characters). Skip newsletters, automated notifications, and FYI emails. "
                    'Example: ["Reply to John about budget approval", "Submit expense report by Friday"]'
                )
                pt_msgs = _sanitize_messages(
                    [
                        {"role": "system", "content": pt_instruction},
                        {"role": "user", "content": "\n\n".join(pt_blocks)},
                    ]
                )
                task_titles = []
                try:
                    if provider == "ollama":
                        raw_tasks = await self._call_ollama(ollama_host, model, pt_msgs)
                    elif provider == "openai":
                        raw_tasks = await self._call_openai_compat(
                            "https://api.openai.com/v1", model, api_key, pt_msgs
                        )
                    elif provider == "anthropic":
                        raw_tasks = await self._call_anthropic(model, api_key, pt_msgs)
                    elif provider in ("openai_compat", "github_models"):
                        _pt_u = (
                            self._GITHUB_MODELS_BASE_URL
                            if provider == "github_models"
                            else base_url
                        )
                        raw_tasks = await self._call_openai_compat(
                            _pt_u, model, api_key, pt_msgs
                        )
                    else:
                        raw_tasks = "[]"
                    json_match = _re.search(r"\[.*\]", raw_tasks, _re.DOTALL)
                    if json_match:
                        task_titles = json.loads(json_match.group(0))
                        task_titles = [str(t)[:255] for t in task_titles if t]
                except Exception:
                    task_titles = []
                if not task_titles:
                    return self.render_as_json(
                        {
                            "status": True,
                            "type": "push_todo_no_tasks",
                            "reply": "No action items were found in your recent emails.",
                        }
                    )
                lists_resp = await _msgraph_api_get(access_token, "/me/todo/lists", {})
                todo_lists = lists_resp.get("value", [])
                default_list = next(
                    (
                        l
                        for l in todo_lists
                        if l.get("wellknownListName") == "defaultList"
                    ),
                    todo_lists[0] if todo_lists else None,
                )
                if not default_list:
                    default_list = await _msgraph_api_post(
                        access_token,
                        "/me/todo/lists",
                        {"displayName": "Email Action Items"},
                    )
                list_id = default_list.get("id", "")
                list_name = default_list.get("displayName", "Tasks")
                created = []
                for title in task_titles[:20]:
                    try:
                        await _msgraph_api_post(
                            access_token,
                            f"/me/todo/lists/{list_id}/tasks",
                            {"title": title},
                        )
                        created.append(title)
                    except Exception:
                        pass
                return self.render_as_json(
                    {
                        "status": True,
                        "type": "todo_pushed",
                        "list_name": list_name,
                        "tasks": created,
                        "reply": (
                            f"Done! Added {len(created)} task{'s' if len(created) != 1 else ''} "
                            f'to your "{list_name}" list in Microsoft To Do.'
                        ),
                    }
                )

        except Exception as exc:
            self.set_status(500)
            return self.render_as_json({"error": str(exc)[:300]})
