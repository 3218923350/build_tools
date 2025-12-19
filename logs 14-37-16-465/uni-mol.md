# Tool: Uni-Mol

- Version: 
- Homepage: https://github.com/deepmodeling/Uni-Mol
- Docs: 
- Source: tools/deepmodeling/deepmodeling.json (id=2)

---

## 开始构建（2025-12-18 14:12:39）

### 更新仓库

```text
Already up to date.

```

### 分析仓库与文档（静态收集）

**仓库文件摘要（部分路径）**:

```text
README.md
unimol2/README.md
unimol_plus/README.md
unimol_docking_v2/README.md
unimol_tools/README.md
unimol/README.md
docs/source/school.md
docs/source/examples.md
docs/source/features.md
docs/source/quickstart.md
docs/source/requirements.md
docs/source/installation.md
unimol_plus/setup.py
unimol_tools/setup.py
unimol/setup.py
```

**文档页面地址（部分）**:

```text
https://unimol.readthedocs.io/en/latest/installation.html
https://pypi.org/project/unimol-tools/
https://github.com/deepmodeling/Uni-Mol
https://hub.docker.com/u/dptechnology
```

### 文档抓取链接（docs_ctx 全量）

- https://unimol.readthedocs.io/en/latest/installation.html
- https://pypi.org/project/unimol-tools/
- https://github.com/deepmodeling/Uni-Mol
- https://hub.docker.com/u/dptechnology


---

## 构建尝试 #1（剩余写 Dockerfile 机会：10）

**提案模型**: gemini, **评审模型**: gpt5

**plan.can_build**: True, **confidence**: 0.833

### 综合分析说明

```text
=== Round 1 Proposer (gemini) rationale ===
1. **Target Selection**: The repository contains multiple projects (`unimol`, `unimol_tools`, `unimol_plus`). `unimol_tools` is identified as the user-friendly wrapper for property prediction and representation, and its documentation explicitly states it has removed the complex dependency on `Uni-Core` (which requires custom compilation). Therefore, `unimol_tools` is the safest and most useful 'minimal' entry point.
2. **Dependency Management**: 
   - `python:3.9-slim` is selected to satisfy the Python 3.8+ requirement.
   - `numpy<2.0.0` is explicitly installed because `unimol_tools/README.md` and `setup.py` strictly require it (RDKit compatibility).
   - System libraries (`libxrender1`, `libxext6`) are added to support `rdkit`.
3. **Installation Method**: Following 'Option 2' in `unimol_tools/README.md`, the Dockerfile clones the full `Uni-Mol` repository and installs `unimol_tools` from source. This ensures the user has access to the latest code and the surrounding repository context (examples, other folders) if needed.
4. **SSH/MCP**: The required snippet is included, with the `numpy` installation modified to respect the version constraint.

=== Round 1 Reviewer (gpt5) critique ===
Overall, the proposal is strong and close to ready. It follows the official guidance to install Uni-Mol tools (either via PyPI or from source), targets Python 3.9 which satisfies the 3.8+ requirement, and correctly respects the numpy<2.0.0 constraint noted in the documentation. It also embeds the required SSH/supervisor/net-tools snippet, permits root login via SSH, disables PAM, and explicitly installs mcp and numpy, thus meeting all hard requirements.

Key improvements applied in the finalized Dockerfile:
- RDKit reliability: unimol_tools lists 'rdkit' as a dependency, and RDKit wheels on PyPI can be inconsistent by name (rdkit vs rdkit-pypi). The repository docs for related components recommend 'rdkit-pypi==2022.9.3'. To reduce build risk, we explicitly install rdkit-pypi beforehand and install unimol_tools with --no-deps to avoid re-resolving it. We also include common runtime libraries (libxrender1, libxext6, libgl1-mesa-glx, libsm6) that RDKit often needs.
- Dependency order and pinning: We preinstall pandas<2.0.0 and numpy<2.0.0 to match unimol_tools constraints, and install torch and other Python dependencies before installing unimol_tools from source, which aligns with their docs and reduces surprises during dependency resolution.
- Required snippet parity: We retained an equivalent of the REQUIRED_SSH_MCP_SNIPPET, including supervisor configuration, sshd keepalive tuning, PermitRootLogin yes, UsePAM no, and explicit pip install of mcp and numpy. We also avoided adding a restrictive CMD/ENTRYPOINT.

Residual risks:
- If the environment or PyPI availability for certain wheels (torch, rdkit-pypi) changes, installs may fail; however, this is the most compatible approach per upstream notes. If rdkit (not rdkit-pypi) becomes required strictly by name resolution in future releases, installing unimol_tools without --no-deps may again be necessary, but current setup avoids common breakage.
- No default CMD to launch supervisord; this is intentional to avoid restrictive entrypoints. If a default SSH-up container is desired, a CMD to run supervisord can be added by the runner.

Given these adjustments, the image should build and satisfy the hard requirements and typical runtime needs of unimol_tools.
```

