# foreach_static_zip

Sentinel LE case. `Fn::ForEach` over a static collection with all expanded
functions sharing the same `CodeUri`. Locks the expanded-template shape
(`AlphaFunction`, `BetaFunction` inlined as siblings, ForEach key gone)
and the post-package shape (each function's `CodeUri` rewritten to the
same `s3://golden-bucket/<sha256>`).
