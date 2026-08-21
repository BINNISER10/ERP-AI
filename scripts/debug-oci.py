#!/usr/bin/env python3
"""Debug OCI config and try to connect."""

import oci
import os

# Try loading from default config file
config_locations = [
    os.path.expanduser("~/.oci/config"),
    "terraform/oci_api_key.pem",
]

print("=== Checking config locations ===")
for loc in config_locations:
    print(f"  {loc}: exists={os.path.exists(loc)}")

# Manual config
config = {
    "user": "ocid1.user.oc1..aaaaaaaaibvc2fji2muxbaszrjji3sjhrvstrvi65rxmseqvsrrjsyo2moja",
    "fingerprint": "37:fd:2d:a2:5d:cf:53:07:5b:b9:16:81:1e:88:04:31",
    "key_file": "terraform/oci_api_key.pem",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaa4ka62v2faxgd6lvy6u3lnebthjfrmvplfhvx4cmjx6vwz6pwtqna",
    "region": "ca-montreal-1",
}

print("\n=== Config ===")
for k, v in config.items():
    print(f"  {k}: {v}")

print(f"\n  Key file exists: {os.path.exists(config['key_file'])}")

if os.path.exists(config['key_file']):
    with open(config['key_file'], 'r') as f:
        content = f.read()
    print(f"  Key file starts with: {content[:30]}...")
    print(f"  Key file length: {len(content)}")

print("\n=== Validating config ===")
try:
    oci.config.validate_config(config)
    print("[OK] Config is valid!")
except Exception as e:
    print(f"[ERROR] Config validation failed: {e}")

print("\n=== Trying to connect ===")
try:
    identity = oci.identity.IdentityClient(config)
    # Try to get the user
    user = identity.get_user(config["user"]).data
    print(f"[OK] Connected! User: {user.name} ({user.email})")
except Exception as e:
    print(f"[ERROR] Connection failed: {e}")
    
    # Try with different key file paths
    for path in ["oci_api_key.pem", "terraform/oci_api_key.pem", os.path.join(os.getcwd(), "terraform", "oci_api_key.pem")]:
        config2 = config.copy()
        config2["key_file"] = path
        if os.path.exists(path):
            print(f"\n  Trying with key_file={path}...")
            try:
                identity = oci.identity.IdentityClient(config2)
                user = identity.get_user(config2["user"]).data
                print(f"  [OK] Connected with {path}! User: {user.name}")
                break
            except Exception as e2:
                print(f"  [ERROR] {e2}")
