"""
Permission definitions and default role mappings.
"""

PERMISSIONS = [
    "tools:read",
    "tools:install",
    "dashboard:edit",
    "tickets:create",
    "tickets:manage",
    "team:invite",
    "settings:write",
    "audit:read",
    "automations:read",
    "automations:manage",
    "kyc:submit",
    "kyc:review",
    "users:read",
    "users:write"
]

ROLE_PERMISSIONS = {
    "owner": PERMISSIONS,
    "admin": PERMISSIONS,
    "manager": [
        "tools:read",
        "tools:install",
        "dashboard:edit",
        "tickets:create",
        "tickets:manage",
        "team:invite",
        "settings:write",
        "audit:read",
        "automations:read",
        "automations:manage",
        "kyc:submit",
        "users:read"
    ],
    "agent": [
        "tools:read",
        "dashboard:edit",
        "tickets:create",
        "tickets:manage",
        "automations:read",
        "kyc:submit"
    ],
    "viewer": [
        "tools:read",
        "automations:read"
    ],
    "system_admin": PERMISSIONS
}

ROLE_DESCRIPTIONS = {
    "owner": "Tenant owner with full access.",
    "admin": "Tenant admin with full access.",
    "manager": "Manager with team and operations access.",
    "agent": "Agent with operational access.",
    "viewer": "Read-only access to dashboards and tools.",
    "system_admin": "System-wide administrator."
}
