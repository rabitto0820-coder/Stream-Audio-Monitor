import sounddevice as sd

print("=== オーディオデバイス一覧 ===")
print(sd.query_devices())

print("\n=== デフォルトデバイス ===")
print(sd.default.device)