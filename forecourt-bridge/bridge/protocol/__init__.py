from .base import ProtocolAdapter, Reading
from .simulator import SimulatorAdapter
from .lanfeng import LanfengAdapter

ADAPTERS = {
    "simulator": SimulatorAdapter,
    "lanfeng": LanfengAdapter,
}


def get_adapter(name, serial_config):
    try:
        adapter_cls = ADAPTERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown protocol adapter '{name}'. Available: {list(ADAPTERS)}"
        ) from None
    return adapter_cls(serial_config)
