load("@rules_python//python:defs.bzl", "py_binary")
load("@pip_deps//:requirements.bzl", "requirement")

package(default_visibility = ["//visibility:public"])

py_binary(
    name = "gen_keycaps",
    srcs = ["gen_keycaps.py"],
    main = "gen_keycaps.py",
    deps = [
        requirement("numpy"),
        requirement("requests"),
        requirement("trimesh"),
    ],
)
