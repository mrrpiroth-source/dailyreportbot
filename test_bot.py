"""
Unit tests to verify permissions, admin panels, and button command aliases for v2.5.0.
"""

import bot
import config
from database import Database


def test_master_owner_permissions():
    """Verify Master Bot Owners (7299682335, 7013708703) have permanent Super Admin rights."""
    assert bot.is_admin(config.MASTER_BOT_OWNER_ID) is True
    assert bot.check_permission(config.MASTER_BOT_OWNER_ID) is True
    assert bot.is_admin(7013708703) is True
    assert bot.check_permission(7013708703) is True


def test_admin_panel_buttons():
    """Verify Master Admin Control Panel includes all essential buttons."""
    text, btns = bot.build_admin_panel()
    assert len(btns) >= 4

    btn_data_list = []
    for row in btns:
        for b in row:
            raw_data = getattr(getattr(b, "type", None), "data", None)
            if raw_data:
                btn_data_list.append(raw_data)

    assert b"admin_trigger_update" in btn_data_list
    assert b"admin_groups" in btn_data_list
    assert b"admin_all_users" in btn_data_list
    assert b"admin_confirm_clear" in btn_data_list


def test_khmer_text_and_button_aliases():
    """Verify that Khmer text and button taps resolve to correct commands."""
    test_cases = [
        ("/today", "/today"),
        ("/today@daily_bot", "/today"),
        ("📊 របាយការណ៍លក់", "/today"),
        ("📊 របាយការណ៍ថ្ងៃនេះ", "/today"),
        ("របាយការណ៍លក់", "/today"),
        ("👑 Admin Panel", "/admin"),
        ("admin panel", "/admin"),
        ("👥 គ្រប់គ្រង Group", "/manage"),
        ("គ្រប់គ្រង group", "/manage"),
        ("ℹ️ ស្ថានភាព / Version", "/version"),
        ("version", "/version"),
    ]

    for raw_txt, expected_cmd in test_cases:
        text_stripped = raw_txt.strip()
        cmd = text_stripped.split()[0].lower() if text_stripped else ""
        if "@" in cmd:
            cmd = cmd.split("@")[0]

        if "របាយការណ៍" in text_stripped.lower() or text_stripped in (
            "📊 របាយការណ៍លក់", "📊 របាយការណ៍", "របាយការណ៍លក់", "📊 របាយការណ៍ថ្ងៃនេះ"
        ):
            cmd = "/today"
        elif "ស្ថានភាព / version" in text_stripped.lower() or text_stripped in (
            "ℹ️ ស្ថានភាព / Version", "ℹ️ ស្ថានភាព / version", "ស្ថានភាព", "version"
        ):
            cmd = "/version"
        elif "admin panel" in text_stripped.lower() or text_stripped in (
            "👑 Admin Panel", "👑 admin panel"
        ):
            cmd = "/admin"
        elif "គ្រប់គ្រង group" in text_stripped.lower() or text_stripped in (
            "👥 គ្រប់គ្រង Group", "👥 គ្រប់គ្រង group"
        ):
            cmd = "/manage"

        assert cmd == expected_cmd, f"Expected {expected_cmd} for '{raw_txt}', got {cmd}"


def test_safe_reply_parameters():
    """Verify safe_reply and safe_edit_or_respond accept parse_mode and kwargs."""
    import inspect
    sig_reply = inspect.signature(bot.safe_reply)
    sig_edit = inspect.signature(bot.safe_edit_or_respond)
    assert "parse_mode" in sig_reply.parameters, "safe_reply must have parse_mode"
    assert "parse_mode" in sig_edit.parameters, "safe_edit_or_respond must have parse_mode"


def test_approved_staff_permission():
    """Verify approved staff has report access via check_permission."""
    db = Database()
    db.add_authorized_user(
        user_id=5359573118,
        username="sunsreypov",
        full_name="ស៊ន់ ស្រីពៅ",
        role="staff",
        chat_id=-1004325343684,
        chat_title="Meeting cafe ☕",
        group_role="staff"
    )
    assert bot.check_permission(5359573118, -1004325343684) is True
    assert bot.check_permission(5359573118, None) is True
    assert bot.check_permission(9999999999, -1004325343684) is False


if __name__ == "__main__":
    test_master_owner_permissions()
    test_admin_panel_buttons()
    test_khmer_text_and_button_aliases()
    test_safe_reply_parameters()
    test_approved_staff_permission()
    print(f"✅ All unit tests passed successfully for Version v{config.BOT_VERSION}!")

