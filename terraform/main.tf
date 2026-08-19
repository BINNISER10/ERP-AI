terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 5.0"
    }
  }
  # Optional remote state with locking (recommended for production):
  # 1. Create an Object Storage bucket, then uncomment:
  # backend "s3" {
  #   bucket     = "nexus-tfstate"
  #   region     = "ap-sydney-1"
  #   key        = "terraform/terraform.tfstate"
  #   endpoint   = "ns-<namespace>.compat.objectstorage.ap-sydney-1.oraclecloud.com"
  #   skip_region_validation      = true
  #   skip_credentials_validation = true
  #   skip_requesting_account_id  = true
  # }
  required_version = ">= 1.2"
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}

resource "oci_core_vcn" "nexus_vcn" {
  compartment_id = var.compartment_ocid
  display_name   = "nexus-vcn"
  cidr_block     = "10.0.0.0/16"
  dns_label      = "nexusvcn"
}

resource "oci_core_internet_gateway" "nexus_igw" {
  compartment_id = var.compartment_ocid
  display_name   = "nexus-igw"
  vcn_id         = oci_core_vcn.nexus_vcn.id
}

resource "oci_core_route_table" "nexus_route_table" {
  compartment_id = var.compartment_ocid
  display_name   = "nexus-route-table"
  vcn_id         = oci_core_vcn.nexus_vcn.id

  route_rules {
    destination       = "0.0.0.0/0"
    network_entity_id = oci_core_internet_gateway.nexus_igw.id
  }
}

resource "oci_core_security_list" "nexus_security_list" {
  compartment_id = var.compartment_ocid
  display_name   = "nexus-security-list"
  vcn_id         = oci_core_vcn.nexus_vcn.id

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH — restrict to operator IP range whenever possible
  ingress_security_rules {
    protocol    = "6"
    source      = var.ssh_allowed_cidrs
    description = "SSH"
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Public web traffic only goes through nginx (HTTP → HTTPS redirect)
  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    description = "HTTP"
    tcp_options {
      min = 80
      max = 80
    }
  }

  ingress_security_rules {
    protocol    = "6"
    source      = "0.0.0.0/0"
    description = "HTTPS"
    tcp_options {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_subnet" "nexus_subnet" {
  compartment_id    = var.compartment_ocid
  display_name      = "nexus-subnet"
  vcn_id            = oci_core_vcn.nexus_vcn.id
  cidr_block        = "10.0.0.0/24"
  route_table_id    = oci_core_route_table.nexus_route_table.id
  security_list_ids = [oci_core_security_list.nexus_security_list.id]
  dns_label         = "nexussubnet"
  dhcp_options_id   = oci_core_vcn.nexus_vcn.default_dhcp_options_id
}

data "oci_core_images" "ubuntu_images" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

resource "oci_core_instance" "nexus_erp" {
  compartment_id      = var.compartment_ocid
  display_name        = "nexus-erp"
  shape               = var.instance_shape
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[0].name

  create_vnic_details {
    subnet_id        = oci_core_subnet.nexus_subnet.id
    assign_public_ip = true
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu_images.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_size
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(templatefile("${path.module}/cloud-init.yml", {}))
  }

  dynamic "shape_config" {
    for_each = can(regex("Flex$", var.instance_shape)) ? [1] : []
    content {
      ocpus         = var.instance_ocpus
      memory_in_gbs = var.instance_memory_in_gbs
    }
  }
}