### 引用链接

- https://github.com/deepmodeling/Uni-Mol/tree/main/unimol_tools  — unimol_tools README recommends installing from source for the latest version and notes the removal of Uni-Core dependency.
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py  — setup.py confirms dependencies: numpy<2.0.0, torch, rdkit, etc.
- https://unimol.readthedocs.io/en/latest/installation.html  — Documentation confirms Python requirements and installation steps.
- https://unimol.readthedocs.io/en/latest/installation.html  — Official docs recommending installation via pip and noting numpy<2.0.0 compatibility.
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py  — Setup file showing dependencies: numpy<2.0.0, pandas<2.0.0, torch, rdkit, etc.
- https://github.com/deepmodeling/Uni-Mol  — Repository context; related subprojects (e.g., docking) document using rdkit-pypi wheels on Linux.

### 本轮使用的链接（去重）

- https://github.com/deepmodeling/Uni-Mol/tree/main/unimol_tools
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py
- https://unimol.readthedocs.io/en/latest/installation.html
- https://github.com/deepmodeling/Uni-Mol

### 本轮 Dockerfile（原始）

```dockerfile
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Base system deps (build tools and RDKit runtime libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl unzip supervisor net-tools openssh-server build-essential \
    libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# REQUIRED_SSH_MCP_SNIPPET (equivalent)
RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \
    cat > /etc/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.log
[program:sshd]
command=/usr/sbin/sshd -D
EOF

RUN cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 60
ClientAliveCountMax 3
EOF

RUN mkdir -p /var/run/sshd && \
    mkdir -p /var/log/supervisor && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config && \
    rm -rf /var/lib/apt/lists/*

# Ensure recent pip, and install mandatory packages
RUN python -m pip install --upgrade pip && \
    pip install mcp "numpy<2.0.0"

# Pre-install runtime deps to make unimol_tools install reliable
# Use rdkit-pypi as documented in repo for Linux wheels; keep pandas<2 for compat
RUN pip install "rdkit-pypi==2022.9.3" "pandas<2.0.0" torch joblib pyyaml addict scikit-learn numba tqdm huggingface_hub

# Install Uni-Mol Tools from source, avoiding re-resolving deps
WORKDIR /app
RUN git clone https://github.com/deepmodeling/Uni-Mol.git && \
    pip install --no-deps ./Uni-Mol/unimol_tools

# No restrictive CMD/ENTRYPOINT; supervisord can be started by the runner if needed

```

### 本轮 Dockerfile（sanitize 后实际使用）

```dockerfile
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Base system deps (build tools and RDKit runtime libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl unzip supervisor net-tools openssh-server build-essential \
    libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# REQUIRED_SSH_MCP_SNIPPET (equivalent)
RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \
    cat > /etc/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.log
[program:sshd]
command=/usr/sbin/sshd -D
EOF

RUN cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 60
ClientAliveCountMax 3
EOF

RUN mkdir -p /var/run/sshd && \
    mkdir -p /var/log/supervisor && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config && \
    rm -rf /var/lib/apt/lists/*

# Ensure recent pip, and install mandatory packages
RUN python -m pip install --upgrade pip && \
    pip install mcp "numpy<2.0.0"

# Pre-install runtime deps to make unimol_tools install reliable
# Use rdkit-pypi as documented in repo for Linux wheels; keep pandas<2 for compat
RUN pip install "rdkit-pypi==2022.9.3" "pandas<2.0.0" torch joblib pyyaml addict scikit-learn numba tqdm huggingface_hub

# Install Uni-Mol Tools from source, avoiding re-resolving deps
WORKDIR /app
RUN git clone https://github.com/deepmodeling/Uni-Mol.git && \
    pip install --no-deps ./Uni-Mol/unimol_tools

# No restrictive CMD/ENTRYPOINT; supervisord can be started by the runner if needed

```

