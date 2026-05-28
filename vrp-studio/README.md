# VRP Studio

VRP Studio 是一个用于展示和调试 VRP 求解过程的可视化服务。

## 启动说明

### 1) 安装依赖

在仓库根目录执行（推荐使用 `uv`）：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -r vrp-studio/requirements.txt
```

或者使用 `pip`：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r vrp-studio/requirements.txt
```

### 2) 安装/构建 vrp-cli（Python 绑定）

如果本地尚未安装可用的 `vrp-cli`，先在仓库根目录执行：

```bash
./build.sh --no-rust
```

Windows:

```powershell
.\build.ps1 -NoRust
```

### 3) 启动服务

在仓库根目录执行：

```bash
uv run --python .venv/bin/python vrp-studio --port 8000
```

Windows:

```powershell
uv run --python .venv\Scripts\python.exe vrp-studio --port 8000
```

如果你已经激活了虚拟环境，也可以直接使用：

```bash
.venv/bin/vrp-studio --port 8000
```

启动后可在浏览器访问：`http://127.0.0.1:8000`。
