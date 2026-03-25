#!/usr/bin/env python3
from evdev import InputDevice, list_devices, ecodes, UInput
import time
import select
import argparse

# Debounce settings:
# - MIN_INTERVAL: minimum time between "press" events of the same key to be considered valid
# - MAX_RUNTIME: None = run forever; otherwise stop after N seconds
MIN_INTERVAL = 0.01
MAX_RUNTIME = None

IGNORED_KEY_RELEASE_GRACE = 0.020  # seconds


def find_device_by_name(target_name: str):
    """
    Find the first evdev device whose reported name exactly matches target_name.
    Returns an InputDevice or None if not found.
    """
    for path in list_devices():
        dev = InputDevice(path)
        if dev.name == target_name:
            return dev
    return None


def wait_for_device(target_name: str, interval: float = 0.5):
    """
    Poll until a matching device appears.
    Useful for hot-plugging (keyboard unplug/replug).
    """
    print(f"Waiting for device '{target_name}'...")
    while True:
        dev = find_device_by_name(target_name)
        if dev is not None:
            return dev
        time.sleep(interval)


def release_all_keys(ui):
    """
    Send a release event for all known KEY_* codes on the virtual device.
    This helps clear any 'stuck' modifier state in the OS.
    """
    for code in ecodes.keys.keys():
        ui.write(ecodes.EV_KEY, code, 0)
    ui.syn()


def grab_when_idle(dev: InputDevice, verbose: bool, poll_interval: float = 0.05):
    """
    Wait until no keys are pressed before grabbing the device.
    Prevents the 'key stuck' bug when a press happened before the grab.
    """
    warned = False

    while True:
        try:
            active = dev.active_keys()
        except OSError as e:
            # device may have disappeared while waiting
            raise e

        if not active:
            # all keys released, safe to grab
            print("Grabbing device so only this script sees its events...")
            dev.grab()
            print("Grab successful.")
            return

        # keys still held
        if not warned:
            print("Waiting for all keys to be released before grabbing the device...")
            warned = True

        if verbose:
            print(f"Currently pressed keys: {active}")

        time.sleep(poll_interval)


def code_to_key_name(code: int) -> str:
    """
    Convert a numeric evdev key code (event.code) into a human-readable name like 'KEY_A'.

    Notes:
    - For EV_KEY events, Linux uses numeric codes that map to symbolic constants.
    - ecodes.KEY is a dict mapping numeric codes -> 'KEY_*' strings.
    - If a code is unknown, we return a fallback string.
    """
    return ecodes.KEY.get(code, f"KEY_{code}")


def parse_ignored_keys(values):
    alias_map = {
        "CTRL": {ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL},
        "CONTROL": {ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL},
        "LCTRL": {ecodes.KEY_LEFTCTRL},
        "LEFTCTRL": {ecodes.KEY_LEFTCTRL},
        "RCTRL": {ecodes.KEY_RIGHTCTRL},
        "RIGHTCTRL": {ecodes.KEY_RIGHTCTRL},
    }

    result = set()

    for raw in values:
        token = raw.strip()
        upper = token.upper()

        if upper in alias_map:
            result.update(alias_map[upper])
            continue

        if token.isdigit():
            result.add(int(token))
            continue

        if upper in ecodes.ecodes and isinstance(ecodes.ecodes[upper], int):
            result.add(ecodes.ecodes[upper])
            continue

        prefixed = f"KEY_{upper}"
        if prefixed in ecodes.ecodes and isinstance(ecodes.ecodes[prefixed], int):
            result.add(ecodes.ecodes[prefixed])
            continue

        raise ValueError(f"Unknown key identifier: {raw}")

    return result


