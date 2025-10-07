# pip install requests opencv-python
import requests
from requests.adapters import HTTPAdapter, Retry
import time

class RobotCar:
    def __init__(self, host, timeout=1.5):
        """
        host: IP or mDNS name of the ESP32, e.g., '192.168.4.1' or 'car.local'
        """
        self.base = f"http://{host}"
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.2, status_forcelist=[502, 503, 504])
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

    def _get(self, path):
        url = f"{self.base}{path}"
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        return r.text

    # Movement
    def forward(self): return self._get("/go")
    def back(self):    return self._get("/back")
    def left(self):    return self._get("/left")
    def right(self):   return self._get("/right")
    def stop(self):    return self._get("/stop")

    # Light
    def led_on(self):  return self._get("/ledon")
    def led_off(self): return self._get("/ledoff")

    # Camera stream URL (open with OpenCV or a browser)
    def stream_url(self): return f"{self.base.replace('://', '://')}:81/stream"


if __name__ == "__main__":
    car = RobotCar(host="YOUR_ESP_IP_HERE")  # e.g., "192.168.1.87"

    try:
        print("Forward for 0.5s…")
        car.forward()
        time.sleep(0.5)
        car.stop()

        print("Right for 0.3s…")
        car.right()
        time.sleep(0.3)
        car.stop()

        print("LED on for 1s…")
        car.led_on()
        time.sleep(1.0)
        car.led_off()

        print("Done.")
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