### docker build 日志

```text

#0 building with "desktop-linux" instance using docker driver

#1 [internal] load build definition from Dockerfile
#1 transferring dockerfile: 1.80kB done
#1 DONE 0.0s

#2 [internal] load metadata for docker.io/library/python:3.9-slim
#2 ...

#3 [auth] library/python:pull token for registry-1.docker.io
#3 DONE 0.0s

#2 [internal] load metadata for docker.io/library/python:3.9-slim
#2 DONE 3.7s

#4 [internal] load .dockerignore
#4 transferring context: 2B done
#4 DONE 0.0s

#5 [1/9] FROM docker.io/library/python:3.9-slim@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b
#5 resolve docker.io/library/python:3.9-slim@sha256:2d97f6910b16bd338d3060f261f53f144965f755599aab1acda1e13cf1731b1b done
#5 CACHED

#6 [2/9] RUN apt-get update && apt-get install -y --no-install-recommends     git wget curl unzip supervisor net-tools openssh-server build-essential     libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates     && rm -rf /var/lib/apt/lists/*
#6 0.427 Get:1 http://deb.debian.org/debian trixie InRelease [140 kB]
#6 0.783 Get:2 http://deb.debian.org/debian trixie-updates InRelease [47.3 kB]
#6 0.945 Get:3 http://deb.debian.org/debian-security trixie-security InRelease [43.4 kB]
#6 1.250 Get:4 http://deb.debian.org/debian trixie/main arm64 Packages [9607 kB]
#6 130.2 Get:5 http://deb.debian.org/debian trixie-updates/main arm64 Packages [5404 B]
#6 130.3 Get:6 http://deb.debian.org/debian-security trixie-security/main arm64 Packages [85.0 kB]
#6 131.1 Fetched 9928 kB in 2min 11s (75.9 kB/s)
#6 131.1 Reading package lists...
#6 131.3 Reading package lists...
#6 131.6 Building dependency tree...
#6 131.7 Reading state information...
#6 131.7 Package libgl1-mesa-glx is not available, but is referred to by another package.
#6 131.7 This may mean that the package is missing, has been obsoleted, or
#6 131.7 is only available from another source
#6 131.7 
#6 131.7 E: Package 'libgl1-mesa-glx' has no installation candidate
#6 ERROR: process "/bin/sh -c apt-get update && apt-get install -y --no-install-recommends     git wget curl unzip supervisor net-tools openssh-server build-essential     libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates     && rm -rf /var/lib/apt/lists/*" did not complete successfully: exit code: 100
------
 > [2/9] RUN apt-get update && apt-get install -y --no-install-recommends     git wget curl unzip supervisor net-tools openssh-server build-essential     libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates     && rm -rf /var/lib/apt/lists/*:
130.3 Get:6 http://deb.debian.org/debian-security trixie-security/main arm64 Packages [85.0 kB]


131.6 Building dependency tree...
131.7 Reading state information...
131.7 Package libgl1-mesa-glx is not available, but is referred to by another package.
131.7 This may mean that the package is missing, has been obsoleted, or
131.7 is only available from another source
131.7 
131.7 E: Package 'libgl1-mesa-glx' has no installation candidate
------
Dockerfile:7
--------------------
   6 |     # Base system deps (build tools and RDKit runtime libs)
   7 | >>> RUN apt-get update && apt-get install -y --no-install-recommends \
   8 | >>>     git wget curl unzip supervisor net-tools openssh-server build-essential \
   9 | >>>     libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates \
  10 | >>>     && rm -rf /var/lib/apt/lists/*
  11 |     
--------------------
ERROR: failed to build: failed to solve: process "/bin/sh -c apt-get update && apt-get install -y --no-install-recommends     git wget curl unzip supervisor net-tools openssh-server build-essential     libxrender1 libxext6 libgl1-mesa-glx libsm6 ca-certificates     && rm -rf /var/lib/apt/lists/*" did not complete successfully: exit code: 100

```