def run_loop(target_name: str, verbose: bool, ignored_keys):
    """
    Main loop:
    - Wait for target keyboard device.
    - Grab it (so only this script sees its events).
    - Create a virtual keyboard device (uinput) mirroring the real one.
    - Apply per-key debounce on press events.
    - Forward allowed events to the virtual device.
    """
    while True:
        dev = wait_for_device(target_name)

        print(f"Using device: {dev.path} ({dev.name})")

        # grab the device only when no keys are down
        try:
            grab_when_idle(dev, verbose=verbose)
        except OSError as e:
            print(f"Failed to grab device: {e}")
            try:
                dev.close()
            except Exception:
                pass
            time.sleep(1.0)
            continue

        # create a virtual keyboard with the same capabilities
        try:
            ui = UInput.from_device(dev, name="debounced-" + dev.name)
        except OSError as e:
            print(f"Failed to create UInput device: {e}")
            try:
                dev.ungrab()
            except OSError:
                pass
            try:
                dev.close()
            except Exception:
                pass
            time.sleep(1.0)
            continue

        # extra safety: clear any potentially stuck keys on the virtual dev
        release_all_keys(ui)

        key_state = {}
        pending_release = {}

        print(f"Debounce filter active on {dev.path}")
        print(f"Blocking same-key presses < {MIN_INTERVAL*1000:.1f} ms\n")

        start_time = time.time()

        try:
            while True:
                now = time.time()

                if MAX_RUNTIME is not None and (now - start_time) >= MAX_RUNTIME:
                    print("\nTimer expired — exiting.")
                    return

                expired = [key for key, deadline in pending_release.items() if now >= deadline]
                for key in expired:
                    ui.write(ecodes.EV_KEY, key, 0)
                    key_state[key] = {"down": False, "last_time": now}
                    if verbose:
                        print(f"PASS  delayed release key={key} dt={(now - key_state[key]['last_time']):.4f}s")
                    del pending_release[key]
                if expired:
                    ui.syn()

                try:
                    r, _, _ = select.select([dev.fd], [], [], 0.01)
                    if dev.fd not in r:
                        continue

                    events = dev.read()

                    for event in events:
                        if event.type == ecodes.EV_KEY:
                            key = event.code
                            value = event.value  # 1=press, 0=release, 2=repeat
                            key_name = code_to_key_name(key)

                            st = key_state.get(key, {"down": False, "last_time": 0.0})
                            is_down = st["down"]
                            last_time = st["last_time"]
                            dt = now - last_time

                            # ignore hardware auto-repeat completely
                            if value == 2:  # repeat
                                continue

                            if key in ignored_keys:
                                if value == 0:  # release
                                    if is_down:
                                        pending_release[key] = now + IGNORED_KEY_RELEASE_GRACE
                                    continue

                                if value == 1:  # press
                                    if key in pending_release:
                                        del pending_release[key]
                                        key_state[key] = {"down": True, "last_time": now}
                                        if verbose:
                                            print(f"CANCEL delayed release key={key} dt={dt:.4f}s")
                                        continue

                                    if is_down:
                                        # already considered down; ignore
                                        continue

                                    key_state[key] = {"down": True, "last_time": now}
                                    if verbose:
                                        print(f"PASS  press key={key} ({key_name}) dt={dt:.4f}s")

                                    ui.write_event(event)
                                    continue

                            if value == 1:  # press
                                if is_down:
                                    # already considered down; ignore
                                    continue

                                # debounce fast re-press
                                if dt < MIN_INTERVAL:
                                    print(f"BLOCK fast re-press key={key} ({key_name}) dt={dt:.4f}s")
                                    continue

                                key_state[key] = {"down": True, "last_time": now}
                                if verbose:
                                    print(f"PASS  press key={key} ({key_name}) dt={dt:.4f}s")

                            elif value == 0:  # release
                                key_state[key] = {"down": False, "last_time": now}

                        # forward allowed events
                        ui.write_event(event)

                    ui.syn()

                except OSError as e:
                    # device went away / I/O issue
                    print(f"Device I/O error ({e}); device may have been disconnected. Reattaching...")
                    # clear any keys on the virtual device before we drop it
                    try:
                        pending_release.clear()
                        release_all_keys(ui)
                    except Exception:
                        pass
                    break

        finally:
            print("Releasing device and closing.")
            try:
                dev.ungrab()
            except OSError:
                pass
            try:
                dev.close()
            except Exception:
                pass
            try:
                ui.close()
            except Exception:
                pass

            print("Device loop ended; waiting for keyboard to reappear...\n")


def main():
    parser = argparse.ArgumentParser(
        description="Debounce keyboard events for a specific device."
    )
    parser.add_argument(
        "device_name",
        help="Exact evdev device name to grab (e.g. 'SINO WEALTH Trust GXT 871 ZORA').",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log PASS events (in addition to BLOCKed ones).",
    )
    parser.add_argument(
        "--ignored-keys",
        nargs="+",
        default=[],
        metavar="KEY",
        help="Keys to use delayed-release handling for (examples: CTRL, LEFTCTRL, RIGHTCTRL, KEY_LEFTCTRL, 29).",
    )
    args = parser.parse_args()

    try:
        ignored_keys = parse_ignored_keys(args.ignored_keys)
    except ValueError as e:
        parser.error(str(e))

    run_loop(target_name=args.device_name, verbose=args.verbose, ignored_keys=ignored_keys)


if __name__ == "__main__":
    main()
