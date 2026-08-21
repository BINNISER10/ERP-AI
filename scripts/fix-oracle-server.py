#!/usr/bin/env python3
"""Check and restart the Oracle Cloud instance for Nexus ERP."""

import oci
import sys
import time

# Load config from terraform.tfvars
config = {
    "user": "ocid1.user.oc1..aaaaaaaaibvc2fji2muxbaszrjji3sjhrvstrvi65rxmseqvsrrjsyo2moja",
    "fingerprint": "37:fd:2d:a2:5d:cf:53:07:5b:b9:16:81:1e:88:04:31",
    "key_file": "oci_api_key.pem",
    "tenancy": "ocid1.tenancy.oc1..aaaaaaaa4ka62v2faxgd6lvy6u3lnebthjfrmvplfhvx4cmjx6vwz6pwtqna",
    "region": "ca-montreal-1",
}

# Also need compartment
compartment_ocid = "ocid1.tenancy.oc1..aaaaaaaa4ka62v2faxgd6lvy6u3lnebthjfrmvplfhvx4cmjx6vwz6pwtqna"
instance_id = "ocid1.instance.oc1.ca-montreal-1.an4xkljruck3pnicx2msms72jxtkbsfwq4aexmfwevwt53ik2r2r2dd6afoa"

print("[1/5] Loading OCI config...")
try:
    config_obj = oci.config.from_file(file_location="terraform/oci_api_key.pem", profile_name="DEFAULT")
except Exception:
    # Use manual config
    config["key_file"] = "terraform/oci_api_key.pem"
    config_obj = config

# Validate
try:
    oci.config.validate_config(config_obj)
    print("[OK] Config valid")
except Exception as e:
    print(f"[WARN] Config validation: {e}")
    # Try with the file path
    config_obj["key_file"] = "terraform/oci_api_key.pem"
    try:
        oci.config.validate_config(config_obj)
        print("[OK] Config valid with terraform/ prefix")
    except Exception as e2:
        print(f"[ERROR] Config invalid: {e2}")
        sys.exit(1)

print("[2/5] Connecting to OCI Compute client...")
compute = oci.core.ComputeClient(config_obj)

print("[3/5] Fetching instance status...")
try:
    instance = compute.get_instance(instance_id).data
    print(f"  Instance: {instance.display_name}")
    print(f"  State: {instance.lifecycle_state}")
    print(f"  Shape: {instance.shape}")
    print(f"  IP: {instance.primary_vnic.public_ip if hasattr(instance, 'primary_vnic') else 'N/A'}")
except Exception as e:
    print(f"[ERROR] Cannot fetch instance: {e}")
    # Try listing all instances
    print("  Trying to list all instances...")
    try:
        instances = compute.list_instances(compartment_ocid).data
        for inst in instances:
            print(f"  Found: {inst.display_name} | State: {inst.lifecycle_state} | ID: {inst.id}")
    except Exception as e2:
        print(f"[ERROR] Cannot list instances: {e2}")
        sys.exit(1)
    sys.exit(0)

# If stopped, start it
if instance.lifecycle_state.upper() == "STOPPED":
    print("[4/5] Instance is STOPPED. Starting...")
    try:
        compute.instance_action(instance_id, action="START")
        print("[OK] Start command sent")
    except Exception as e:
        print(f"[ERROR] Cannot start: {e}")
        sys.exit(1)
elif instance.lifecycle_state.upper() == "RUNNING":
    print("[4/5] Instance is RUNNING. Trying reboot...")
    # Try soft reboot first
    try:
        compute.instance_action(instance_id, action="SOFTRESET")
        print("[OK] Soft reboot sent")
    except Exception as e:
        print(f"[WARN] Soft reboot failed: {e}, trying hard reset...")
        try:
            compute.instance_action(instance_id, action="RESET")
            print("[OK] Hard reset sent")
        except Exception as e2:
            print(f"[ERROR] Cannot reset: {e2}")
elif instance.lifecycle_state.upper() == "TERMINATED":
    print("[ERROR] Instance is TERMINATED. Cannot recover.")
    print("Need to create a new instance.")
    sys.exit(1)
else:
    print(f"[4/5] Instance state is {instance.lifecycle_state}. Waiting...")

# Wait for instance to be running
print("[5/5] Waiting for instance to be RUNNING...")
for i in range(12):
    time.sleep(10)
    try:
        inst = compute.get_instance(instance_id).data
        state = inst.lifecycle_state
        print(f"  [{i*10}s] State: {state}")
        if state.upper() == "RUNNING":
            # Get VNIC info
            try:
                vnics = compute.list_vnic_attachments(compartment_ocid, instance_id=instance_id).data
                for v in vnics:
                    if v.lifecycle_state == "ATTACHED":
                        vnic = compute.get_vnic(v.vnic_id).data
                        print(f"  Public IP: {vnic.public_ip}")
            except Exception as e:
                print(f"  [WARN] Cannot get VNIC: {e}")
            print("[OK] Instance is RUNNING!")
            break
    except Exception as e:
        print(f"  [{i*10}s] Error: {e}")
else:
    print("[TIMEOUT] Instance did not become RUNNING in 120s")

print("Done.")
