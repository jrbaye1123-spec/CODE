# Generate 5 layers for each scenario
N = 1024
Kmax = 20
d = 4096

for scenario in ["isotropic", "spiked", "anisotropic"]:
    for l in range(1, 6):
        generate_synthetic_layer(
            layer_idx=l,
            N=N,
            Kmax=Kmax,
            d=d,
            spectrum_type=scenario,
            seed=12345 + l,
            output_dir=f"./synthetic_cache_{scenario}"
        )