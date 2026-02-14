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
    device-tree-compiler \
    lcov \
    nano \
    valgrind \
    clang \
    ccache \
    cmake \
    clangd-18 \
    bear

# Set clangd as the default language server
RUN update-alternatives --install /usr/bin/clangd clangd /usr/bin/clangd-15 100

# Install RISC-V Toolchain (xPack) + compatibility symlinks for riscv64-unknown-elf-*
ARG XPACK_RISCV_VER=15.2.0-1

WORKDIR /tmp
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) xarch="linux-x64" ;; \
      arm64) xarch="linux-arm64" ;; \
      *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    \
    base="https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/download/v${XPACK_RISCV_VER}"; \
    tgz="xpack-riscv-none-elf-gcc-${XPACK_RISCV_VER}-${xarch}.tar.gz"; \
    sha="${tgz}.sha"; \
    \
    curl -L --fail -o "$tgz" "${base}/${tgz}"; \
    curl -L --fail -o "$sha" "${base}/${sha}"; \
    sha256sum -c "$sha"; \
    \
    rm -rf /opt/riscv; \
    mkdir -p /opt; \
    tar -xzf "$tgz" -C /opt; \
    mv "/opt/xpack-riscv-none-elf-gcc-${XPACK_RISCV_VER}" /opt/riscv; \
    rm -f "$tgz" "$sha"; \
    \
    # Compatibility: keep existing course scripts working (riscv64-unknown-elf-* prefix)
    for tool in gcc g++ cpp ar as ld nm objcopy objdump ranlib readelf size strip; do \
      ln -sf "/opt/riscv/bin/riscv-none-elf-${tool}" "/opt/riscv/bin/riscv64-unknown-elf-${tool}"; \
    done; \
    \
    # Sanity checks: both names should work
    riscv-none-elf-gcc --version; \
    riscv64-unknown-elf-gcc --version; \
    riscv64-unknown-elf-gcc -march=rv32imfd -mabi=ilp32d -x c - -c -o /tmp/t.o <<'EOF'\nint main(){return 0;}\nEOF

ENV RISCV="/opt/riscv"
ENV PATH="/opt/riscv/bin:${PATH}"

# Install Spike RISC-V ISA Simulator
WORKDIR /tmp
RUN git clone https://github.com/riscv-software-src/riscv-isa-sim.git
WORKDIR /tmp/riscv-isa-sim
RUN git checkout v1.1.0
RUN mkdir build
WORKDIR /tmp/riscv-isa-sim/build
RUN ../configure --prefix=$RISCV --with-isa=RV32IMFD --with-target=riscv32-unknown-elf
RUN make
RUN make install
RUN rm -rf /tmp/riscv-isa-sim
RUN spike --help

WORKDIR /tmp
RUN git clone https://github.com/riscv-software-src/riscv-pk.git
WORKDIR /tmp/riscv-pk
RUN git checkout 9c61d29846d8521d9487a57739330f9682d5b542
RUN mkdir build
WORKDIR /tmp/riscv-pk/build
RUN ../configure --prefix=$RISCV --host=riscv64-unknown-elf --with-arch=rv32imfd --with-abi=ilp32d
RUN make
RUN make install
RUN rm -rf /tmp/riscv-pk

ENTRYPOINT [ "/bin/bash" ]
