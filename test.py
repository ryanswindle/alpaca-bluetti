import time

from alpaca.switch import Switch
from config import config


def label_state(state: bool) -> str:
    return "ON" if state else "OFF"


switch = Switch(f"{config.server.host}:{config.server.port}", 0)

print(f"  Name:   {switch.Name}")
print(f"  Driver: {switch.DriverVersion}\n")

# Connect — returns immediately, BLE handshake runs in background
print("Connecting...")
switch.Connected = True
t0 = time.time()
while not switch.Connected:
    time.sleep(0.5)
    elapsed = time.time() - t0
    if elapsed > 60:
        print("  ERROR: Timed out waiting for BLE connection")
        raise SystemExit(1)
print(f"  Connected: {switch.Connected}")

# MaxSwitch
max_sw = switch.MaxSwitch
print(f"  MaxSwitch: {max_sw}\n")

# Enumerate switches
print("--- Switch inventory ---")
for i in range(max_sw):
    name = switch.GetSwitchName(i)
    desc = switch.GetSwitchDescription(i)
    can_w = switch.CanWrite(i)
    can_a = switch.CanAsync(i)
    step = switch.SwitchStep(i)
    min_v = switch.MinSwitchValue(i)
    max_v = switch.MaxSwitchValue(i)
    state = switch.GetSwitch(i)
    value = switch.GetSwitchValue(i)
    print(f"  [{i}] {name}: {label_state(state)}  (value={value})")
    print(f"      desc=\"{desc}\"")
    print(f"      canWrite={can_w}  canAsync={can_a}")
    print(f"      min={min_v}  max={max_v}  step={step}")
print()

# # Toggle test on AC Output (switch 0)
# switch_id = 1
# print(f"--- Toggle test (switch {switch_id}: AC Output) ---")
# original = switch.GetSwitch(switch_id)
# print(f"  Current state: {label_state(original)}")
#
# time.sleep(5)
#
# target = not original
# print(f"  Setting switch {switch_id} to {label_state(target)}...")
# switch.SetSwitch(switch_id, target)
# time.sleep(5)
# print(f"  State after SetSwitch: {label_state(switch.GetSwitch(switch_id))}")
#
# print(f"  Restoring switch {switch_id} to {label_state(original)}...")
# switch.SetSwitch(switch_id, original)
# time.sleep(5)
# print(f"  State after restore:   {label_state(switch.GetSwitch(switch_id))}")
# print()

# Disconnect
print("Disconnecting...")
switch.Connected = False
print(f"  Connected: {switch.Connected}")
print()