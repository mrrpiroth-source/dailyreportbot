import re

def patch_bot():
    with open('bot.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the top of _process_message
    target = """    async def _process_message(event: events.NewMessage.Event):
        print(f"DEBUG: ទទួលសារ! Text: {event.raw_text!r} | Out: {getattr(event, 'out', False)} | Sender: {event.sender_id} | Chat: {event.chat_id}")"""

    replacement = """    async def _process_message(event: events.NewMessage.Event):
        # HYBRID ROUTING
        is_bot = (event.client == bot_client)
        is_cmd = event.raw_text and event.raw_text.startswith(("/", "."))
        
        # 1. Userbot ONLY handles KHQR parsing (no commands)
        if not is_bot and is_cmd:
            return
            
        # 2. Bot Account ONLY handles commands & buttons (no KHQR parsing, as it can't read bots anyway)
        if is_bot and not is_cmd:
            return
            
        print(f"DEBUG: [{ 'BOT' if is_bot else 'USER' }] ទទួលសារ! Text: {event.raw_text!r} | Out: {getattr(event, 'out', False)} | Sender: {event.sender_id} | Chat: {event.chat_id}")"""

    if target in content:
        content = content.replace(target, replacement)
    
    # Also, the KHQR messages need to be replied to via the bot_client, not user_client!
    # Wait, does KHQR reply? 
    # Ah! In bot.py line 1155, that's callback query. KHQR parsing DOES NOT send replies to the group by default.
    # It only sends if there is a callback query or command!
    # Wait, earlier I saw:
    # safe_reply(event, ...) for access denied.
    # safe_reply(event, ...) for /today.
    # What about KHQR parsing? It just does: db.insert_transaction(...) and no reply!
    # Let me check if there's any `safe_reply` for KHQR. No, KHQR just inserts silently.
    
    # Wait, does `safe_reply` use `bot_client.send_message` if event.client is user_client?
    # Because if `user_client` needs to send something (like `notify_owner_of_access_request`), it should use `bot_client`.
    # I already replaced `client=client` with `client=bot_client` for `notify_owner_of_access_request`.

    with open('bot.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    patch_bot()
