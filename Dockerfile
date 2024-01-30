FROM ubuntu:22.04

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
    nano

# Install RISC-V Toolchain
WORKDIR /tmp
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; arch="${arch##*-}"; \
    url=; \
    case "$arch" in \
    'arm64') \
    curl --output riscv-gnu-toolchain.tar.gz -L "https://github.com/langproc/langproc-2022-cw/releases/download/v1.0.0/riscv-gnu-toolchain-2022-09-21-ubuntu-22.04-arm64.tar.gz" \
    ;; \
    *) curl --output riscv-gnu-toolchain.tar.gz -L "https://github.com/langproc/langproc-2022-cw/releases/download/v1.0.0/riscv-gnu-toolchain-2022-09-21-ubuntu-22.04-amd64.tar.gz" \
    ;; \
    esac;
RUN rm -rf /opt/riscv
RUN tar -xzf riscv-gnu-toolchain.tar.gz --directory /opt
ENV PATH="/opt/riscv/bin:${PATH}"
ENV RISCV="/opt/riscv"
RUN rm -rf riscv-gnu-toolchain.tar.gz
RUN riscv64-unknown-elf-gcc --help

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
RUN git checkout 573c858d9071a2216537f71de651a814f76ee76d
RUN mkdir build
WORKDIR /tmp/riscv-pk/build
RUN ../configure --prefix=$RISCV --host=riscv64-unknown-elf --with-arch=rv32imfd --with-abi=ilp32d
RUN make
RUN make install

ENTRYPOINT [ "/bin/bash" ]