**本轮结果**：docker build 失败（退出码 1），构建机会已消耗 1 次，将根据日志进行下一轮分析。


---

## 构建尝试 #2（剩余写 Dockerfile 机会：9）

**提案模型**: gemini, **评审模型**: gpt5

**plan.can_build**: True, **confidence**: 0.880

### 综合分析说明

```text
=== Round 1 Proposer (gemini) rationale ===
1. **Fixing Previous Failure**: The previous build failed because `libgl1-mesa-glx` is not available in Debian 12 (Bookworm), which `python:3.9-slim` is based on. I replaced it with `libgl1`, which provides the necessary GL libraries for RDKit/OpenCV-like packages.
2. **Dependency Constraints**: `unimol_tools` explicitly requires `numpy<2.0.0` (due to RDKit compatibility issues with NumPy 2.x). I enforced this constraint in the pip install command.
3. **System Dependencies**: Added `libxrender1`, `libxext6`, `libsm6`, and `libgl1` to support `rdkit` runtime requirements.
4. **Installation Method**: Used the 'Install from source' method (Option 2 in README) to ensure the environment matches the repository context. Pre-installed dependencies (`torch`, `rdkit`, `pandas<2.0.0`) to handle version constraints explicitly before the setup.py runs.
5. **Mandatory Requirements**: Included the SSH/Supervisor/MCP snippet exactly as requested.

=== Round 1 Reviewer (gpt5) critique ===
Strengths of the proposal: 
- It correctly targets unimol_tools, which is the documented, user-friendly entry point and does not require Uni-Core. 
- It enforces numpy<2.0.0, aligning with upstream guidance due to RDKit compatibility. 
- It includes the required SSH/supervisor/net-tools setup, permits root login, disables PAM, and performs pip install of mcp and numpy, satisfying the hard requirements. 
- It fixes the previous build failure by replacing libgl1-mesa-glx with libgl1 on Debian Bookworm.

Important adjustments applied in the final Dockerfile: 
- RDKit packaging: Installing pip package "rdkit" can be unreliable or source-build on Debian slim images. The repository and related docs commonly recommend "rdkit-pypi==2022.9.3" for stable Linux wheels. We pinned rdkit-pypi to reduce build risk. 
- Snippet compliance: We reproduced the REQUIRED_SSH_MCP_SNIPPET semantics, including Supervisor config, SSH keepalive, PermitRootLogin yes, UsePAM no, creation of /var/run/sshd and /var/log/supervisor, and explicit pip install of mcp and numpy. 
- Dependency order: We upgrade pip first, then install strict deps (numpy<2, pandas<2, torch, etc.) before installing unimol_tools from source with --no-deps, preventing setup.py from re-resolving and possibly pulling problematic variants.

Risks and notes: 
- Torch CPU wheels can be large and may vary; if GPU use is needed, the torch install should be aligned with CUDA runtime, per PyTorch docs. For general CPU use, the current approach is acceptable. 
- SSH login may require setting a root password or using keys depending on the runner; however, the snippet matches the required configuration and keeps CMD/ENTRYPOINT unrestricted. 
- If future unimol_tools releases change RDKit packaging assumptions, the rdkit-pypi pin may need to be updated.

Overall, with these modifications, the image adheres to official installation guidance for unimol_tools, satisfies all hard requirements (openssh-server, supervisor, net-tools, pip install mcp, and numpy installation), avoids restrictive entrypoints, and addresses the previously observed apt package issue on Bookworm.
```

### 引用链接

- https://github.com/deepmodeling/Uni-Mol/tree/main/unimol_tools  — README.md specifies installation options and dependencies (numpy<2.0.0).
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py  — setup.py lists dependencies: torch, rdkit, pandas, etc.
- https://packages.debian.org/bookworm/libgl1  — Debian Bookworm (12) replaces libgl1-mesa-glx with libgl1.
- https://unimol.readthedocs.io/en/latest/installation.html  — Official installation guidance for unimol_tools, recommending PyPI or source installation; notes on numpy<2.0.0.
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py  — Lists unimol_tools dependencies (numpy<2, pandas<2, torch, rdkit, etc.).
- https://packages.debian.org/bookworm/libgl1  — Debian Bookworm provides libgl1; libgl1-mesa-glx is not available, addressing the previous build failure.

