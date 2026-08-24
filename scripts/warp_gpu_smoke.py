import warp as wp

wp.init()

@wp.kernel
def write_value(output: wp.array(dtype=wp.int32)):
    output[0] = 42


device = wp.get_device("cuda:0")
output = wp.zeros(1, dtype=wp.int32, device=device)
wp.launch(write_value, dim=1, inputs=[output], device=device)
wp.synchronize_device(device)
value = int(output.numpy()[0])
assert value == 42, value
print({"warp_version": wp.config.version, "device": "cuda:0", "value": value, "ok": True})
