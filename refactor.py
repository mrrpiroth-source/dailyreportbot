import re

def refactor_bot():
    with open('bot.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update start_bot
    start_bot_replacement = """
async def start_bot():
    \"\"\"Main startup routine for the Telegram client.\"\"\"
    await start_health_check_server()

    if not config.API_ID or not config.API_HASH:
        print("Missing API_ID / API_HASH")
        return
        
    if not config.BOT_TOKEN:
        print("❌ កំហុស (ERROR): សូមបញ្ចូល TELEGRAM_BOT_TOKEN នៅក្នុង Render Environment Variables!")
        return

    user_client = TelegramClient(StringSession(config.USER_SESSION_STRING), config.API_ID, config.API_HASH)
    bot_client = TelegramClient('bot_session_file', config.API_ID, config.API_HASH)

    print("🚀 កំពុងដំណើរការ Hybrid Bot (Userbot + Bot Account)...")

    await user_client.connect()
    if not await user_client.is_user_authorized():
        print("❌ Invalid USER_SESSION_STRING")
        import sys
        sys.exit(1)

    await bot_client.start(bot_token=config.BOT_TOKEN)

    me_user = await user_client.get_me()
    me_bot = await bot_client.get_me()
    
    print(f"✅ Userbot Connected: @{me_user.username}")
    print(f"✅ Official Bot Connected: @{me_bot.username}")
    
    if me_user.id not in config.ADMIN_USER_IDS:
        config.ADMIN_USER_IDS.append(me_user.id)
        config.MASTER_BOT_OWNER_ID = me_user.id

    # Store global bot_client for easy access in handlers
    global _bot_client
    _bot_client = bot_client

    setup_handlers(user_client, bot_client, bot_id=me_bot.id)
    scheduler = setup_scheduler(bot_client)
    scheduler.start()

    try:
        from telethon.tl.functions.bots import SetBotCommandsRequest
        from telethon.tl.types import BotCommand, BotCommandScopeDefault
        await bot_client(SetBotCommandsRequest(
            scope=BotCommandScopeDefault(),
            lang_code="",
            commands=[
                BotCommand(command="today", description="📊 មើលរបាយការណ៍លក់ថ្ងៃនេះ"),
                BotCommand(command="yesterday", description="📅 របាយការណ៍ម្សិលមិញ"),
                BotCommand(command="week", description="🗓 របាយការណ៍ ៧ថ្ងៃចុងក្រោយ"),
                BotCommand(command="month", description="📈 របាយការណ៍ប្រចាំខែ"),
                BotCommand(command="year", description="📆 របាយការណ៍ប្រចាំឆ្នាំ"),
                BotCommand(command="admin", description="👑 ផ្ទាំងបញ្ជាម្ចាស់ Bot"),
            ]
        ))
    except Exception as e:
        logger.debug(f"Could not register Bot Commands: {e}")

    if config.SYNC_ON_STARTUP and config.MONITOR_CHAT_ID:
        from sync_history import sync_previous_messages
        asyncio.create_task(sync_previous_messages(user_client, config.MONITOR_CHAT_ID, limit=config.SYNC_LIMIT))

    import asyncio
    await asyncio.gather(
        user_client.run_until_disconnected(),
        bot_client.run_until_disconnected()
    )
"""
    # Replace start_bot function completely
    content = re.sub(r'async def start_bot\(\):.*?async def start_health_check_server\(\):', start_bot_replacement + '\nasync def start_health_check_server():', content, flags=re.DOTALL)

    # 2. Update setup_handlers signature
    content = content.replace('def setup_handlers(client: TelegramClient, bot_id: int = 0):', 'def setup_handlers(user_client: TelegramClient, bot_client: TelegramClient, bot_id: int = 0):')

    # 3. Fix events registering
    content = content.replace('@client.on(events.CallbackQuery)', '@bot_client.on(events.CallbackQuery)')
    content = content.replace('@client.on(events.NewMessage(incoming=True, outgoing=True))', '@bot_client.on(events.NewMessage(incoming=True, outgoing=True))')

    # We need user_client to handle the KHQR parsing because bot_client can't see other bots.
    # So we must listen to NewMessage on BOTH, or explicitly split them.
    # Actually, the simplest way is to register `message_listener` on BOTH clients!
    # And inside `_process_message`, we distinguish them.
    # But wait, `event.client` refers to the client that received the message.
    
    # We will register `message_listener` to both:
    dual_listener = """    @user_client.on(events.NewMessage(incoming=True, outgoing=True))
    @bot_client.on(events.NewMessage(incoming=True, outgoing=True))
    async def message_listener"""
    content = content.replace('@bot_client.on(events.NewMessage(incoming=True, outgoing=True))\n    async def message_listener', dual_listener)
    
    # Inside _process_message, if event.client is bot_client, ignore KHQR parsing.
    # If event.client is user_client, ignore commands.
    
    # 4. Replace `safe_edit_or_respond(event, ...)` with `event.client.send_message(...)` where appropriate, 
    # but wait, `event.client` for KHQR is `user_client`, which CANNOT send buttons.
    # So we must use `bot_client.send_message` globally inside KHQR handler!
    # Let's replace `client` with `bot_client` in `notify_owner_of_access_request` inside `setup_handlers`.
    content = content.replace('notify_owner_of_access_request(\n                        client=client,', 'notify_owner_of_access_request(\n                        client=bot_client,')
    
    # Replace `safe_edit_or_respond(event` with `safe_edit_or_respond(event, bot_client` ?
    # Let's just modify `safe_edit_or_respond` and `safe_reply` to take `bot_client` as a fallback.
    
    with open('bot_new.py', 'w', encoding='utf-8') as f:
        f.write(content)
        
if __name__ == "__main__":
    refactor_bot()
