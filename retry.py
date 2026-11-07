#!/usr/bin/env python3
"""One quick pass over Always Free shapes in eu-madrid-1. Exit 0 always; writes result to $GITHUB_OUTPUT."""
import os, time, datetime, oci

CFG = os.path.expanduser("~/.oci/config")
AD = "NhlH:EU-MADRID-1-AD-1"
SUBNET = "ocid1.subnet.oc1.eu-madrid-1.aaaaaaaaegdaxz37oxzvczwx2ethp3r4ztm435qhb3mc5rcg3ssdrtlaudwq"
IMG_ARM = "ocid1.image.oc1.eu-madrid-1.aaaaaaaal7jmbfkizhtwk56chfo5afzif33a2wig36bk6h33jalamck3lhdq"
PUB = open(os.path.expanduser("~/.oci/ssh.pub")).read().strip()

c = oci.config.from_file(CFG); cc = oci.core.ComputeClient(c); T = c["tenancy"]

def out(k, v):
    p = os.environ.get("GITHUB_OUTPUT")
    if p:
        open(p, "a").write(f"{k}={v}\n")

def log(m): print(f"{datetime.datetime.utcnow().isoformat()}Z {m}", flush=True)

def existing():
    return [i for i in cc.list_instances(T).data
            if i.display_name.startswith("hermes") and i.lifecycle_state not in ("TERMINATED", "TERMINATING")]

def x86_image():
    imgs = cc.list_images(T, operating_system="Canonical Ubuntu", shape="VM.Standard.E2.1.Micro",
                          sort_by="TIMECREATED", sort_order="DESC").data
    for i in imgs:
        if "24.04" in i.display_name and "Minimal" in i.display_name and "aarch64" not in i.display_name:
            return i.id
    return imgs[0].id

def attempt(shape, ocpu, mem, fd, img):
    det = oci.core.models.LaunchInstanceDetails(
        availability_domain=AD, compartment_id=T, display_name="hermes", shape=shape, fault_domain=fd,
        shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(ocpus=ocpu, memory_in_gbs=mem) if ocpu else None,
        source_details=oci.core.models.InstanceSourceViaImageDetails(image_id=img, boot_volume_size_in_gbs=50),
        create_vnic_details=oci.core.models.CreateVnicDetails(subnet_id=SUBNET, assign_public_ip=True),
        metadata={"ssh_authorized_keys": PUB})
    return cc.launch_instance(det).data

ex = existing()
if ex:
    log("instance already exists: " + ", ".join(f"{i.shape} {i.lifecycle_state}" for i in ex))
    out("result", "exists"); raise SystemExit(0)

plans = [("VM.Standard.A1.Flex", 2, 12, f"FAULT-DOMAIN-{n}") for n in (1, 2, 3)] + \
        [("VM.Standard.A1.Flex", 1, 6, f"FAULT-DOMAIN-{n}") for n in (1, 2, 3)] + \
        [("VM.Standard.E2.1.Micro", None, None, None)]
for shape, ocpu, mem, fd in plans:
    try:
        img = x86_image() if shape.startswith("VM.Standard.E2") else IMG_ARM
        inst = attempt(shape, ocpu, mem, fd, img)
        log(f"SUCCESS {shape} {ocpu}/{mem} {fd}")
        out("result", "success"); out("shape", f"{shape} {ocpu or 1} OCPU {mem or 1} GB")
        raise SystemExit(0)
    except oci.exceptions.ServiceError as e:
        log(f"{shape} {ocpu}/{mem} {fd}: {e.status} {e.code} {e.message[:90]}")
        time.sleep(30 if e.status == 429 else 12)
out("result", "none")
