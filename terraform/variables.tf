variable "tenancy_ocid" {
  description = "Oracle Cloud Tenancy OCID"
  type        = string
}

variable "user_ocid" {
  description = "Oracle Cloud User OCID"
  type        = string
}

variable "compartment_ocid" {
  description = "Oracle Cloud Compartment OCID (can be the same as tenancy_ocid)"
  type        = string
}

variable "fingerprint" {
  description = "API key fingerprint"
  type        = string
}

variable "private_key_path" {
  description = "Path to the OCI API private key file (.pem)"
  type        = string
}

variable "region" {
  description = "Oracle Cloud region (e.g., me-jeddah-1, eu-frankfurt-1, us-ashburn-1)"
  type        = string
}

variable "ssh_public_key" {
  description = "SSH public key to authorize on the instance"
  type        = string
}

variable "ssh_allowed_cidrs" {
  description = "CIDR block(s) allowed to reach SSH. MUST be restricted to your operator IP (e.g. 1.2.3.4/32)."
  type        = string
  default     = "0.0.0.0/0"
}

variable "instance_shape" {
  description = "Compute shape. VM.Standard.A1.Flex is Always Free on ARM."
  type        = string
  default     = "VM.Standard.A1.Flex"
}

variable "instance_ocpus" {
  description = "Number of OCPUs"
  type        = number
  default     = 4
}

variable "instance_memory_in_gbs" {
  description = "Memory in GB"
  type        = number
  default     = 12
}

variable "boot_volume_size" {
  description = "Boot volume size in GB"
  type        = number
  default     = 100
}
