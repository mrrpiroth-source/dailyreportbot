"""
Test Role-Based Access Control (RBAC) and Security Permissions
"""

import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from database import Database

def test_permissions():
    db = Database("test_auth.db")

    owner_id = 999000111
    staff_id = 888000222
    stranger_id = 777000333

    print("=== TESTING RBAC PERMISSION SYSTEM ===")

    # 1. Initially stranger and staff have no access
    assert not db.is_user_authorized(stranger_id), "Stranger should not be authorized"
    assert not db.is_user_authorized(staff_id), "Staff should not be authorized initially"
    print("✅ [PASS] Unauthorized users correctly blocked.")

    # 2. Add Staff
    ok = db.add_authorized_user(
        user_id=staff_id,
        username="cashier_staff",
        full_name="SOK VISAL",
        role="staff",
        added_by=owner_id
    )
    assert ok, "Failed to add staff"
    assert db.is_user_authorized(staff_id), "Staff should now be authorized"
    assert not db.is_user_authorized(stranger_id), "Stranger must remain unauthorized"
    print("✅ [PASS] Staff authorized successfully.")

    # 3. List users
    users = db.list_authorized_users()
    assert len(users) == 1
    assert users[0]["user_id"] == staff_id
    print(f"✅ [PASS] User list verified: {users[0]['full_name']} ({users[0]['username']}) - {users[0]['role']}")

    # 4. Remove Staff
    removed = db.remove_authorized_user(staff_id)
    assert removed, "Failed to remove staff"
    assert not db.is_user_authorized(staff_id), "Staff should now be revoked"
    print("✅ [PASS] Staff permission revoked successfully.")

    # Clean up test DB
    import os
    if os.path.exists("test_auth.db"):
        os.remove("test_auth.db")

    print("\n🎉 RBAC Security Test 100% Passed!\n")

if __name__ == "__main__":
    test_permissions()
