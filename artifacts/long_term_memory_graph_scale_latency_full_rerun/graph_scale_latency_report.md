# Long-Term Memory Graph Scale-Latency Benchmark

- Prefix: `graph-scale-`
- Scale factors: `1, 2, 4`
- Repeats: `5`
- Warmup rounds: `2`

| Scale | Nodes | Edges | Recall mean ms | Recall p95 ms | Recall qps | Detail mean ms | Detail p95 ms | Detail qps |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1` | `360` | `3012` | `99.08` | `120.244` | `10.093` | `3.759` | `4.572` | `266.028` |
| `2` | `720` | `3045` | `98.422` | `126.376` | `10.16` | `3.672` | `4.185` | `272.331` |
| `4` | `1440` | `2440` | `91.602` | `142.437` | `10.917` | `3.674` | `4.029` | `272.183` |
