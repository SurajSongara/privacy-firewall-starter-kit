# P004_PRECISION_BENCHMARK

Extend the R010 benchmark runner to report precision alongside recall: per-detector true/false positive counts against labeled expectations for the synthetic set and TestFiles. Snapshot a baseline (JSON) checked into examples/; the runner fails if precision or recall regresses beyond tolerance. Every P00x task after this one must show benchmark before/after in its commit message.
