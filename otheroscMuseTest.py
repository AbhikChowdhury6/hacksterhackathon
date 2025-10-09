# muse_osc_receiver.py
from pythonosc import dispatcher, osc_server
import time

def print_once(msg=[True]):
    if msg[0]:
        print("Listening for Mind Monitor OSC…")
        print("Mapped paths: /muse/eeg (/muse/eeg/aux optional), /muse/acc, /muse/gyro")
        msg[0] = False

def eeg_handler(address, *vals):
    # vals can be 4 or 5 floats depending on Mind Monitor config (aux channel)
    t = time.time()
    if len(vals) == 4:
        tp9, af7, af8, tp10 = vals
        print(f"{t:.3f} EEG 4ch  TP9={tp9:.2f}  AF7={af7:.2f}  AF8={af8:.2f}  TP10={tp10:.2f}")
    elif len(vals) == 5:
        tp9, af7, af8, tp10, aux = vals
        print(f"{t:.3f} EEG 5ch  TP9={tp9:.2f}  AF7={af7:.2f}  AF8={af8:.2f}  TP10={tp10:.2f}  AUX={aux:.2f}")
    else:
        print(f"{t:.3f} EEG unexpected len={len(vals)}: {vals}")

def acc_handler(address, x, y, z):
    print(f"{time.time():.3f} ACC  x={x:.3f}  y={y:.3f}  z={z:.3f}")

def gyro_handler(address, x, y, z):
    print(f"{time.time():.3f} GYRO x={x:.3f}  y={y:.3f}  z={z:.3f}")

if __name__ == "__main__":
    disp = dispatcher.Dispatcher()
    disp.map("/muse/eeg", eeg_handler)
    # Some Mind Monitor builds also send /muse/eeg/aux separately—optional:
    disp.map("/muse/acc", acc_handler)
    disp.map("/muse/gyro", gyro_handler)

    server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", 5000), disp)
    print_once()
    server.serve_forever()
