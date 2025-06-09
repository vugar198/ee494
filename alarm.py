import requests

esp_ip = "http://192.168.1.102"  # Replace with actual ESP8266 IP

def request_and_print(endpoint, params=None):
    try:
        r = requests.get(f"{esp_ip}{endpoint}", params=params, timeout=5)
        print(f"[✓] Request to {endpoint} succeeded: {r.text}")
    except requests.RequestException as e:
        print(f"[✗] Request to {endpoint} failed: {e}")

def play_track(n):
    request_and_print("/play", {"n": n})

def set_volume(v):
    if 0 <= v <= 30:
        request_and_print("/volume", {"v": v})
    else:
        print("[!] Volume must be between 0 and 30.")

def pause():
    request_and_print("/pause")

def resume():
    request_and_print("/resume")

def next_track():
    request_and_print("/next")

def prev_track():
    request_and_print("/prev")

# Example interactive usage
if _name_ == "_main_":
    print("DFPlayer Control Console")
    print("Commands: play <n>, volume <v>, pause, resume, next, prev, exit")

    while True:
        cmd = input(">> ").strip().lower()
        if cmd == "exit":
            break
        elif cmd.startswith("play "):
            try:
                n = int(cmd.split()[1])
                play_track(n)
            except:
                print("[!] Invalid track number.")
        elif cmd.startswith("volume "):
            try:
                v = int(cmd.split()[1])
                set_volume(v)
            except:
                print("[!] Invalid volume value.")
        elif cmd == "pause":
            pause()
        elif cmd == "resume":
            resume()
        elif cmd == "next":
            next_track()
        elif cmd == "prev":
            prev_track()
        else:
            print("[!] Unknown command.")