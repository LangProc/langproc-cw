FROM ubuntu:24.04

# Install dependencies
RUN apt-get update && apt-get install -y --fix-missing \
    git \
    lsb-release \
    python3 \
    python3-pip \
    autoconf \
    bc \
    bison \
    dos2unix \
    gdb \
    gcc \
    lcov \
    make \
    flex \
    build-essential \
    ca-certificates \
    curl \
    lcov \
    nano \
    valgrind \
    clang \
    ccache \
    cmake \
    clangd-18 \
    bear

# Set clangd as the default language server
RUN update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-18 100

WORKDIR /tmp
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) xarch="linux-x64" ;; \
      arm64) xarch="linux-arm64" ;; \
      *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    \
    base="https://github.com/langproc/langproc-cw/???"; \
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

ENV RISCV="/opt/riscv"
ENV PATH="/opt/riscv/bin:${PATH}"

ENTRYPOINT [ "/bin/bash" ]
