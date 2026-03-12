load("@rules_python//python:defs.bzl", "py_binary", "py_library")
load("@rules_python//python:pip.bzl", "compile_pip_requirements")
load("@pip_deps//:requirements.bzl", "requirement")

# Run this to update requirements_lock.txt with pinned versions and hashes.
compile_pip_requirements(
    name = "requirements",
    requirements_in = "requirements.txt",
    requirements_txt = "requirements_lock.txt",
)

# Build script for ZMK firmware
py_binary(
    name = "build",
    srcs = ["build.py"],
    main = "build.py",
)
