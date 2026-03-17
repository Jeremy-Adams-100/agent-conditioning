"""GCP Compute Engine abstraction layer.

When GCP_MOCK=true (default), uses an in-memory dict to simulate VMs.
When GCP_MOCK=false, uses google-cloud-compute SDK (requires credentials).
"""

import asyncio
import secrets

from explorer_platform import config

# ---------------------------------------------------------------------------
# Mock implementation (GCP_MOCK=true)
# ---------------------------------------------------------------------------

_mock_vms: dict[str, dict] = {}
_mock_ip_counter = 1


async def _mock_create_vm(name: str, metadata: dict) -> dict:
    global _mock_ip_counter
    # In mock mode, point at localhost so a local VM agent can handle requests
    ip = "127.0.0.1"
    _mock_ip_counter += 1
    vm = {
        "name": name,
        "zone": config.GCP_ZONE,
        "status": "RUNNING",
        "internal_ip": ip,
        "metadata": metadata,
    }
    _mock_vms[name] = vm
    return {"name": name, "zone": config.GCP_ZONE, "internal_ip": ip}


async def _mock_suspend_vm(zone: str, name: str) -> None:
    if name in _mock_vms:
        _mock_vms[name]["status"] = "SUSPENDED"


async def _mock_resume_vm(zone: str, name: str) -> None:
    if name in _mock_vms:
        _mock_vms[name]["status"] = "RUNNING"


async def _mock_delete_vm(zone: str, name: str) -> None:
    _mock_vms.pop(name, None)


async def _mock_get_vm_info(zone: str, name: str) -> dict:
    vm = _mock_vms.get(name)
    if not vm:
        raise ValueError(f"VM not found: {name}")
    return {"status": vm["status"], "internal_ip": vm["internal_ip"]}


# ---------------------------------------------------------------------------
# Real GCP implementation (GCP_MOCK=false)
# ---------------------------------------------------------------------------


async def _real_create_vm(name: str, metadata: dict) -> dict:
    from google.cloud import compute_v1

    def _create():
        client = compute_v1.InstancesClient()

        # Build metadata items
        items = [{"key": k, "value": v} for k, v in metadata.items()]

        instance = compute_v1.Instance(
            name=name,
            machine_type=f"zones/{config.GCP_ZONE}/machineTypes/{config.GCP_MACHINE_TYPE}",
            disks=[compute_v1.AttachedDisk(
                boot=True,
                auto_delete=True,
                initialize_params=compute_v1.AttachedDiskInitializeParams(
                    source_image=f"projects/{config.GCP_PROJECT}/global/images/{config.GCP_BASE_IMAGE}",
                    disk_size_gb=20,
                ),
            )],
            network_interfaces=[compute_v1.NetworkInterface(
                # Internal IP only — no external access
                name="global/networks/default",
            )],
            metadata=compute_v1.Metadata(items=items),
        )

        op = client.insert(project=config.GCP_PROJECT, zone=config.GCP_ZONE, instance_resource=instance)
        op.result()  # wait for completion

        # Fetch the created instance to get its internal IP
        inst = client.get(project=config.GCP_PROJECT, zone=config.GCP_ZONE, instance=name)
        ip = inst.network_interfaces[0].network_i_p
        return {"name": name, "zone": config.GCP_ZONE, "internal_ip": ip}

    return await asyncio.to_thread(_create)


async def _real_suspend_vm(zone: str, name: str) -> None:
    from google.cloud import compute_v1

    def _suspend():
        client = compute_v1.InstancesClient()
        op = client.suspend(project=config.GCP_PROJECT, zone=zone, instance=name)
        op.result()

    await asyncio.to_thread(_suspend)


async def _real_resume_vm(zone: str, name: str) -> None:
    from google.cloud import compute_v1

    def _resume():
        client = compute_v1.InstancesClient()
        op = client.resume(project=config.GCP_PROJECT, zone=zone, instance=name)
        op.result()

    await asyncio.to_thread(_resume)


async def _real_delete_vm(zone: str, name: str) -> None:
    from google.cloud import compute_v1

    def _delete():
        client = compute_v1.InstancesClient()
        op = client.delete(project=config.GCP_PROJECT, zone=zone, instance=name)
        op.result()

    await asyncio.to_thread(_delete)


async def _real_get_vm_info(zone: str, name: str) -> dict:
    from google.cloud import compute_v1

    def _get():
        client = compute_v1.InstancesClient()
        inst = client.get(project=config.GCP_PROJECT, zone=zone, instance=name)
        return {
            "status": inst.status,
            "internal_ip": inst.network_interfaces[0].network_i_p if inst.network_interfaces else None,
        }

    return await asyncio.to_thread(_get)


# ---------------------------------------------------------------------------
# Module-level dispatch
# ---------------------------------------------------------------------------

if config.GCP_MOCK:
    create_vm = _mock_create_vm
    suspend_vm = _mock_suspend_vm
    resume_vm = _mock_resume_vm
    delete_vm = _mock_delete_vm
    get_vm_info = _mock_get_vm_info
else:
    create_vm = _real_create_vm
    suspend_vm = _real_suspend_vm
    resume_vm = _real_resume_vm
    delete_vm = _real_delete_vm
    get_vm_info = _real_get_vm_info
