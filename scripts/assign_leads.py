#!/usr/bin/env python3
"""
Round-robin lead assignment by team.
- China leads (addressCountry = 中国/China) -> 内贸组
- Non-China leads -> 外贸组
"""

import requests
import json
import sys

BASE = "http://localhost:8080/api/v1"
API_KEY = "3f0f4ef281df645acdc6e30bf3d406ac"
HEADERS = {"X-Api-Key": API_KEY, "Content-Type": "application/json"}

# Team IDs from setup
TEAMS = {
    "外贸": "f2abdbc4da34cf06e",
    "内贸": "e97c6626987f655ba",
}

def get_all_users():
    """Get all users with their teams and IDs."""
    users = []
    offset = 0
    while True:
        resp = requests.get(f"{BASE}/User?offset={offset}&maxSize=50", headers=HEADERS)
        data = resp.json()
        for u in data.get("list", []):
            users.append({
                "id": u["id"],
                "userName": u["userName"],
                "type": u.get("type", "regular"),
                "teamsIds": [t["id"] if isinstance(t, dict) else t for t in u.get("teamsIds", [])],
                "rolesIds": [r["id"] if isinstance(r, dict) else r for r in u.get("rolesIds", [])],
            })
        if len(data.get("list", [])) < 50:
            break
        offset += 50
    return users

def get_team_members(users, team_id):
    """Get members of a specific team (non-admin only)."""
    return [u for u in users if team_id in u.get("teamsIds", []) and u["type"] != "admin"]

def get_unassigned_leads():
    """Get all leads without assignedUser."""
    leads = []
    offset = 0
    while True:
        resp = requests.get(
            f"{BASE}/Lead?offset={offset}&maxSize=100&select=id,name,addressCountry,assignedUserId",
            headers=HEADERS
        )
        data = resp.json()
        for l in data.get("list", []):
            if not l.get("assignedUserId") and not l.get("assignedUserId"):
                country = l.get("addressCountry") or ""
                leads.append({
                    "id": l["id"],
                    "name": l.get("name", ""),
                    "country": country,
                })
        if len(data.get("list", [])) < 100:
            break
        offset += 100
    return leads

def is_china(country):
    """Check if country is China."""
    if not country:
        return False
    c = country.strip().lower()
    return c in ("中国", "china", "cn", "chinese", "zhongguo", "mainland china", "prc", "pr china")

def count_assigned(user_id):
    """Count leads assigned to a user."""
    resp = requests.get(
        f"{BASE}/Lead?maxSize=0&where[0][type]=equals&where[0][attribute]=assignedUserId&where[0][value]={user_id}",
        headers=HEADERS
    )
    return resp.json().get("total", 0)

def assign_lead(lead_id, user_id, team_id):
    """Assign a lead to a user and team."""
    try:
        requests.put(
            f"{BASE}/Lead/{lead_id}",
            headers=HEADERS,
            json={
                "assignedUserId": user_id,
                "teamsIds": [team_id],
            }
        )
        return True
    except Exception as e:
        print(f"  ERROR assigning {lead_id}: {e}")
        return False

def main():
    print("=== Lead Round-Robin Assignment ===\n")

    # 1. Get all users
    print("Fetching users...")
    users = get_all_users()
    print(f"  Total: {len(users)} users")

    # 2. Get team members
    waimao_members = get_team_members(users, TEAMS["外贸"])
    neimao_members = get_team_members(users, TEAMS["内贸"])

    print(f"  外贸组 members: {[u['userName'] for u in waimao_members]}")
    print(f"  内贸组 members: {[u['userName'] for u in neimao_members]}")

    # 3. Get unassigned leads
    print("\nFetching unassigned leads...")
    unassigned = get_unassigned_leads()
    print(f"  Unassigned: {len(unassigned)} leads")

    # 4. Separate by country
    china_leads = [l for l in unassigned if is_china(l["country"])]
    foreign_leads = [l for l in unassigned if not is_china(l["country"])]

    print(f"  China leads: {len(china_leads)}")
    print(f"  Foreign leads: {len(foreign_leads)}")

    # 5. Assign foreign leads to 外贸组
    if foreign_leads and waimao_members:
        print(f"\nAssigning {len(foreign_leads)} foreign leads to 外贸组...")
        # Count current assignments
        member_counts = {u["id"]: count_assigned(u["id"]) for u in waimao_members}
        members_sorted = sorted(member_counts.items(), key=lambda x: x[1])
        member_ids = [m[0] for m in members_sorted]

        assigned = 0
        for lead in foreign_leads:
            idx = assigned % len(member_ids)
            uid = member_ids[idx]
            if assign_lead(lead["id"], uid, TEAMS["外贸"]):
                assigned += 1
            if assigned % 50 == 0:
                print(f"  {assigned}/{len(foreign_leads)} assigned...")
        print(f"  Done: {assigned} foreign leads assigned")

    # 6. Assign China leads to 内贸组
    if china_leads and neimao_members:
        print(f"\nAssigning {len(china_leads)} China leads to 内贸组...")
        member_counts = {u["id"]: count_assigned(u["id"]) for u in neimao_members}
        members_sorted = sorted(member_counts.items(), key=lambda x: x[1])
        member_ids = [m[0] for m in members_sorted]

        assigned = 0
        for lead in china_leads:
            idx = assigned % len(member_ids)
            uid = member_ids[idx]
            if assign_lead(lead["id"], uid, TEAMS["内贸"]):
                assigned += 1
        print(f"  Done: {assigned} China leads assigned")

    # 7. Summary
    print("\n=== Assignment Summary ===")
    for user in waimao_members + neimao_members:
        count = count_assigned(user["id"])
        print(f"  {user['userName']:15s}: {count} leads")

    # Verify no unassigned remain
    remaining = len(get_unassigned_leads())
    print(f"\n  Unassigned remaining: {remaining}")

if __name__ == "__main__":
    main()
