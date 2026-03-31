FROM ubuntu:24.04

# Install dependencies
RUN apt-get update && apt-get install -y --fix-missing \
    curl \
    locales \
    dos2unix \
    lsb-release \
    ca-certificates \
    git \
    nano \
    flex \
    bison \
    build-essential \
    ccache \
    python3 \
    python3-pip \
    python3-rich \
    device-tree-compiler \
    rr \
    gdb \
    time \
    lcov;

ARG ARTIFACT_TAG=v2.1.0

WORKDIR /tmp
RUN localedef -i en_GB -f UTF-8 en_GB.UTF-8; \
    set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) xarch="linux-x64" ;; \
      arm64) xarch="linux-arm64" ;; \
      *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    \
    base="https://github.com/LangProc/langproc-cw/releases/download/${ARTIFACT_TAG}"; \
    tgz="riscv-gnu-toolchain-${xarch}.tar.gz"; \
    sha="${tgz}.sha"; \
    \
    curl -L --fail -o "$tgz" "${base}/${tgz}"; \
    curl -L --fail -o "$sha" "${base}/${sha}"; \
    sha256sum -c "$sha"; \
    \
    rm -rf /opt/riscv; \
    mkdir -p /opt; \
    tar -xzf "$tgz" -C /opt; \
    rm -f "$tgz" "$sha"; \
    \
    /opt/riscv/bin/riscv32-unknown-elf-gcc --version

ENV RISCV="/opt/riscv" \
    PATH="/opt/riscv/bin:${PATH}"

ENTRYPOINT [ "/bin/bash" ]
