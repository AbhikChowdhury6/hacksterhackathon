# muse_osc_receiver.py
from pythonosc import dispatcher, osc_server

def eeg_handler(address, *args):
    print(f"{address}: {args}")

if __name__ == "__main__":
    disp = dispatcher.Dispatcher()
    disp.map("/muse/eeg", eeg_handler)
    # optionally map /muse/acc, /muse/gyro, etc.
    server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", 5000), disp)
    print("Listening for OSC data on port 5000...")
    server.serve_forever()

#muse 8073
#my ip 172.22.111.46 heatsync
#192.168.1.10

#10.173.69.73 me
#l