### 本轮使用的链接（去重）

- https://github.com/deepmodeling/Uni-Mol/tree/main/unimol_tools
- https://github.com/deepmodeling/Uni-Mol/blob/main/unimol_tools/setup.py
- https://packages.debian.org/bookworm/libgl1
- https://unimol.readthedocs.io/en/latest/installation.html

### 本轮 Dockerfile（原始）

```dockerfile
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Base system deps and runtime libs (Bookworm: libgl1 instead of libgl1-mesa-glx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl unzip supervisor net-tools openssh-server build-essential \
    libxrender1 libxext6 libgl1 libsm6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# REQUIRED_SSH_MCP_SNIPPET (exact-equivalent implementation)
RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \
    cat > /etc/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.log
[program:sshd]
command=/usr/sbin/sshd -D
EOF

RUN cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 60
ClientAliveCountMax 3
EOF

RUN mkdir -p /var/run/sshd && \
    mkdir -p /var/log/supervisor && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config

# Ensure recent pip and install mandatory Python packages
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir mcp "numpy<2.0.0"

# Pre-install unimol_tools dependencies; use rdkit-pypi for reliable Linux wheels
RUN pip install --no-cache-dir \
    "pandas<2.0.0" \
    torch \
    joblib \
    pyyaml \
    addict \
    scikit-learn \
    numba \
    tqdm \
    huggingface_hub \
    "rdkit-pypi==2022.9.3"

# Install Uni-Mol Tools from source (Option 2 per docs) without re-resolving deps
WORKDIR /app
RUN git clone https://github.com/deepmodeling/Uni-Mol.git && \
    pip install --no-deps ./Uni-Mol/unimol_tools && \
    rm -rf /app/Uni-Mol

# No restrictive CMD/ENTRYPOINT; supervisord/sshd can be started by the runner if needed

```

### 本轮 Dockerfile（sanitize 后实际使用）

```dockerfile
FROM python:3.9-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# Base system deps and runtime libs (Bookworm: libgl1 instead of libgl1-mesa-glx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl unzip supervisor net-tools openssh-server build-essential \
    libxrender1 libxext6 libgl1 libsm6 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# REQUIRED_SSH_MCP_SNIPPET (exact-equivalent implementation)
RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \
    cat > /etc/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.log
[program:sshd]
command=/usr/sbin/sshd -D
EOF

RUN cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 60
ClientAliveCountMax 3
EOF

RUN mkdir -p /var/run/sshd && \
    mkdir -p /var/log/supervisor && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config

# Ensure recent pip and install mandatory Python packages
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir mcp "numpy<2.0.0"

# Pre-install unimol_tools dependencies; use rdkit-pypi for reliable Linux wheels
RUN pip install --no-cache-dir \
    "pandas<2.0.0" \
    torch \
    joblib \
    pyyaml \
    addict \
    scikit-learn \
    numba \
    tqdm \
    huggingface_hub \
    "rdkit-pypi==2022.9.3"

# Install Uni-Mol Tools from source (Option 2 per docs) without re-resolving deps
WORKDIR /app
RUN git clone https://github.com/deepmodeling/Uni-Mol.git && \
    pip install --no-deps ./Uni-Mol/unimol_tools && \
    rm -rf /app/Uni-Mol

# No restrictive CMD/ENTRYPOINT; supervisord/sshd can be started by the runner if needed

RUN apt-get update && apt-get install -y curl unzip supervisor net-tools openssh-server --no-install-recommends && \
    cat > /etc/supervisord.conf << 'EOF'
[supervisord]
nodaemon=true
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.log
[program:sshd]
command=/usr/sbin/sshd -D
EOF

RUN cat >> /etc/ssh/sshd_config << 'EOF'
ClientAliveInterval 60
ClientAliveCountMax 3
EOF

RUN mkdir -p /var/run/sshd && \
    mkdir -p /var/log/supervisor && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/g' /etc/ssh/sshd_config && \
    sed -i 's/UsePAM yes/UsePAM no/g' /etc/ssh/sshd_config

RUN pip install mcp numpy

```

### docker build 日志

