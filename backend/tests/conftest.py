import os

# BlockSikka default test authentication mode
#
# Existing API regression tests focus on business
# behavior. Dedicated auth/RBAC tests explicitly
# enable authentication per test.
os.environ.setdefault(
    "BLOCKSIKKA_AUTH_REQUIRED",
    "false",
)

