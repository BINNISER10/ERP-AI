output "nexus_server_public_ip" {
  description = "Public IP of the Nexus ERP server"
  value       = oci_core_instance.nexus_erp.public_ip
}

output "nexus_vcn_id" {
  description = "VCN ID"
  value       = oci_core_vcn.nexus_vcn.id
}
